# Production Readiness Guide - Backend Polish 12

## Overview

This guide documents the comprehensive production readiness implementation for the Agency Dark backend, covering error handling, monitoring, deployment automation, and operational procedures.

## Completed Components

### 1. Advanced Error Handling ✅

**File**: `core/error_handling/error_handler.py`

#### Features:
- **Custom Exception Hierarchy**: Structured exceptions for different error types
- **Comprehensive Error Tracking**: Integration with Sentry for production error monitoring
- **User-Friendly Messages**: Separate internal and user-facing error messages
- **Error Recovery**: Circuit breaker pattern for external services
- **Error Analytics**: Track and analyze error patterns
- **Detailed Logging**: Structured logging with context

#### Exception Types:
```python
# Validation errors
raise ValidationException("Invalid email format", field="email")

# Authentication/Authorization
raise AuthenticationException("Token expired")
raise AuthorizationException("Insufficient permissions")

# Business logic
raise BusinessLogicException("Insufficient balance", rule="minimum_balance")

# External services
raise ExternalServiceException("Payment Gateway", "Connection timeout")

# Resource not found
raise ResourceNotFoundException("User", user_id)
```

#### Circuit Breaker Usage:
```python
# Create circuit breaker for external service
payment_circuit = error_handler.create_circuit_breaker(
    name="payment_gateway",
    failure_threshold=5,
    recovery_timeout=60
)

# Use circuit breaker
try:
    result = await payment_circuit.call(payment_service.process, payment_data)
except ExternalServiceException:
    # Handle gracefully
    pass
```

### 2. Comprehensive Monitoring System ✅

**File**: `core/monitoring/monitoring_system.py`

#### Metrics Collection:
- **Prometheus Integration**: Export metrics in Prometheus format
- **OpenTelemetry Tracing**: Distributed tracing support
- **Custom Metrics**: Business and technical metrics
- **Real-time Dashboards**: Performance and health visualization

#### Default Metrics:
```python
# HTTP Metrics
- requests_total (counter)
- request_duration_seconds (histogram)
- active_requests (gauge)

# Database Metrics
- db_connections_active (gauge)
- db_query_duration_seconds (histogram)

# Cache Metrics
- cache_hits_total (counter)
- cache_misses_total (counter)

# Business Metrics
- user_registrations_total (counter)
- api_keys_created_total (counter)

# System Metrics
- cpu_usage_percent (gauge)
- memory_usage_bytes (gauge)
- disk_usage_percent (gauge)
```

#### Health Checks:
```python
# Add custom health check
monitoring.add_health_check(
    name="payment_gateway",
    check_func=check_payment_gateway,
    timeout=10,
    critical=False
)

# Health check endpoint response
GET /health
{
    "status": "healthy",
    "checks": {
        "database": {"status": "healthy"},
        "redis": {"status": "healthy"},
        "disk_space": {"status": "healthy"}
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Alerting:
```python
# Add custom alert
monitoring.add_alert(
    name="high_error_rate",
    condition=lambda: error_rate > 0.05,
    message="Error rate exceeds 5%",
    severity=AlertSeverity.ERROR,
    actions=[send_slack_notification, page_on_call]
)
```

### 3. Deployment Automation ✅

#### A. Main Deployment Script (`scripts/deploy.sh`)

Features:
- **Multi-environment Support**: Development, staging, production
- **Automated Testing**: Run tests before deployment
- **Docker Image Building**: Build and push to registry
- **Database Migrations**: Automated migration execution
- **Kubernetes Deployment**: Helm-based deployments
- **Health Verification**: Post-deployment health checks
- **Rollback Support**: Automatic rollback on failure
- **Notifications**: Slack/email deployment notifications

Usage:
```bash
# Deploy to staging
./scripts/deploy.sh staging v1.2.3

# Deploy to production
./scripts/deploy.sh production v1.2.3

# Deploy with default version (latest)
./scripts/deploy.sh staging
```

#### B. Health Check Script (`scripts/health_check.py`)

Comprehensive health validation:
- API endpoint checks
- Database connectivity
- Redis connectivity
- System resource monitoring
- External service validation
- Performance metrics

Usage:
```bash
# Basic health check
python scripts/health_check.py

