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

variable "alert_email_addresses" {
  description = "Email addresses for alerts"
  type        = list(string)
  default     = []
}

# ECS Configuration
variable "ecs_cluster_name" {
  description = "ECS cluster name"
  type        = string
}

# ALB Configuration
variable "alb_name" {
  description = "ALB name"
  type        = string
}

variable "alb_arn_suffix" {
  description = "ALB ARN suffix"
  type        = string
}

variable "backend_target_group_arn_suffix" {
  description = "Backend target group ARN suffix"
  type        = string
}

# RDS Configuration
variable "rds_instance_id" {
  description = "RDS instance identifier"
  type        = string
}

# Redis Configuration
variable "redis_cluster_id" {
  description = "Redis cluster ID"
  type        = string
}

# CloudWatch Logs
variable "backend_log_group_name" {
  description = "Backend CloudWatch log group name"
  type        = string
}