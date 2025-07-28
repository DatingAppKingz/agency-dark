terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
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
      Project     = "AgencyDark"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

# Variables
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

variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Main domain name"
  type        = string
  default     = "agencydark.com"
}