# Check specific environment
python scripts/health_check.py --api-url https://api.agencydark.com

# Output as JSON
python scripts/health_check.py --output json --output-file health.json
```

#### C. Backup Script (`scripts/backup.sh`)

Features:
- **Database Backups**: PostgreSQL with compression
- **Redis Backups**: RDB snapshots
- **Configuration Backups**: Environment files and configs
- **S3 Upload**: Automatic upload to S3
- **Retention Management**: Automatic cleanup of old backups
- **Backup Verification**: Integrity checks

Usage:
```bash
# Create backup
./scripts/backup.sh backup

# List backups
./scripts/backup.sh list

# Restore from backup
./scripts/backup.sh restore backup_file.sql.gz

# Cleanup old backups
./scripts/backup.sh cleanup
```

### 4. Production Configuration

#### Environment Variables:
```bash
# Application
APP_NAME=agency-dark
APP_ENV=production
DEBUG=false
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname
DB_POOL_SIZE=20
DB_POOL_RECYCLE=3600

# Redis
REDIS_URL=redis://:password@host:6379/0

# Monitoring
SENTRY_DSN=https://your-sentry-dsn
PROMETHEUS_PORT=9090
ENABLE_TRACING=true
OTLP_ENDPOINT=http://jaeger:4317

# Error Handling
ERROR_TRACKING=true
CIRCUIT_BREAKER_ENABLED=true

# Backups
BACKUP_DIR=/backups
BACKUP_RETENTION_DAYS=30
AWS_S3_BUCKET=agency-dark-backups
```

#### Docker Compose Production:
```yaml
version: '3.8'

services:
  backend:
    image: agency-dark-backend:latest
    environment:
      - APP_ENV=production
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

## Operational Procedures

### 1. Deployment Checklist

Before deployment:
- [ ] All tests passing
- [ ] Security scan completed
- [ ] Database migrations tested
- [ ] Load testing performed
- [ ] Rollback plan prepared
- [ ] Team notified

During deployment:
- [ ] Monitor error rates
- [ ] Check response times
- [ ] Verify health checks
- [ ] Monitor resource usage
- [ ] Check external services

After deployment:
- [ ] Run smoke tests
- [ ] Verify critical flows
- [ ] Check monitoring dashboards
- [ ] Update documentation
- [ ] Send completion notification

### 2. Monitoring Dashboard

Access monitoring endpoints:
- **Metrics**: `GET /metrics` (Prometheus format)
- **Health**: `GET /health` (JSON health status)
- **Dashboard**: `GET /admin/monitoring` (Web UI)

Key metrics to monitor:
1. **Response Time**: p50, p95, p99
2. **Error Rate**: 4xx, 5xx errors
3. **Throughput**: Requests per second
4. **Database**: Query time, connection pool
5. **Cache**: Hit rate, evictions
6. **Resources**: CPU, memory, disk

### 3. Incident Response

#### Severity Levels:
- **Critical**: Complete outage, data loss risk
- **High**: Major functionality impaired
- **Medium**: Minor functionality affected
- **Low**: Cosmetic issues, minor bugs

#### Response Steps:
1. **Acknowledge**: Confirm incident receipt
2. **Assess**: Determine severity and impact
3. **Communicate**: Notify stakeholders
4. **Investigate**: Check logs, metrics, traces
5. **Mitigate**: Apply temporary fixes
6. **Resolve**: Implement permanent solution
7. **Review**: Post-mortem analysis

#### Common Issues:

**High CPU Usage**:
```bash
# Check top processes
docker exec backend top

# Check slow queries
docker exec backend python -m core.monitoring.slow_query_analyzer

# Scale horizontally
kubectl scale deployment backend --replicas=5
```

**Database Connection Issues**:
```bash
# Check connection pool
curl http://localhost:8000/admin/monitoring/db-pool

# Reset connections
docker exec backend python -m core.database.reset_connections

# Increase pool size
kubectl set env deployment/backend DB_POOL_SIZE=50
```

