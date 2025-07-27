#!/bin/bash
set -e

# Deployment script for AgencyDark production

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check environment file
    if [ ! -f ".env.production" ]; then
        log_error ".env.production file not found"
        log_info "Copy .env.production.example to .env.production and configure it"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Validate environment
validate_environment() {
    log_info "Validating environment configuration..."
    
    cd backend
    python scripts/validate_env.py --env-file ../.env.production
    if [ $? -ne 0 ]; then
        log_error "Environment validation failed"
        exit 1
    fi
    cd ..
    
    log_info "Environment validation passed"
}

# Create required directories
create_directories() {
    log_info "Creating required directories..."
    
    mkdir -p backend/{logs,uploads,ml_models,temp}
    mkdir -p docker/postgres
    
    # Set permissions
    chmod 777 backend/{logs,uploads,temp}
    chmod 755 backend/ml_models
    
    log_info "Directories created"
}

# Build images
build_images() {
    log_info "Building Docker images..."
    
    # Load environment variables
    export $(cat .env.production | grep -v '^#' | xargs)
    
    # Build with build arguments
    docker-compose -f docker-compose.prod.yml build \
        --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
        --build-arg VCS_REF=$(git rev-parse --short HEAD) \
        --build-arg VERSION=${VERSION:-1.0.0}
    
    log_info "Images built successfully"
}

# Deploy application
deploy() {
    log_info "Deploying application..."
    
    # Stop existing containers
    log_info "Stopping existing containers..."
    docker-compose -f docker-compose.prod.yml down
    
    # Start new containers
    log_info "Starting new containers..."
    docker-compose -f docker-compose.prod.yml up -d
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10
    
    # Check health
    check_health
    
    log_info "Deployment completed successfully"
}

# Check health of services
check_health() {
    log_info "Checking service health..."
    
    # Check database
    if docker-compose -f docker-compose.prod.yml exec -T db pg_isready -U agencydark; then
        log_info "Database is healthy"
    else
        log_error "Database health check failed"
        exit 1
    fi
    
    # Check Redis
    if docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping | grep -q PONG; then
        log_info "Redis is healthy"
    else
        log_error "Redis health check failed"
        exit 1
    fi
    
    # Check backend API
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        log_info "Backend API is healthy"
    else
        log_error "Backend API health check failed"
        exit 1
    fi
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    docker-compose -f docker-compose.prod.yml exec -T backend alembic upgrade head
    
    if [ $? -eq 0 ]; then
        log_info "Migrations completed successfully"
    else
        log_error "Migrations failed"
        exit 1
    fi
}

# Show logs
show_logs() {
    log_info "Showing logs (Ctrl+C to exit)..."
    docker-compose -f docker-compose.prod.yml logs -f
}

# Main deployment flow
main() {
    log_info "Starting AgencyDark production deployment"
    
    # Change to project root
    cd "$(dirname "$0")/.."
    
    # Run deployment steps
    check_prerequisites
    validate_environment
    create_directories
    build_images
    deploy
    run_migrations
    
    log_info "Deployment completed!"
    log_info "Access the application at: https://yourdomain.com"
    log_info "View logs with: $0 logs"
}

# Parse command line arguments
case "${1}" in
    logs)
        show_logs
        ;;
    health)
        check_health
        ;;
    migrate)
        run_migrations
        ;;
    *)
        main
        ;;
esac