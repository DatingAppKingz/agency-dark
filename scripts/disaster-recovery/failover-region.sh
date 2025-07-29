#!/bin/bash
set -euo pipefail

# Multi-Region Failover Script
# Usage: ./failover-region.sh <target-region> [--emergency]

TARGET_REGION=${1:-us-west-2}
EMERGENCY_MODE=${2:-}
CURRENT_REGION=${AWS_DEFAULT_REGION:-us-east-1}

# Configuration
PRIMARY_CLUSTER="agency-production"
DR_CLUSTER="agency-dr"
DNS_ZONE_ID="Z1234567890ABC"
DOMAIN="api.agency.com"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites for failover..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed"
        exit 1
    fi
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    # Verify target region cluster
    if ! aws eks describe-cluster --name $DR_CLUSTER --region $TARGET_REGION &> /dev/null; then
        log_error "DR cluster not found in region: $TARGET_REGION"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Health check for region
check_region_health() {
    local region=$1
    local cluster=$2
    
    log_info "Checking health of $cluster in $region..."
    
    # Update kubeconfig
    aws eks update-kubeconfig --name $cluster --region $region
    
    # Check cluster nodes
    local ready_nodes=$(kubectl get nodes --no-headers | grep " Ready " | wc -l)
    if [[ $ready_nodes -lt 3 ]]; then
        log_warning "Only $ready_nodes nodes ready in $cluster"
        return 1
    fi
    
    # Check critical deployments
    local healthy_deploys=$(kubectl get deployments -n production --no-headers | grep -E "([0-9]+)/\1" | wc -l)
    local total_deploys=$(kubectl get deployments -n production --no-headers | wc -l)
    
    if [[ $healthy_deploys -ne $total_deploys ]]; then
        log_warning "Not all deployments are healthy: $healthy_deploys/$total_deploys"
        return 1
    fi
    
    log_success "Region $region is healthy"
    return 0
}

# Sync data to DR region
sync_data() {
    log_info "Syncing data to DR region..."
    
    # Trigger final database replication
    kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: final-db-sync-$(date +%s)
  namespace: production
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: sync
        image: postgres:16-alpine
        command:
        - sh
        - -c
        - |
          # Perform final sync
          pg_dump \$PRIMARY_DB | psql \$DR_DB
          echo "Final database sync completed"
        env:
        - name: PRIMARY_DB
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: primary-url
        - name: DR_DB
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: dr-url
EOF
    
    # Wait for sync to complete
    kubectl wait --for=condition=complete job/final-db-sync-* -n production --timeout=600s
    
    log_success "Data sync completed"
}

# Update application configuration
update_app_config() {
    local region=$1
    
    log_info "Updating application configuration for $region..."
    
    # Update region-specific configs
    kubectl patch configmap app-config -n production --type merge -p '
    {
      "data": {
        "AWS_REGION": "'$region'",
        "IS_PRIMARY": "true",
        "FAILOVER_MODE": "active"
      }
    }'
    
    # Restart deployments to pick up new config
    kubectl rollout restart deployment -n production
    
    log_success "Application configuration updated"
}

# Switch DNS
switch_dns() {
    local target_region=$1
    
    log_info "Switching DNS to $target_region..."
    
    # Get DR load balancer endpoint
    aws eks update-kubeconfig --name $DR_CLUSTER --region $target_region
    local dr_endpoint=$(kubectl get service agency-backend -n production -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
    
    if [[ -z "$dr_endpoint" ]]; then
        log_error "Could not find DR endpoint"
        return 1
    fi
    
    # Update Route53 record
    cat > /tmp/dns-change.json <<EOF
{
  "Changes": [
    {
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "$DOMAIN",
        "Type": "CNAME",
        "TTL": 60,
        "ResourceRecords": [
          {
            "Value": "$dr_endpoint"
          }
        ]
      }
    }
  ]
}
EOF
    
    # Apply DNS change
    CHANGE_ID=$(aws route53 change-resource-record-sets \
        --hosted-zone-id $DNS_ZONE_ID \
        --change-batch file:///tmp/dns-change.json \
        --query 'ChangeInfo.Id' --output text)
    
    log_info "DNS change initiated: $CHANGE_ID"
    
    # Wait for DNS propagation
    aws route53 wait resource-record-sets-changed --id $CHANGE_ID
    
    log_success "DNS switched to DR region"
}

