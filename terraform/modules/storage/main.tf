# S3 Bucket for uploads
resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project_name}-uploads-${var.environment}"

  tags = {
    Name = "${var.project_name}-uploads-${var.environment}"
  }
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket Lifecycle Rules
resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "delete-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }

  rule {
    id     = "expire-temp-uploads"
    status = "Enabled"

    filter {
      prefix = "temp/"
    }

    expiration {
      days = 7
    }
  }
}

# S3 Bucket CORS Configuration
resource "aws_s3_bucket_cors_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = ["https://*.${var.domain_name}"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# S3 Bucket for ALB access logs
resource "aws_s3_bucket" "alb_logs" {
  bucket = "${var.project_name}-alb-logs-${var.environment}"

  tags = {
    Name = "${var.project_name}-alb-logs-${var.environment}"
  }
}

# S3 Bucket Policy for ALB access logs
data "aws_elb_service_account" "main" {}

resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = data.aws_elb_service_account.main.arn
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.alb_logs.arn}/*"
      }
    ]
  })
}

# S3 Bucket for backups
resource "aws_s3_bucket" "backups" {
  bucket = "${var.project_name}-backups-${var.environment}"

  tags = {
    Name = "${var.project_name}-backups-${var.environment}"
  }
}

# S3 Bucket Versioning for backups
resource "aws_s3_bucket_versioning" "backups" {
  bucket = aws_s3_bucket.backups.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption for backups
resource "aws_s3_bucket_server_side_encryption_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 Bucket Lifecycle for backups
resource "aws_s3_bucket_lifecycle_configuration" "backups" {
  bucket = aws_s3_bucket.backups.id

  rule {
    id     = "transition-old-backups"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }
}

# CloudFront Distribution for static assets
resource "aws_cloudfront_distribution" "static_assets" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.project_name} static assets"
  default_root_object = "index.html"

  origin {
    domain_name = aws_s3_bucket.uploads.bucket_regional_domain_name
    origin_id   = "S3-${aws_s3_bucket.uploads.id}"

    s3_origin_config {
      origin_access_identity = aws_cloudfront_origin_access_identity.static_assets.cloudfront_access_identity_path
    }
  }

  aliases = ["cdn.${var.domain_name}"]

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.uploads.id}"

    forwarded_values {
      query_string = false
      headers      = ["Origin", "Access-Control-Request-Method", "Access-Control-Request-Headers"]

      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
    compress               = true
  }

  # Cache behavior for images
  ordered_cache_behavior {
    path_pattern     = "*.jpg"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.uploads.id}"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400
    max_ttl                = 31536000
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.cloudfront_certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name = "${var.project_name}-cdn-${var.environment}"
  }
}

# CloudFront Origin Access Identity
resource "aws_cloudfront_origin_access_identity" "static_assets" {
  comment = "${var.project_name} static assets OAI"
}

# Update S3 bucket policy to allow CloudFront access
resource "aws_s3_bucket_policy" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = aws_cloudfront_origin_access_identity.static_assets.iam_arn
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.uploads.arn}/*"
      }
    ]
  })
}

# Outputs
output "uploads_bucket_name" {
  description = "Name of the uploads S3 bucket"
  value       = aws_s3_bucket.uploads.id
}

output "uploads_bucket_arn" {
  description = "ARN of the uploads S3 bucket"
  value       = aws_s3_bucket.uploads.arn
}

output "backups_bucket_name" {
  description = "Name of the backups S3 bucket"
  value       = aws_s3_bucket.backups.id
}

output "backups_bucket_arn" {
  description = "ARN of the backups S3 bucket"
  value       = aws_s3_bucket.backups.arn
}

output "alb_logs_bucket_name" {
  description = "Name of the ALB logs S3 bucket"
  value       = aws_s3_bucket.alb_logs.id
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.static_assets.id
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = aws_cloudfront_distribution.static_assets.domain_name
}