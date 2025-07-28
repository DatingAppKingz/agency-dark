# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-${var.environment}"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.project_name}-db-subnet-${var.environment}"
  }
}

# RDS Parameter Group
resource "aws_db_parameter_group" "postgres" {
  name_prefix = "${var.project_name}-postgres-"
  family      = "postgres15"
  description = "PostgreSQL parameter group for ${var.project_name}"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_duration"
    value = "1"
  }

  tags = {
    Name = "${var.project_name}-postgres-params-${var.environment}"
  }
}

# RDS Instance
resource "aws_db_instance" "postgres" {
  identifier = "${var.project_name}-postgres-${var.environment}"
  
  # Engine
  engine         = "postgres"
  engine_version = var.postgres_version
  
  # Instance
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true
  
  # Database
  db_name  = var.database_name
  username = var.master_username
  password = var.master_password
  port     = 5432
  
  # Network
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  
  # Backup
  backup_retention_period = var.backup_retention_period
  backup_window          = var.backup_window
  maintenance_window     = var.maintenance_window
  
  # Performance and Monitoring
  parameter_group_name        = aws_db_parameter_group.postgres.name
  enabled_cloudwatch_logs_exports = ["postgresql"]
  performance_insights_enabled    = true
  performance_insights_retention_period = 7
  monitoring_interval            = 60
  monitoring_role_arn           = aws_iam_role.rds_monitoring.arn
  
  # High Availability
  multi_az = var.multi_az
  
  # Other
  deletion_protection = var.deletion_protection
  skip_final_snapshot = false
  final_snapshot_identifier = "${var.project_name}-postgres-final-${var.environment}-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  
  tags = {
    Name = "${var.project_name}-postgres-${var.environment}"
  }
}

# RDS Monitoring Role
resource "aws_iam_role" "rds_monitoring" {
  name_prefix = "${var.project_name}-rds-monitoring-"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Name = "${var.project_name}-rds-monitoring-${var.environment}"
  }
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-redis-subnet-${var.environment}"
  subnet_ids = var.private_subnet_ids

  tags = {
    Name = "${var.project_name}-redis-subnet-${var.environment}"
  }
}

# ElastiCache Parameter Group
resource "aws_elasticache_parameter_group" "redis" {
  name_prefix = "${var.project_name}-redis-"
  family      = "redis7"
  description = "Redis parameter group for ${var.project_name}"

  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  tags = {
    Name = "${var.project_name}-redis-params-${var.environment}"
  }
}

# ElastiCache Redis
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${var.project_name}-redis-${var.environment}"
  replication_group_description = "Redis cluster for ${var.project_name}"
  
  # Engine
  engine               = "redis"
  engine_version       = var.redis_version
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  port                 = 6379
  
  # Instance
  node_type                  = var.redis_node_type
  number_cache_clusters      = var.redis_num_cache_nodes
  automatic_failover_enabled = var.redis_num_cache_nodes > 1
  
  # Network
  subnet_group_name = aws_elasticache_subnet_group.main.name
  security_group_ids = [var.redis_security_group_id]
  
  # Security
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token
  
  # Backup
  snapshot_retention_limit = var.redis_snapshot_retention_limit
  snapshot_window         = var.redis_snapshot_window
  
  # Maintenance
  maintenance_window = var.redis_maintenance_window
  
  # Notifications
  notification_topic_arn = var.sns_topic_arn
  
  tags = {
    Name = "${var.project_name}-redis-${var.environment}"
  }
}

# Outputs
output "postgres_endpoint" {
  description = "PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = true
}

output "postgres_database_name" {
  description = "PostgreSQL database name"
  value       = aws_db_instance.postgres.db_name
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive   = true
}

output "redis_port" {
  description = "Redis port"
  value       = aws_elasticache_replication_group.redis.port
}