#!/bin/bash
set -euo pipefail

# Automated Backup Script with Verification
# Usage: ./backup-automation.sh <component> [environment]

COMPONENT=${1:-all}
ENVIRONMENT=${2:-production}
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Configuration
BACKUP_BUCKET="s3://agency-backups"
BACKUP_RETENTION_DAYS=30
NOTIFICATION_WEBHOOK=${SLACK_WEBHOOK_URL:-}

# Components
declare -A COMPONENTS=(
    ["database"]="PostgreSQL database"
    ["redis"]="Redis cache"
    ["files"]="Application files and uploads"
    ["configs"]="Configuration and secrets"
    ["monitoring"]="Monitoring data and dashboards"
)

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

# Send notification
notify() {
    local status=$1
    local message=$2
    
    if [[ -n "$NOTIFICATION_WEBHOOK" ]]; then
        curl -X POST $NOTIFICATION_WEBHOOK \
            -H 'Content-Type: application/json' \
            -d "{\"text\":\"Backup $status: $message\"}" \
            2>/dev/null || true
    fi
}

# Backup database
backup_database() {
    log_info "Starting database backup..."
    
    local backup_name="postgres-${ENVIRONMENT}-${TIMESTAMP}.sql.gz"
    local backup_path="$BACKUP_BUCKET/postgres/$backup_name"
    
    # Create backup job
    kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: backup-db-${TIMESTAMP}
  namespace: ${ENVIRONMENT}
spec:
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: backup
        image: postgres:16-alpine
        command:
        - sh
        - -c
        - |
          set -e
          apk add --no-cache aws-cli
          
          # Create backup with compression
          pg_dump \$DATABASE_URL --no-owner --clean --if-exists | gzip > /tmp/backup.sql.gz
          
          # Calculate checksum
          sha256sum /tmp/backup.sql.gz > /tmp/backup.sql.gz.sha256
          
          # Upload to S3
          aws s3 cp /tmp/backup.sql.gz $backup_path
          aws s3 cp /tmp/backup.sql.gz.sha256 ${backup_path}.sha256
          
          # Verify upload
          aws s3 ls $backup_path
          
          echo "Database backup completed: $backup_name"
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: database-url
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: backup-credentials
              key: access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: backup-credentials
              key: secret-access-key
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
EOF
    
    # Wait for completion
    kubectl wait --for=condition=complete job/backup-db-${TIMESTAMP} -n ${ENVIRONMENT} --timeout=1800s
    
    log_success "Database backup completed: $backup_name"
    echo "$backup_path"
}

# Backup Redis
backup_redis() {
    log_info "Starting Redis backup..."
    
    local backup_name="redis-${ENVIRONMENT}-${TIMESTAMP}.rdb"
    local backup_path="$BACKUP_BUCKET/redis/$backup_name"
    
    # Create backup job
    kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: backup-redis-${TIMESTAMP}
  namespace: ${ENVIRONMENT}
spec:
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: backup
        image: redis:7-alpine
        command:
        - sh
        - -c
        - |
          set -e
          apk add --no-cache aws-cli
          
          # Trigger Redis backup
          redis-cli -h \$REDIS_HOST --rdb /tmp/backup.rdb
          
          # Upload to S3
          aws s3 cp /tmp/backup.rdb $backup_path
          
          echo "Redis backup completed: $backup_name"
        env:
        - name: REDIS_HOST
          value: agency-redis-master
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: backup-credentials
              key: access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: backup-credentials
              key: secret-access-key
EOF
    
    # Wait for completion
    kubectl wait --for=condition=complete job/backup-redis-${TIMESTAMP} -n ${ENVIRONMENT} --timeout=600s
    
    log_success "Redis backup completed: $backup_name"
    echo "$backup_path"
}

