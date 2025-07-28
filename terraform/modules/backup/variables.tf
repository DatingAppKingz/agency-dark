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

# RDS Configuration
variable "rds_instance_arn" {
  description = "RDS instance ARN"
  type        = string
}

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

# S3 Configuration
variable "backup_s3_bucket" {
  description = "S3 bucket for backups"
  type        = string
}

variable "backup_s3_bucket_arn" {
  description = "S3 bucket ARN for backups"
  type        = string
}

# Network Configuration
variable "private_subnet_ids" {
  description = "List of private subnet IDs"
  type        = list(string)
}

variable "lambda_security_group_id" {
  description = "Security group ID for Lambda functions"
  type        = string
}