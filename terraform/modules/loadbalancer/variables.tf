variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs"
  type        = list(string)
}

variable "alb_security_group_id" {
  description = "Security group ID for ALB"
  type        = string
}

variable "domain_name" {
  description = "Main domain name"
  type        = string
}

variable "enable_deletion_protection" {
  description = "Enable deletion protection for ALB"
  type        = bool
  default     = true
}

variable "enable_access_logs" {
  description = "Enable access logs for ALB"
  type        = bool
  default     = true
}

variable "access_logs_bucket" {
  description = "S3 bucket for ALB access logs"
  type        = string
  default     = ""
}

variable "create_route53_records" {
  description = "Create Route53 records"
  type        = bool
  default     = true
}