# Backup files
backup_files() {
    log_info "Starting files backup..."
    
    local backup_name="files-${ENVIRONMENT}-${TIMESTAMP}.tar.gz"
    local backup_path="$BACKUP_BUCKET/files/$backup_name"
    
    # Create backup job
    kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: backup-files-${TIMESTAMP}
  namespace: ${ENVIRONMENT}
spec:
  ttlSecondsAfterFinished: 3600
  template:
    spec:
      restartPolicy: Never
      volumes:
      - name: app-data
        persistentVolumeClaim:
          claimName: agency-app-data
      containers:
      - name: backup
        image: alpine:3.18
        command:
        - sh
        - -c
        - |
          set -e
          apk add --no-cache aws-cli tar
          
          # Create archive
          tar -czf /tmp/backup.tar.gz -C /data .
          
          # Upload to S3
          aws s3 cp /tmp/backup.tar.gz $backup_path
          
          echo "Files backup completed: $backup_name"
        volumeMounts:
        - name: app-data
          mountPath: /data
          readOnly: true
        env:
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: backup-credentials
              key: access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: backup-credentials
              key: secret-access-key
EOF
    
    # Wait for completion
    kubectl wait --for=condition=complete job/backup-files-${TIMESTAMP} -n ${ENVIRONMENT} --timeout=1800s
    
    log_success "Files backup completed: $backup_name"
    echo "$backup_path"
}

# Backup configurations
backup_configs() {
    log_info "Starting configuration backup..."
    
    local backup_name="configs-${ENVIRONMENT}-${TIMESTAMP}.tar.gz"
    local temp_dir="/tmp/config-backup-$$"
    
    mkdir -p $temp_dir
    
    # Export Kubernetes resources
    kubectl get configmaps,secrets,services,deployments,ingresses \
        -n ${ENVIRONMENT} \
        -o yaml > $temp_dir/k8s-resources.yaml
    
    # Export Helm values
    helm get values agency-backend -n ${ENVIRONMENT} > $temp_dir/helm-values.yaml
    
    # Create archive
    tar -czf $temp_dir/backup.tar.gz -C $temp_dir .
    
    # Upload to S3
    aws s3 cp $temp_dir/backup.tar.gz $BACKUP_BUCKET/configs/$backup_name
    
    # Cleanup
    rm -rf $temp_dir
    
    log_success "Configuration backup completed: $backup_name"
    echo "$BACKUP_BUCKET/configs/$backup_name"
}

# Backup monitoring data
backup_monitoring() {
    log_info "Starting monitoring data backup..."
    
    local backup_name="monitoring-${ENVIRONMENT}-${TIMESTAMP}.tar.gz"
    
    # Export Grafana dashboards
    kubectl exec -n monitoring deployment/grafana -- \
        grafana-cli admin export-dashboard --dir /tmp/dashboards
    
    # Export Prometheus rules
    kubectl get prometheusrules -n monitoring -o yaml > /tmp/prometheus-rules.yaml
    
    # Create archive and upload
    kubectl exec -n monitoring deployment/grafana -- \
        tar -czf /tmp/monitoring-backup.tar.gz /tmp/dashboards /tmp/prometheus-rules.yaml
    
    kubectl cp monitoring/$(kubectl get pod -n monitoring -l app=grafana -o jsonpath='{.items[0].metadata.name}'):/tmp/monitoring-backup.tar.gz \
        /tmp/monitoring-backup.tar.gz
    
    aws s3 cp /tmp/monitoring-backup.tar.gz $BACKUP_BUCKET/monitoring/$backup_name
    
    log_success "Monitoring backup completed: $backup_name"
    echo "$BACKUP_BUCKET/monitoring/$backup_name"
}

# Verify backup
verify_backup() {
    local backup_path=$1
    local component=$2
    
    log_info "Verifying backup: $backup_path"
    
    # Check if backup exists in S3
    if ! aws s3 ls $backup_path > /dev/null 2>&1; then
        log_error "Backup not found in S3: $backup_path"
        return 1
    fi
    
    # Check backup size
    local size=$(aws s3 ls $backup_path | awk '{print $3}')
    if [[ $size -lt 1000 ]]; then
        log_warning "Backup size is suspiciously small: $size bytes"
        return 1
    fi
    
    # Verify checksum if available
    if aws s3 ls ${backup_path}.sha256 > /dev/null 2>&1; then
        log_info "Verifying checksum..."
        # Download and verify checksum
        aws s3 cp ${backup_path}.sha256 /tmp/
        aws s3 cp $backup_path /tmp/
        if sha256sum -c /tmp/$(basename ${backup_path}).sha256; then
            log_success "Checksum verification passed"
        else
            log_error "Checksum verification failed"
            return 1
        fi
    fi
    
    log_success "Backup verification passed"
    return 0
}

