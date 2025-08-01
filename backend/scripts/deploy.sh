#!/bin/bash

# Agency Dark Backend Deployment Script
# Handles deployment to various environments

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOYMENT_ENV="${1:-staging}"
DEPLOYMENT_VERSION="${2:-latest}"

# Load environment-specific configuration
ENV_FILE="${PROJECT_ROOT}/.env.${DEPLOYMENT_ENV}"
if [ -f "$ENV_FILE" ]; then
    export $(cat "$ENV_FILE" | grep -v '^#' | xargs)
fi

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check required tools
    local required_tools=("docker" "kubectl" "helm" "git")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed"
            exit 1
        fi
    done
    
    # Check environment variables
    local required_vars=("DATABASE_URL" "REDIS_URL" "SECRET_KEY")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            log_error "Environment variable $var is not set"
            exit 1
        fi
    done
    
    log_info "Prerequisites check passed"
}

run_tests() {
    log_info "Running tests..."
    
    cd "$PROJECT_ROOT"
    
    # Run unit tests
    poetry run pytest tests/unit/ -v --tb=short || {
        log_error "Unit tests failed"
        exit 1
    }
    
    # Run integration tests (if not production)
    if [ "$DEPLOYMENT_ENV" != "production" ]; then
        poetry run pytest tests/integration/ -v --tb=short || {
            log_error "Integration tests failed"
            exit 1
        }
    fi
    
    # Run security scan
    poetry run bandit -r . -ll || {
        log_warning "Security issues found"
    }
    
    # Check dependencies
    poetry run safety check || {
        log_warning "Vulnerable dependencies found"
    }
    
    log_info "Tests completed"
}

build_docker_image() {
    log_info "Building Docker image..."
    
    cd "$PROJECT_ROOT"
    
    # Build image
    docker build \
        -t "agency-dark-backend:${DEPLOYMENT_VERSION}" \
        -t "agency-dark-backend:latest" \
        -f Dockerfile \
        . || {
        log_error "Docker build failed"
        exit 1
    }
    
    # Tag for registry
    if [ -n "${DOCKER_REGISTRY:-}" ]; then
        docker tag "agency-dark-backend:${DEPLOYMENT_VERSION}" \
            "${DOCKER_REGISTRY}/agency-dark-backend:${DEPLOYMENT_VERSION}"
        
        # Push to registry
        docker push "${DOCKER_REGISTRY}/agency-dark-backend:${DEPLOYMENT_VERSION}" || {
            log_error "Docker push failed"
            exit 1
        }
    fi
    
    log_info "Docker image built and pushed"
}

run_database_migrations() {
    log_info "Running database migrations..."
    
    # Run migrations in a temporary container
    docker run --rm \
        -e DATABASE_URL="$DATABASE_URL" \
        --network host \
        "agency-dark-backend:${DEPLOYMENT_VERSION}" \
        alembic upgrade head || {
        log_error "Database migrations failed"
        exit 1
    }
    
    log_info "Database migrations completed"
}

deploy_kubernetes() {
    log_info "Deploying to Kubernetes..."
    
    cd "$PROJECT_ROOT/k8s"
    
    # Update ConfigMap
    kubectl create configmap agency-dark-config \
        --from-env-file="$ENV_FILE" \
        --dry-run=client -o yaml | kubectl apply -f - || {
        log_error "ConfigMap update failed"
        exit 1
    }
    
    # Update Secrets (if they've changed)
    if [ -f "${PROJECT_ROOT}/.secrets.${DEPLOYMENT_ENV}" ]; then
        kubectl create secret generic agency-dark-secrets \
            --from-env-file="${PROJECT_ROOT}/.secrets.${DEPLOYMENT_ENV}" \
            --dry-run=client -o yaml | kubectl apply -f - || {
            log_error "Secrets update failed"
            exit 1
        }
    fi
    
    # Deploy using Helm
    helm upgrade --install agency-dark-backend \
        ../helm/agency-dark \
        --namespace "${K8S_NAMESPACE:-default}" \
        --set image.tag="${DEPLOYMENT_VERSION}" \
        --set environment="${DEPLOYMENT_ENV}" \
        --values "../helm/agency-dark/values.${DEPLOYMENT_ENV}.yaml" || {
        log_error "Helm deployment failed"
        exit 1
    }
    
    # Wait for deployment to be ready
    kubectl rollout status deployment/agency-dark-backend \
        -n "${K8S_NAMESPACE:-default}" \
        --timeout=5m || {
        log_error "Deployment rollout failed"
        exit 1
    }
    
    log_info "Kubernetes deployment completed"
}

