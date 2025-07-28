variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "app_security_group_id" {
  description = "Security group ID for application"
  type        = string
}

variable "backend_target_group_arn" {
  description = "Target group ARN for backend"
  type        = string
}

variable "alb_listener_arn" {
  description = "ALB listener ARN"
  type        = string
}

# Database Configuration
variable "db_endpoint" {
  description = "Database endpoint"
  type        = string
}

variable "db_name" {
  description = "Database name"
  type        = string
}

variable "db_username" {
  description = "Database username"
  type        = string
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

# Redis Configuration
variable "redis_endpoint" {
  description = "Redis endpoint"
  type        = string
}

variable "redis_port" {
  description = "Redis port"
  type        = number
}

variable "redis_auth_token" {
  description = "Redis auth token"
  type        = string
  sensitive   = true
}

# S3 Configuration
variable "s3_bucket_arn" {
  description = "S3 bucket ARN for uploads"
  type        = string
}

# Backend Configuration
variable "backend_cpu" {
  description = "CPU units for backend task"
  type        = number
  default     = 1024
}

variable "backend_memory" {
  description = "Memory for backend task"
  type        = number
  default     = 2048
}

variable "backend_desired_count" {
  description = "Desired count for backend service"
  type        = number
  default     = 2
}

variable "backend_min_capacity" {
  description = "Minimum capacity for backend autoscaling"
  type        = number
  default     = 2
}

variable "backend_max_capacity" {
  description = "Maximum capacity for backend autoscaling"
  type        = number
  default     = 10
}

# Frontend Configuration
variable "frontend_cpu" {
  description = "CPU units for frontend task"
  type        = number
  default     = 512
}

variable "frontend_memory" {
  description = "Memory for frontend task"
  type        = number
  default     = 1024
}

variable "frontend_desired_count" {
  description = "Desired count for frontend service"
  type        = number
  default     = 2
}

# Celery Configuration
variable "celery_cpu" {
  description = "CPU units for celery task"
  type        = number
  default     = 512
}

variable "celery_memory" {
  description = "Memory for celery task"
  type        = number
  default     = 1024
}

variable "celery_desired_count" {
  description = "Desired count for celery workers"
  type        = number
  default     = 2
}