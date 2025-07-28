# ECR Repository for Docker images
resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}-backend-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${var.project_name}-backend-ecr-${var.environment}"
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${var.project_name}-frontend-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${var.project_name}-frontend-ecr-${var.environment}"
  }
}

resource "aws_ecr_repository" "celery" {
  name                 = "${var.project_name}-celery-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "${var.project_name}-celery-ecr-${var.environment}"
  }
}

# ECR Lifecycle Policies
resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project_name}-ecs-cluster-${var.environment}"
  }
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}-backend-${var.environment}"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-backend-logs-${var.environment}"
  }
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.project_name}-frontend-${var.environment}"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-frontend-logs-${var.environment}"
  }
}

resource "aws_cloudwatch_log_group" "celery" {
  name              = "/ecs/${var.project_name}-celery-${var.environment}"
  retention_in_days = 30

  tags = {
    Name = "${var.project_name}-celery-logs-${var.environment}"
  }
}

# Task Execution Role
resource "aws_iam_role" "ecs_task_execution_role" {
  name_prefix = "${var.project_name}-ecs-task-exec-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ecs-task-exec-role-${var.environment}"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task Role
resource "aws_iam_role" "ecs_task_role" {
  name_prefix = "${var.project_name}-ecs-task-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ecs-task-role-${var.environment}"
  }
}

# S3 access for task role
resource "aws_iam_role_policy" "ecs_task_s3_policy" {
  name = "${var.project_name}-ecs-task-s3-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${var.s3_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arn
        ]
      }
    ]
  })
}

# Secrets Manager access for task execution role
resource "aws_iam_role_policy" "ecs_task_execution_secrets_policy" {
  name = "${var.project_name}-ecs-task-exec-secrets-policy"
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project_name}/*"
        ]
      }
    ]
  })
}

# Backend Task Definition
resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend-${var.environment}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn           = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name  = "backend"
      image = "${aws_ecr_repository.backend.repository_url}:latest"
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "ENVIRONMENT"
          value = var.environment
        },
        {
          name  = "DATABASE_URL"
          value = "postgresql://${var.db_username}:${var.db_password}@${var.db_endpoint}/${var.db_name}"
        },
        {
          name  = "REDIS_URL"
          value = "redis://:${var.redis_auth_token}@${var.redis_endpoint}:${var.redis_port}"
        }
      ]

      secrets = [
        {
          name      = "JWT_SECRET_KEY"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/jwt_secret"
        },
        {
          name      = "STRIPE_API_KEY"
          valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/stripe_api_key"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.project_name}-backend-task-${var.environment}"
  }
}

# Backend Service
resource "aws_ecs_service" "backend" {
  name            = "${var.project_name}-backend-${var.environment}"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    security_groups  = [var.app_security_group_id]
    subnets          = var.private_subnet_ids
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.backend_target_group_arn
    container_name   = "backend"
    container_port   = 8000
  }

  service_registries {
    registry_arn = aws_service_discovery_service.backend.arn
  }

  deployment_configuration {
    maximum_percent         = 200
    minimum_healthy_percent = 100
  }

  depends_on = [var.alb_listener_arn]

  tags = {
    Name = "${var.project_name}-backend-service-${var.environment}"
  }
}

# Service Discovery
resource "aws_service_discovery_private_dns_namespace" "main" {
  name        = "${var.project_name}.local"
  description = "Private namespace for ${var.project_name}"
  vpc         = var.vpc_id

  tags = {
    Name = "${var.project_name}-service-discovery-${var.environment}"
  }
}

resource "aws_service_discovery_service" "backend" {
  name = "backend"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id

    dns_records {
      ttl  = 10
      type = "A"
    }

    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# Auto Scaling
resource "aws_appautoscaling_target" "backend_ecs_target" {
  max_capacity       = var.backend_max_capacity
  min_capacity       = var.backend_min_capacity
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.backend.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "backend_cpu_scaling" {
  name               = "${var.project_name}-backend-cpu-scaling-${var.environment}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend_ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.backend_ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend_ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}

resource "aws_appautoscaling_policy" "backend_memory_scaling" {
  name               = "${var.project_name}-backend-memory-scaling-${var.environment}"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.backend_ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.backend_ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.backend_ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value = 80.0
  }
}

# Data source for AWS account ID
data "aws_caller_identity" "current" {}

# Outputs
output "ecs_cluster_id" {
  description = "ECS cluster ID"
  value       = aws_ecs_cluster.main.id
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "backend_ecr_repository_url" {
  description = "Backend ECR repository URL"
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_ecr_repository_url" {
  description = "Frontend ECR repository URL"
  value       = aws_ecr_repository.frontend.repository_url
}

output "celery_ecr_repository_url" {
  description = "Celery ECR repository URL"
  value       = aws_ecr_repository.celery.repository_url
}

output "backend_service_name" {
  description = "Backend ECS service name"
  value       = aws_ecs_service.backend.name
}

output "service_discovery_namespace_id" {
  description = "Service discovery namespace ID"
  value       = aws_service_discovery_private_dns_namespace.main.id
}