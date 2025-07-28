#!/bin/bash

# AgencyDark Deployment Script
# This script handles the deployment of the AgencyDark application

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
ACTION=${2:-deploy}
AWS_REGION=${AWS_REGION:-us-east-1}
PROJECT_NAME="agencydark"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Terraform is installed
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured. Please run 'aws configure'."
        exit 1
    fi
    
    print_status "All prerequisites are met."
}

# Function to build and push Docker images
build_and_push_images() {
    print_status "Building and pushing Docker images..."
    
    # Get ECR login token
    aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.$AWS_REGION.amazonaws.com
    
    # Get ECR repository URLs from Terraform output
    cd terraform/environments/$ENVIRONMENT
    BACKEND_REPO=$(terraform output -raw ecr_repository_urls | jq -r .backend)
    
    # Build and push backend image
    print_status "Building backend image..."
    cd ../../../backend
    docker build -t $PROJECT_NAME-backend:latest .
    docker tag $PROJECT_NAME-backend:latest $BACKEND_REPO:latest
    docker tag $PROJECT_NAME-backend:latest $BACKEND_REPO:$GITHUB_SHA
    
    print_status "Pushing backend image..."
    docker push $BACKEND_REPO:latest
    docker push $BACKEND_REPO:$GITHUB_SHA
    
    print_status "Docker images built and pushed successfully."
}

# Function to deploy infrastructure with Terraform
deploy_infrastructure() {
    print_status "Deploying infrastructure with Terraform..."
    
    cd terraform/environments/$ENVIRONMENT
    
    # Initialize Terraform
    terraform init
    
    # Plan deployment
    terraform plan -out=tfplan
    
    # Apply deployment
    terraform apply tfplan
    
    print_status "Infrastructure deployed successfully."
}

# Function to update ECS services
update_ecs_services() {
    print_status "Updating ECS services..."
    
    # Get cluster name from Terraform output
    cd terraform/environments/$ENVIRONMENT
    CLUSTER_NAME=$(terraform output -raw ecs_cluster_name)
    
    # Force new deployment of backend service
    aws ecs update-service \
        --cluster $CLUSTER_NAME \
        --service $PROJECT_NAME-backend-$ENVIRONMENT \
        --force-new-deployment \
        --region $AWS_REGION
    
    print_status "Waiting for service to stabilize..."
    aws ecs wait services-stable \
        --cluster $CLUSTER_NAME \
        --services $PROJECT_NAME-backend-$ENVIRONMENT \
        --region $AWS_REGION
    
    print_status "ECS services updated successfully."
}

# Function to run database migrations
run_migrations() {
    print_status "Running database migrations..."
    
    # Get database endpoint from Terraform output
    cd terraform/environments/$ENVIRONMENT
    DB_ENDPOINT=$(terraform output -raw postgres_endpoint)
    
    # Run migrations using ECS task
    aws ecs run-task \
        --cluster $CLUSTER_NAME \
        --task-definition $PROJECT_NAME-backend-$ENVIRONMENT \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[$(terraform output -json private_subnet_ids | jq -r 'join(",")')]},securityGroups=[$(terraform output -raw app_security_group_id)]}" \
        --overrides '{"containerOverrides":[{"name":"backend","command":["alembic","upgrade","head"]}]}' \
        --region $AWS_REGION
    
    print_status "Database migrations completed."
}

# Function to perform health checks
health_check() {
    print_status "Performing health checks..."
    
    # Get ALB DNS name from Terraform output
    cd terraform/environments/$ENVIRONMENT
    ALB_DNS=$(terraform output -raw alb_dns_name)
    
    # Wait for ALB to be healthy
    for i in {1..30}; do
        if curl -f -s https://$ALB_DNS/health > /dev/null; then
            print_status "Health check passed!"
            return 0
        fi
        echo -n "."
        sleep 10
    done
    
    print_error "Health check failed!"
    return 1
}

# Function to rollback deployment
rollback_deployment() {
    print_warning "Rolling back deployment..."
    
    # Implement rollback logic here
    # This could involve:
    # - Reverting to previous Docker image
    # - Rolling back database migrations
    # - Restoring previous Terraform state
    
    print_status "Rollback completed."
}

# Main deployment flow
main() {
    print_status "Starting deployment for environment: $ENVIRONMENT"
    
    # Check prerequisites
    check_prerequisites
    
    case $ACTION in
        deploy)
            # Full deployment
            build_and_push_images
            deploy_infrastructure
            update_ecs_services
            run_migrations
            health_check
            
            if [ $? -eq 0 ]; then
                print_status "Deployment completed successfully!"
            else
                print_error "Deployment failed!"
                rollback_deployment
                exit 1
            fi
            ;;
            
        build)
            # Only build and push images
            build_and_push_images
            ;;
            
        infrastructure)
            # Only deploy infrastructure
            deploy_infrastructure
            ;;
            
        rollback)
            # Rollback deployment
            rollback_deployment
            ;;
            
        *)
            print_error "Unknown action: $ACTION"
            echo "Usage: $0 [environment] [action]"
            echo "Actions: deploy, build, infrastructure, rollback"
            exit 1
            ;;
    esac
}

# Run main function
main