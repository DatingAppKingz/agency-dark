variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "agencydark"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

# Networking
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

# Domain
variable "domain_name" {
  description = "Main domain name"
  type        = string
  default     = "agencydark.com"
}

variable "create_route53_records" {
  description = "Create Route53 records"
  type        = bool
  default     = true
}

# Database
variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.5"
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "rds_allocated_storage" {
  description = "Allocated storage in GB"
  type        = number
  default     = 100
}

variable "database_name" {
  description = "Name of the database"
  type        = string
  default     = "agencydark"
}

variable "db_master_username" {
  description = "Master username for RDS"
  type        = string
  default     = "postgres"
}

variable "db_master_password" {
  description = "Master password for RDS"
  type        = string
  sensitive   = true
}

variable "backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 7
}

# Redis
variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "7.1"
}

variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes"
  type        = number
  default     = 2
}

variable "redis_auth_token" {
  description = "Auth token for Redis"
  type        = string
  sensitive   = true
}

variable "redis_snapshot_retention_limit" {
  description = "Number of days to retain Redis snapshots"
  type        = number
  default     = 7
}

# Application
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

# Monitoring
variable "alert_email_addresses" {
  description = "Email addresses for alerts"
  type        = list(string)
  default     = []
}