**Memory Leaks**:
```bash
# Analyze memory usage
docker exec backend python -m memory_profiler main.py

# Force garbage collection
curl -X POST http://localhost:8000/admin/gc

# Restart with memory limit
docker restart backend
```

### 4. Backup and Recovery

#### Backup Schedule:
- **Database**: Daily at 2 AM UTC
- **Redis**: Every 6 hours
- **Media**: Weekly on Sunday
- **Configs**: On every change

#### Recovery Procedures:

**Database Recovery**:
```bash
# List available backups
./scripts/backup.sh list

# Restore specific backup
./scripts/backup.sh restore agency_dark_20240115_020000.sql.gz

# Verify restoration
python scripts/health_check.py --database-url $DATABASE_URL
```

**Point-in-Time Recovery**:
```bash
# Restore to specific time
pg_restore --clean --if-exists \
  --dbname=$DATABASE_URL \
  --jobs=4 \
  backup_file.dump

# Apply WAL logs to specific time
pg_wal_replay --target-time="2024-01-15 10:00:00"
```

### 5. Performance Optimization

#### Quick Wins:
1. **Enable caching**: Set `CACHE_ENABLED=true`
2. **Increase workers**: Scale to match CPU cores
3. **Enable compression**: Set `ENABLE_COMPRESSION=true`
4. **Use CDN**: Offload static assets
5. **Database indexes**: Run index analyzer

#### Performance Tuning:
```bash
# Analyze slow queries
docker exec backend python -m core.performance.analyze_queries

# Generate performance report
python scripts/performance_report.py --days 7

# Run load test
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

### 6. Security Procedures

#### Regular Tasks:
- **Weekly**: Security scan with Bandit
- **Monthly**: Dependency vulnerability check
- **Quarterly**: Penetration testing
- **Annually**: Security audit

#### Security Checklist:
```bash
# Run security scan
poetry run bandit -r . -f json -o security_report.json

# Check dependencies
poetry run safety check --json

# Audit API keys
python scripts/audit_api_keys.py --inactive-days 90

# Review access logs
python scripts/analyze_access_logs.py --suspicious
```

## Troubleshooting Guide

### Common Issues:

1. **Service Won't Start**
   - Check logs: `docker logs backend`
   - Verify environment variables
   - Check database connectivity
   - Verify Redis connection

2. **High Error Rate**
   - Check error details in Sentry
   - Review recent deployments
   - Check external service status
   - Verify rate limits

3. **Slow Response Times**
   - Check database query performance
   - Review cache hit rates
   - Check CPU/memory usage
   - Analyze request traces

4. **Memory Issues**
   - Review memory profiling
   - Check for memory leaks
   - Adjust worker processes
   - Enable memory limits

## Production Readiness Checklist

### Infrastructure:
- [x] Load balancer configured
- [x] Auto-scaling enabled
- [x] Health checks implemented
- [x] Monitoring configured
- [x] Logging centralized
- [x] Backups automated
- [x] SSL/TLS configured
- [x] CDN configured

### Application:
- [x] Error handling comprehensive
- [x] Rate limiting enabled
- [x] Security headers configured
- [x] Input validation strict
- [x] Authentication robust
- [x] API versioning implemented
- [x] Documentation complete
- [x] Performance optimized

### Operations:
- [x] Deployment automated
- [x] Rollback procedures tested
- [x] Monitoring alerts configured
- [x] On-call rotation setup
- [x] Runbooks documented
- [x] Disaster recovery plan
- [x] Security procedures defined
- [x] Compliance requirements met

## Support and Resources

### Documentation:
- API Documentation: `/docs`
- Architecture Guide: `ARCHITECTURE.md`
- Security Guide: `SECURITY_HARDENING_GUIDE.md`
- Performance Guide: `PERFORMANCE_OPTIMIZATION_GUIDE.md`

### Monitoring:
- Prometheus: `http://prometheus:9090`
- Grafana: `http://grafana:3000`
- Sentry: `https://sentry.io/organizations/agency-dark`
- Jaeger: `http://jaeger:16686`

### Contact:
- On-call: Use PagerDuty
- Security: security@agencydark.com
- Support: support@agencydark.com