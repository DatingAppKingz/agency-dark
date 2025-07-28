terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket = "agencydark-terraform-state"
    key    = "production/terraform.tfstate"
    region = "us-east-1"
    encrypt = true
    dynamodb_table = "agencydark-terraform-locks"
  }
}

# Provider Configuration
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# Networking Module
module "networking" {
  source = "../../modules/networking"
  
  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = data.aws_availability_zones.available.names
  enable_nat_gateway = true
}

# Database Module
module "database" {
  source = "../../modules/database"
  
  project_name       = var.project_name
  environment        = var.environment
  private_subnet_ids = module.networking.private_subnet_ids
  security_group_id  = module.networking.database_security_group_id
  redis_security_group_id = module.networking.redis_security_group_id
  
  # RDS Configuration
  postgres_version         = var.postgres_version
  instance_class          = var.rds_instance_class
  allocated_storage       = var.rds_allocated_storage
  database_name           = var.database_name
  master_username         = var.db_master_username
  master_password         = var.db_master_password
  backup_retention_period = var.backup_retention_period
  multi_az               = true
  deletion_protection    = true
  
  # Redis Configuration
  redis_version                  = var.redis_version
  redis_node_type               = var.redis_node_type
  redis_num_cache_nodes         = var.redis_num_cache_nodes
  redis_auth_token              = var.redis_auth_token
  redis_snapshot_retention_limit = var.redis_snapshot_retention_limit
}

# Storage Module
module "storage" {
  source = "../../modules/storage"
  
  project_name               = var.project_name
  environment                = var.environment
  domain_name               = var.domain_name
  cloudfront_certificate_arn = aws_acm_certificate.cloudfront.arn
}

# ACM Certificate for CloudFront (must be in us-east-1)
resource "aws_acm_certificate" "cloudfront" {
  provider          = aws.us_east_1
  domain_name       = "cdn.${var.domain_name}"
  validation_method = "DNS"
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name = "${var.project_name}-cdn-cert-${var.environment}"
  }
}

# Additional provider for us-east-1 (required for CloudFront certificates)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
  
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# Load Balancer Module
module "loadbalancer" {
  source = "../../modules/loadbalancer"
  
  project_name                = var.project_name
  environment                 = var.environment
  vpc_id                      = module.networking.vpc_id
  public_subnet_ids           = module.networking.public_subnet_ids
  alb_security_group_id       = module.networking.alb_security_group_id
  domain_name                 = var.domain_name
  enable_deletion_protection  = true
  enable_access_logs          = true
  access_logs_bucket          = module.storage.alb_logs_bucket_name
  create_route53_records      = var.create_route53_records
}

# Application Module
module "application" {
  source = "../../modules/application"
  
  project_name             = var.project_name
  environment              = var.environment
  aws_region               = var.aws_region
  vpc_id                   = module.networking.vpc_id
  private_subnet_ids       = module.networking.private_subnet_ids
  app_security_group_id    = module.networking.app_security_group_id
  backend_target_group_arn = module.loadbalancer.backend_target_group_arn
  alb_listener_arn         = module.loadbalancer.https_listener_arn
  
  # Database Configuration
  db_endpoint      = module.database.postgres_endpoint
  db_name          = var.database_name
  db_username      = var.db_master_username
  db_password      = var.db_master_password
  
  # Redis Configuration
  redis_endpoint   = module.database.redis_endpoint
  redis_port       = module.database.redis_port
  redis_auth_token = var.redis_auth_token
  
  # S3 Configuration
  s3_bucket_arn = module.storage.uploads_bucket_arn
  
  # Service Configuration
  backend_cpu           = var.backend_cpu
  backend_memory        = var.backend_memory
  backend_desired_count = var.backend_desired_count
  backend_min_capacity  = var.backend_min_capacity
  backend_max_capacity  = var.backend_max_capacity
}

# Monitoring Module
module "monitoring" {
  source = "../../modules/monitoring"
  
  project_name          = var.project_name
  environment           = var.environment
  aws_region            = var.aws_region
  alert_email_addresses = var.alert_email_addresses
  
  # Resources to monitor
  ecs_cluster_name               = module.application.ecs_cluster_name
  alb_name                       = split("/", module.loadbalancer.alb_arn)[2]
  alb_arn_suffix                 = regex(".*:loadbalancer/(.*)", module.loadbalancer.alb_arn)[0]
  backend_target_group_arn_suffix = regex(".*:(.*)", module.loadbalancer.backend_target_group_arn)[0]
  rds_instance_id                = split(":", module.database.postgres_endpoint)[0]
  redis_cluster_id               = "${var.project_name}-redis-${var.environment}"
  backend_log_group_name         = "/ecs/${var.project_name}-backend-${var.environment}"
}

# Backup Module
module "backup" {
  source = "../../modules/backup"
  
  project_name      = var.project_name
  environment       = var.environment
  aws_region        = var.aws_region
  
  # Resources to backup
  rds_instance_arn = "arn:aws:rds:${var.aws_region}:${data.aws_caller_identity.current.account_id}:db:${var.project_name}-postgres-${var.environment}"
  
  # Database configuration for Lambda backup
  db_endpoint      = module.database.postgres_endpoint
  db_name          = var.database_name
  db_username      = var.db_master_username
  db_password      = var.db_master_password
  
  # S3 Configuration
  backup_s3_bucket     = module.storage.backups_bucket_name
  backup_s3_bucket_arn = module.storage.backups_bucket_arn
  
  # Network Configuration
  private_subnet_ids       = module.networking.private_subnet_ids
  lambda_security_group_id = aws_security_group.lambda.id
}

# Security Group for Lambda functions
resource "aws_security_group" "lambda" {
  name_prefix = "${var.project_name}-lambda-"
  description = "Security group for Lambda functions"
  vpc_id      = module.networking.vpc_id
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
  
  tags = {
    Name = "${var.project_name}-lambda-sg-${var.environment}"
  }
}

# Data source for AWS account ID
data "aws_caller_identity" "current" {}

# Outputs
output "alb_dns_name" {
  description = "ALB DNS name"
  value       = module.loadbalancer.alb_dns_name
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = module.storage.cloudfront_domain_name
}

output "ecr_repository_urls" {
  description = "ECR repository URLs"
  value = {
    backend = module.application.backend_ecr_repository_url
    frontend = module.application.frontend_ecr_repository_url
    celery  = module.application.celery_ecr_repository_url
  }
}

output "monitoring_dashboard_url" {
  description = "CloudWatch dashboard URL"
  value       = module.monitoring.dashboard_url
}