# Verify failover
verify_failover() {
    local region=$1
    
    log_info "Verifying failover to $region..."
    
    # Check DNS resolution
    local resolved_endpoint=$(dig +short $DOMAIN | tail -n1)
    log_info "DNS resolves to: $resolved_endpoint"
    
    # Test API endpoint
    local response=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN/health)
    if [[ "$response" == "200" ]]; then
        log_success "API endpoint is responding"
    else
        log_error "API endpoint returned: $response"
        return 1
    fi
    
    # Check metrics
    aws eks update-kubeconfig --name $DR_CLUSTER --region $region
    kubectl top nodes
    kubectl top pods -n production
    
    log_success "Failover verification completed"
}

# Notify stakeholders
notify_stakeholders() {
    local status=$1
    local message=$2
    
    log_info "Notifying stakeholders..."
    
    # Send notifications via SNS
    aws sns publish \
        --topic-arn "arn:aws:sns:${AWS_DEFAULT_REGION}:123456789012:dr-notifications" \
        --subject "Disaster Recovery Failover: $status" \
        --message "$message"
    
    # Update status page
    curl -X POST https://api.statuspage.io/v1/incidents \
        -H "Authorization: OAuth $STATUSPAGE_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
            "incident": {
                "name": "Regional Failover in Progress",
                "status": "investigating",
                "message": "'"$message"'"
            }
        }'
}

# Main failover process
main() {
    log_info "Starting regional failover process"
    log_info "Current Region: $CURRENT_REGION"
    log_info "Target Region: $TARGET_REGION"
    
    # Check if emergency mode
    if [[ "$EMERGENCY_MODE" == "--emergency" ]]; then
        log_warning "EMERGENCY MODE: Skipping health checks"
    else
        # Verify current region is actually down
        if check_region_health $CURRENT_REGION $PRIMARY_CLUSTER; then
            log_warning "Primary region appears healthy. Use --emergency to force failover."
            read -p "Continue anyway? (yes/no): " confirm
            if [[ "$confirm" != "yes" ]]; then
                log_info "Failover cancelled"
                exit 0
            fi
        fi
    fi
    
    # Check prerequisites
    check_prerequisites
    
    # Verify DR region health
    if ! check_region_health $TARGET_REGION $DR_CLUSTER; then
        log_error "DR region is not healthy. Cannot proceed with failover."
        exit 1
    fi
    
    # Start failover
    notify_stakeholders "Started" "Regional failover initiated from $CURRENT_REGION to $TARGET_REGION"
    
    # Sync final data
    if [[ "$EMERGENCY_MODE" != "--emergency" ]]; then
        sync_data
    fi
    
    # Update configurations
    aws eks update-kubeconfig --name $DR_CLUSTER --region $TARGET_REGION
    update_app_config $TARGET_REGION
    
    # Switch DNS
    switch_dns $TARGET_REGION
    
    # Verify failover
    sleep 30  # Wait for DNS propagation
    if verify_failover $TARGET_REGION; then
        log_success "Regional failover completed successfully"
        notify_stakeholders "Completed" "Regional failover to $TARGET_REGION completed successfully"
    else
        log_error "Failover verification failed"
        notify_stakeholders "Failed" "Regional failover verification failed. Manual intervention required."
        exit 1
    fi
    
    # Print summary
    echo -e "\n${GREEN}=== Failover Summary ===${NC}"
    echo -e "Previous Region: ${RED}$CURRENT_REGION${NC}"
    echo -e "Active Region: ${GREEN}$TARGET_REGION${NC}"
    echo -e "DNS: $DOMAIN"
    echo -e "Status: ${GREEN}ACTIVE${NC}"
    echo -e "\nNext steps:"
    echo -e "1. Monitor application metrics"
    echo -e "2. Verify all integrations"
    echo -e "3. Plan recovery of primary region"
}

# Run main function
main