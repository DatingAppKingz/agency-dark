#!/bin/bash
set -euo pipefail

# Blue-Green Deployment Script for Agency Backend
# Usage: ./blue-green-deploy.sh <image-tag> [namespace]

IMAGE_TAG=${1:-latest}
NAMESPACE=${2:-production}
TIMEOUT=${TIMEOUT:-600}  # 10 minutes default timeout

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
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
    log_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        log_error "Namespace $NAMESPACE does not exist"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Get current active deployment (blue or green)
get_active_deployment() {
    local selector=$(kubectl get service agency-backend -n $NAMESPACE -o jsonpath='{.spec.selector.deployment}')
    echo $selector
}

# Get inactive deployment (opposite of active)
get_inactive_deployment() {
    local active=$1
    if [[ "$active" == "blue" ]]; then
        echo "green"
    else
        echo "blue"
    fi
}

# Scale deployment
scale_deployment() {
    local deployment=$1
    local replicas=$2
    
    log_info "Scaling $deployment to $replicas replicas..."
    kubectl scale deployment agency-backend-$deployment -n $NAMESPACE --replicas=$replicas
    
    # Wait for scaling to complete
    kubectl rollout status deployment/agency-backend-$deployment -n $NAMESPACE --timeout=${TIMEOUT}s
}

# Update deployment image
update_deployment_image() {
    local deployment=$1
    local image_tag=$2
    
    log_info "Updating $deployment deployment with image tag: $image_tag"
    kubectl set image deployment/agency-backend-$deployment backend=agency/backend:$image_tag -n $NAMESPACE
    
    # Wait for rollout to complete
    kubectl rollout status deployment/agency-backend-$deployment -n $NAMESPACE --timeout=${TIMEOUT}s
}

# Run health checks
run_health_checks() {
    local deployment=$1
    local retries=30
    local delay=10
    
    log_info "Running health checks for $deployment deployment..."
    
    # Get a pod from the deployment
    local pod=$(kubectl get pods -n $NAMESPACE -l app=agency-backend,deployment=$deployment -o jsonpath='{.items[0].metadata.name}')
    
    if [[ -z "$pod" ]]; then
        log_error "No pods found for $deployment deployment"
        return 1
    fi
    
    # Check pod health
    for i in $(seq 1 $retries); do
        if kubectl exec -n $NAMESPACE $pod -- curl -f http://localhost:8000/health/ready &> /dev/null; then
            log_success "Health check passed for $deployment deployment"
            return 0
        fi
        
        log_warning "Health check failed, attempt $i/$retries"
        sleep $delay
    done
    
    log_error "Health checks failed after $retries attempts"
    return 1
}

# Switch traffic to new deployment
switch_traffic() {
    local new_deployment=$1
    
    log_info "Switching traffic to $new_deployment deployment..."
    kubectl patch service agency-backend -n $NAMESPACE -p '{"spec":{"selector":{"deployment":"'$new_deployment'"}}}'
    
    log_success "Traffic switched to $new_deployment deployment"
}

# Run smoke tests
run_smoke_tests() {
    local deployment=$1
    
    log_info "Running smoke tests against $deployment deployment..."
    
    # Get service endpoint
    local service_ip=$(kubectl get service agency-backend -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
    
    if [[ -z "$service_ip" ]]; then
        service_ip=$(kubectl get service agency-backend -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')
    fi
    
    # Run basic smoke tests
    if curl -f http://$service_ip/health &> /dev/null; then
        log_success "Smoke test passed: Health endpoint"
    else
        log_error "Smoke test failed: Health endpoint"
        return 1
    fi
    
    if curl -f http://$service_ip/api/v1/status &> /dev/null; then
        log_success "Smoke test passed: API status endpoint"
    else
        log_error "Smoke test failed: API status endpoint"
        return 1
    fi
    
    return 0
}

# Main deployment flow
main() {
    log_info "Starting Blue-Green deployment to $NAMESPACE with image tag: $IMAGE_TAG"
    
    # Check prerequisites
    check_prerequisites
    
    # Get current active deployment
    ACTIVE=$(get_active_deployment)
    INACTIVE=$(get_inactive_deployment $ACTIVE)
    
    log_info "Current active deployment: $ACTIVE"
    log_info "Will deploy to: $INACTIVE"
    
    # Update inactive deployment with new image
    update_deployment_image $INACTIVE $IMAGE_TAG
    
    # Scale up inactive deployment
    scale_deployment $INACTIVE 3
    
    # Run health checks on new deployment
    if ! run_health_checks $INACTIVE; then
        log_error "Health checks failed on $INACTIVE deployment"
        log_info "Rolling back by scaling down $INACTIVE deployment"
        scale_deployment $INACTIVE 0
        exit 1
    fi
    
    # Switch traffic to new deployment
    switch_traffic $INACTIVE
    
    # Run smoke tests on new deployment
    if ! run_smoke_tests $INACTIVE; then
        log_error "Smoke tests failed on $INACTIVE deployment"
        log_info "Rolling back traffic to $ACTIVE deployment"
        switch_traffic $ACTIVE
        scale_deployment $INACTIVE 0
        exit 1
    fi
    
    # Wait for traffic to stabilize
    log_info "Waiting for traffic to stabilize..."
    sleep 30
    
    # Scale down old deployment
    log_info "Scaling down old $ACTIVE deployment..."
    scale_deployment $ACTIVE 0
    
    log_success "Blue-Green deployment completed successfully!"
    log_info "Active deployment is now: $INACTIVE"
}

# Run main function
main