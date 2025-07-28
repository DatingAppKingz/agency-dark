variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "domain_name" {
  description = "Main domain name"
  type        = string
}

variable "cloudfront_certificate_arn" {
  description = "ACM certificate ARN for CloudFront (must be in us-east-1)"
  type        = string
}