deploy_docker_compose() {
    log_info "Deploying with Docker Compose..."
    
    cd "$PROJECT_ROOT"
    
    # Stop existing containers
    docker-compose -f "docker-compose.${DEPLOYMENT_ENV}.yml" down
    
    # Start new containers
    docker-compose -f "docker-compose.${DEPLOYMENT_ENV}.yml" up -d || {
        log_error "Docker Compose deployment failed"
        exit 1
    }
    
    # Wait for health checks
    sleep 10
    
    # Check health
    docker-compose -f "docker-compose.${DEPLOYMENT_ENV}.yml" ps | grep -q "healthy" || {
        log_error "Health checks failed"
        docker-compose -f "docker-compose.${DEPLOYMENT_ENV}.yml" logs
        exit 1
    }
    
    log_info "Docker Compose deployment completed"
}

run_post_deployment_checks() {
    log_info "Running post-deployment checks..."
    
    # Get deployment URL
    if [ "$DEPLOYMENT_ENV" = "production" ]; then
        API_URL="${PRODUCTION_URL:-https://api.agencydark.com}"
    else
        API_URL="${STAGING_URL:-http://localhost:8000}"
    fi
    
    # Check health endpoint
    curl -f "${API_URL}/health" || {
        log_error "Health check failed"
        exit 1
    }
    
    # Check metrics endpoint
    curl -f "${API_URL}/metrics" || {
        log_warning "Metrics endpoint not accessible"
    }
    
    # Run smoke tests
    poetry run pytest tests/smoke/ --api-url="$API_URL" -v || {
        log_error "Smoke tests failed"
        exit 1
    }
    
    log_info "Post-deployment checks passed"
}

send_deployment_notification() {
    log_info "Sending deployment notification..."
    
    # Prepare notification data
    local notification="{
        \"text\": \"Deployment completed\",
        \"environment\": \"${DEPLOYMENT_ENV}\",
        \"version\": \"${DEPLOYMENT_VERSION}\",
        \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
    }"
    
    # Send to Slack (if configured)
    if [ -n "${SLACK_WEBHOOK_URL:-}" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "$notification" \
            "$SLACK_WEBHOOK_URL" || {
            log_warning "Failed to send Slack notification"
        }
    fi
    
    # Log to monitoring system
    echo "$notification" >> "${PROJECT_ROOT}/logs/deployments.log"
    
    log_info "Notifications sent"
}

rollback_deployment() {
    log_error "Deployment failed, initiating rollback..."
    
    if [ "$DEPLOYMENT_METHOD" = "kubernetes" ]; then
        kubectl rollout undo deployment/agency-dark-backend \
            -n "${K8S_NAMESPACE:-default}"
    elif [ "$DEPLOYMENT_METHOD" = "docker-compose" ]; then
        cd "$PROJECT_ROOT"
        docker-compose -f "docker-compose.${DEPLOYMENT_ENV}.yml" down
        # Restore previous version
        docker tag "agency-dark-backend:previous" "agency-dark-backend:latest"
        docker-compose -f "docker-compose.${DEPLOYMENT_ENV}.yml" up -d
    fi
    
    log_error "Rollback completed"
    exit 1
}

# Main deployment flow
main() {
    log_info "Starting deployment to ${DEPLOYMENT_ENV} environment"
    log_info "Version: ${DEPLOYMENT_VERSION}"
    
    # Set deployment method based on environment
    if [ "$DEPLOYMENT_ENV" = "production" ] || [ "$DEPLOYMENT_ENV" = "staging" ]; then
        DEPLOYMENT_METHOD="kubernetes"
    else
        DEPLOYMENT_METHOD="docker-compose"
    fi
    
    # Trap errors for rollback
    trap rollback_deployment ERR
    
    # Execute deployment steps
    check_prerequisites
    run_tests
    build_docker_image
    
    # Tag current as previous for rollback
    docker tag "agency-dark-backend:latest" "agency-dark-backend:previous" 2>/dev/null || true
    
    run_database_migrations
    
    # Deploy based on method
    if [ "$DEPLOYMENT_METHOD" = "kubernetes" ]; then
        deploy_kubernetes
    else
        deploy_docker_compose
    fi
    
    run_post_deployment_checks
    send_deployment_notification
    
    # Remove error trap
    trap - ERR
    
    log_info "Deployment completed successfully!"
}

# Show usage if no environment specified
if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <environment> [version]"
    echo "Environments: development, staging, production"
    echo "Example: $0 staging v1.2.3"
    exit 1
fi

# Run main deployment
main