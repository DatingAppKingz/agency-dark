# DevOps & Deployment Guide - Backend Polish 9

## Overview

This guide covers the complete DevOps setup for Agency Dark backend, including Docker configuration, container orchestration, and deployment strategies.

## Completed Components

### 1. Docker Configuration ✅

#### Production Docker Setup
- **Multi-stage Dockerfile**: Optimized for minimal image size and security
  - Builder stage: Compiles dependencies
  - Runtime stage: Runs with non-root user
  - Health checks included
  - Security hardening applied

#### Development Docker Setup
- **Dockerfile.dev**: Development environment with hot reload
  - Includes debugging tools
  - Development dependencies
  - Volume mounts for code changes

#### Docker Compose Configurations
- **docker-compose.yml**: Production stack
  - PostgreSQL 15
  - Redis 7
  - RabbitMQ
  - Nginx reverse proxy
  - Celery workers and beat
  - Health checks for all services

- **docker-compose.dev.yml**: Development stack
  - Additional tools: PgAdmin, Redis Commander, Mailhog
  - Volume mounts for hot reload
  - Debug ports exposed

### 2. Environment Configuration ✅

#### Enhanced .env.example
Complete environment variable template including:
- Database configuration
- Redis and RabbitMQ settings
- Security keys and algorithms
- External API configurations
- Feature flags
- Rate limiting settings
- Storage options (local/S3)
- Monitoring integration

### 3. Nginx Configuration ✅

#### Production-Ready Nginx Setup
- **nginx.conf**: Main configuration
  - Worker process optimization
  - Gzip compression
  - Security headers
  - Rate limiting zones

- **conf.d/default.conf**: Site configuration
  - API routing with rate limiting
  - WebSocket support
  - Static file serving
  - SSL configuration template

### 4. Automation Tools ✅

#### Makefile.docker
Comprehensive Docker commands:
```bash
# Development
make -f Makefile.docker dev-up      # Start dev environment
make -f Makefile.docker dev-shell   # Open shell
make -f Makefile.docker dev-logs    # View logs

# Production
make -f Makefile.docker prod-deploy # Full deployment
make -f Makefile.docker prod-logs   # Production logs

# Database
make -f Makefile.docker docker-db-backup   # Backup database
make -f Makefile.docker docker-db-migrate  # Run migrations

# Monitoring
make -f Makefile.docker docker-health      # Health checks
make -f Makefile.docker docker-stats       # Container stats
```

## Quick Start

### Development Environment

1. Copy environment file:
```bash
cp .env.example .env
```

2. Start development stack:
```bash
make -f Makefile.docker dev-up
```

3. Run migrations:
```bash
make -f Makefile.docker docker-db-migrate
```

4. Access services:
- API: http://localhost:8000
- PgAdmin: http://localhost:5050
- Redis Commander: http://localhost:8081
- Mailhog: http://localhost:8025

### Production Deployment

1. Build production images:
```bash
make -f Makefile.docker prod-build
```

2. Deploy with migrations:
```bash
make -f Makefile.docker prod-deploy
```

3. Monitor deployment:
```bash
make -f Makefile.docker prod-logs
```

## Container Architecture

```
┌─────────────────┐
│     Nginx       │ (Port 80/443)
│  Reverse Proxy  │
└────────┬────────┘
         │
┌────────▼────────┐
│   Backend API   │ (Port 8000)
│    (Gunicorn)   │
└────────┬────────┘
         │
    ┌────┴────┬─────────┬─────────┐
    │         │         │         │
┌───▼──┐ ┌───▼──┐ ┌────▼───┐ ┌───▼──┐
│Postgres│ │Redis │ │RabbitMQ│ │Celery│
│  DB    │ │Cache │ │ Queue  │ │Worker│
└────────┘ └──────┘ └────────┘ └──────┘
```

## Security Features

1. **Non-root containers**: All services run as non-root users
2. **Network isolation**: Services communicate via internal network
3. **Secret management**: Environment variables for sensitive data
4. **Health checks**: All services have health check endpoints
5. **Rate limiting**: Nginx-level rate limiting for API endpoints

## Monitoring & Observability

### Health Checks
- Backend: `/health` endpoint
- PostgreSQL: `pg_isready`
- Redis: `redis-cli ping`
- RabbitMQ: `rabbitmq-diagnostics ping`

### Logs
- Centralized logging via Docker
- JSON formatted logs for parsing
- Log levels configurable via environment

### Metrics (Ready for Integration)
- Prometheus endpoint ready
- OpenTelemetry support
- Custom metrics for business logic

## Backup & Recovery

### Database Backup
```bash
# Manual backup
make -f Makefile.docker docker-db-backup

# Restore from backup
make -f Makefile.docker docker-db-restore FILE=backup_20240115_120000.sql
```

### Automated Backups
Configure cron job:
```bash
0 2 * * * cd /path/to/project && make -f Makefile.docker docker-db-backup
```

## Scaling Considerations

### Horizontal Scaling
- Backend: Increase `WORKERS` environment variable
- Celery: Scale worker containers
- Database: Configure read replicas

### Vertical Scaling
- Adjust Docker resource limits
- Configure PostgreSQL shared_buffers
- Tune Redis maxmemory

## Troubleshooting

### Common Issues

1. **Port conflicts**
   ```bash
   # Check ports
   netstat -tlnp | grep -E '8000|5432|6379'
   ```

2. **Container health**
   ```bash
   make -f Makefile.docker docker-health
   ```

3. **Database connection**
   ```bash
   make -f Makefile.docker docker-db-shell
   ```

4. **Clear everything**
   ```bash
   make -f Makefile.docker docker-clean-all
   ```

## Next Steps

### Kubernetes Deployment (In Progress)
- Helm charts for easy deployment
- ConfigMaps and Secrets
- Horizontal Pod Autoscaling
- Ingress configuration

### CI/CD Pipeline (Pending)
- GitHub Actions workflow
- Automated testing
- Docker image building
- Deployment automation

## Production Checklist

- [ ] Update all passwords in .env
- [ ] Configure SSL certificates
- [ ] Set up monitoring alerts
- [ ] Configure backup automation
- [ ] Review security headers
- [ ] Set appropriate rate limits
- [ ] Configure log aggregation
- [ ] Set up health check monitoring
- [ ] Review and adjust resource limits
- [ ] Document deployment procedures