# Clean old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups (retention: $BACKUP_RETENTION_DAYS days)..."
    
    local cutoff_date=$(date -d "$BACKUP_RETENTION_DAYS days ago" +%Y-%m-%d)
    
    for component in "${!COMPONENTS[@]}"; do
        log_info "Cleaning $component backups older than $cutoff_date"
        
        aws s3 ls $BACKUP_BUCKET/$component/ --recursive | \
        while read -r line; do
            local file_date=$(echo $line | awk '{print $1}')
            local file_path=$(echo $line | awk '{print $4}')
            
            if [[ "$file_date" < "$cutoff_date" ]]; then
                log_info "Deleting old backup: $file_path"
                aws s3 rm $BACKUP_BUCKET/$file_path
            fi
        done
    done
    
    log_success "Cleanup completed"
}

# Generate backup report
generate_report() {
    local results=$1
    
    log_info "Generating backup report..."
    
    local report="/tmp/backup-report-${TIMESTAMP}.txt"
    
    cat > $report <<EOF
BACKUP REPORT
=============
Date: $(date)
Environment: $ENVIRONMENT
Component: $COMPONENT

Results:
$results

Storage Usage:
$(aws s3 ls $BACKUP_BUCKET --recursive --human-readable --summarize | tail -n 2)

Recent Backups:
$(aws s3 ls $BACKUP_BUCKET --recursive | sort -r | head -n 10)
EOF
    
    # Upload report
    aws s3 cp $report $BACKUP_BUCKET/reports/$(basename $report)
    
    # Send notification
    notify "Report" "Backup report available at: $BACKUP_BUCKET/reports/$(basename $report)"
    
    cat $report
}

# Main backup process
main() {
    log_info "Starting backup automation"
    log_info "Environment: $ENVIRONMENT"
    log_info "Component: $COMPONENT"
    
    local results=""
    local failed=0
    
    # Perform backups based on component selection
    if [[ "$COMPONENT" == "all" ]]; then
        for comp in "${!COMPONENTS[@]}"; do
            log_info "Backing up: ${COMPONENTS[$comp]}"
            if backup_path=$(backup_$comp 2>&1); then
                if verify_backup "$backup_path" "$comp"; then
                    results+="\n✓ $comp: SUCCESS - $backup_path"
                else
                    results+="\n✗ $comp: VERIFICATION FAILED - $backup_path"
                    ((failed++))
                fi
            else
                results+="\n✗ $comp: FAILED"
                ((failed++))
            fi
        done
    else
        if [[ -v COMPONENTS[$COMPONENT] ]]; then
            if backup_path=$(backup_$COMPONENT 2>&1); then
                if verify_backup "$backup_path" "$COMPONENT"; then
                    results+="\n✓ $COMPONENT: SUCCESS - $backup_path"
                else
                    results+="\n✗ $COMPONENT: VERIFICATION FAILED - $backup_path"
                    ((failed++))
                fi
            else
                results+="\n✗ $COMPONENT: FAILED"
                ((failed++))
            fi
        else
            log_error "Unknown component: $COMPONENT"
            exit 1
        fi
    fi
    
    # Cleanup old backups
    cleanup_old_backups
    
    # Generate report
    generate_report "$results"
    
    # Final status
    if [[ $failed -eq 0 ]]; then
        log_success "All backups completed successfully"
        notify "Success" "All backups completed for $ENVIRONMENT"
        exit 0
    else
        log_error "$failed backup(s) failed"
        notify "Failed" "$failed backup(s) failed for $ENVIRONMENT"
        exit 1
    fi
}

# Run main function
main