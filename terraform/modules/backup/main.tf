# AWS Backup Vault
resource "aws_backup_vault" "main" {
  name        = "${var.project_name}-backup-vault-${var.environment}"
  kms_key_arn = aws_kms_key.backup.arn

  tags = {
    Name = "${var.project_name}-backup-vault-${var.environment}"
  }
}

# KMS Key for Backup Encryption
resource "aws_kms_key" "backup" {
  description             = "KMS key for ${var.project_name} backups"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-backup-key-${var.environment}"
  }
}

resource "aws_kms_alias" "backup" {
  name          = "alias/${var.project_name}-backup-${var.environment}"
  target_key_id = aws_kms_key.backup.key_id
}

# Backup Plan
resource "aws_backup_plan" "main" {
  name = "${var.project_name}-backup-plan-${var.environment}"

  rule {
    rule_name         = "daily_backups"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 3 * * ? *)" # Daily at 3 AM UTC
    start_window      = 60
    completion_window = 120

    lifecycle {
      delete_after = 30 # Keep daily backups for 30 days
    }

    recovery_point_tags = {
      Type = "daily"
    }
  }

  rule {
    rule_name         = "weekly_backups"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 5 ? * 1 *)" # Weekly on Monday at 5 AM UTC
    start_window      = 60
    completion_window = 180

    lifecycle {
      delete_after       = 90  # Keep weekly backups for 90 days
      cold_storage_after = 30  # Move to cold storage after 30 days
    }

    recovery_point_tags = {
      Type = "weekly"
    }
  }

  rule {
    rule_name         = "monthly_backups"
    target_vault_name = aws_backup_vault.main.name
    schedule          = "cron(0 5 1 * ? *)" # Monthly on 1st at 5 AM UTC
    start_window      = 60
    completion_window = 240

    lifecycle {
      delete_after       = 365 # Keep monthly backups for 1 year
      cold_storage_after = 60  # Move to cold storage after 60 days
    }

    recovery_point_tags = {
      Type = "monthly"
    }
  }

  tags = {
    Name = "${var.project_name}-backup-plan-${var.environment}"
  }
}

# Backup Selection for RDS
resource "aws_backup_selection" "rds" {
  iam_role_arn = aws_iam_role.backup.arn
  name         = "${var.project_name}-rds-backup-selection-${var.environment}"
  plan_id      = aws_backup_plan.main.id

  resources = [
    var.rds_instance_arn
  ]

  condition {
    string_equals {
      key   = "aws:ResourceTag/Environment"
      value = var.environment
    }
  }
}

# Backup Selection for EBS Volumes
resource "aws_backup_selection" "ebs" {
  iam_role_arn = aws_iam_role.backup.arn
  name         = "${var.project_name}-ebs-backup-selection-${var.environment}"
  plan_id      = aws_backup_plan.main.id

  selection_tag {
    type  = "STRINGEQUALS"
    key   = "Backup"
    value = "true"
  }
}

# IAM Role for AWS Backup
resource "aws_iam_role" "backup" {
  name_prefix = "${var.project_name}-backup-role-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "backup.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-backup-role-${var.environment}"
  }
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "backup_restore" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForRestores"
}

# Lambda Function for Database Dumps
resource "aws_lambda_function" "db_backup" {
  filename         = "${path.module}/lambda/db_backup.zip"
  function_name    = "${var.project_name}-db-backup-${var.environment}"
  role            = aws_iam_role.lambda_backup.arn
  handler         = "index.handler"
  source_code_hash = filebase64sha256("${path.module}/lambda/db_backup.zip")
  runtime         = "python3.11"
  timeout         = 900
  memory_size     = 512

  environment {
    variables = {
      DB_HOST        = var.db_endpoint
      DB_NAME        = var.db_name
      DB_USER        = var.db_username
      DB_PASSWORD    = var.db_password
      S3_BUCKET      = var.backup_s3_bucket
      S3_PREFIX      = "database-dumps/"
      ENVIRONMENT    = var.environment
    }
  }

  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [var.lambda_security_group_id]
  }

  tags = {
    Name = "${var.project_name}-db-backup-lambda-${var.environment}"
  }
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_backup" {
  name_prefix = "${var.project_name}-lambda-backup-role-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-lambda-backup-role-${var.environment}"
  }
}

# Lambda Execution Policy
resource "aws_iam_role_policy" "lambda_backup_policy" {
  name = "${var.project_name}-lambda-backup-policy"
  role = aws_iam_role.lambda_backup.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${var.backup_s3_bucket_arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = [
          aws_kms_key.backup.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  role       = aws_iam_role.lambda_backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

# EventBridge Rule for Lambda
resource "aws_cloudwatch_event_rule" "db_backup_schedule" {
  name                = "${var.project_name}-db-backup-schedule-${var.environment}"
  description         = "Trigger database backup Lambda"
  schedule_expression = "cron(0 4 * * ? *)" # Daily at 4 AM UTC

  tags = {
    Name = "${var.project_name}-db-backup-schedule-${var.environment}"
  }
}

resource "aws_cloudwatch_event_target" "db_backup_lambda" {
  rule      = aws_cloudwatch_event_rule.db_backup_schedule.name
  target_id = "DbBackupLambdaTarget"
  arn       = aws_lambda_function.db_backup.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.db_backup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.db_backup_schedule.arn
}

# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "lambda_backup" {
  name              = "/aws/lambda/${aws_lambda_function.db_backup.function_name}"
  retention_in_days = 14

  tags = {
    Name = "${var.project_name}-db-backup-logs-${var.environment}"
  }
}

# Outputs
output "backup_vault_arn" {
  description = "Backup vault ARN"
  value       = aws_backup_vault.main.arn
}

output "backup_plan_id" {
  description = "Backup plan ID"
  value       = aws_backup_plan.main.id
}

output "backup_kms_key_arn" {
  description = "Backup KMS key ARN"
  value       = aws_kms_key.backup.arn
}

output "db_backup_lambda_arn" {
  description = "Database backup Lambda ARN"
  value       = aws_lambda_function.db_backup.arn
}