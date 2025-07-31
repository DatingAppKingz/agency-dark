# AgencyDark Backend Deployment Guide

This guide covers the complete deployment process for the AgencyDark backend system.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Production Environment Setup](#production-environment-setup)
3. [Database Setup](#database-setup)
4. [Application Configuration](#application-configuration)
5. [Docker Deployment](#docker-deployment)
6. [Manual Deployment](#manual-deployment)
7. [SSL/TLS Configuration](#ssltls-configuration)
8. [Monitoring Setup](#monitoring-setup)
9. [Backup and Recovery](#backup-and-recovery)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- Ubuntu 20.04+ or CentOS 8+ (recommended)
- 4GB RAM minimum (8GB recommended)
- 20GB disk space minimum
- Python 3.11+
- PostgreSQL 14+
- Redis 6+
- Docker & Docker Compose (for containerized deployment)
- Nginx (for reverse proxy)

### Required Services
- PostgreSQL database
- Redis server
- SMTP server (for email notifications)
- S3-compatible storage (for media files)

## Production Environment Setup

### 1. Update System
```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip nginx postgresql redis-server

# CentOS/RHEL
sudo yum update -y
sudo yum install -y python3.11 python3.11-venv python3-pip nginx postgresql redis
```

### 2. Create Application User
```bash
sudo useradd -m -s /bin/bash agencydark
sudo mkdir -p /opt/agencydark
sudo chown agencydark:agencydark /opt/agencydark
```

### 3. Clone Repository
```bash
sudo su - agencydark
cd /opt/agencydark
git clone https://github.com/yourusername/agency-dark.git
cd agency-dark/backend
```

## Database Setup

### 1. PostgreSQL Configuration
```bash
# Create database and user
sudo -u postgres psql
```

```sql
CREATE DATABASE agencydark_prod;
CREATE USER agencydark_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE agencydark_prod TO agencydark_user;

-- Enable required extensions
\c agencydark_prod
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
```

### 2. Configure PostgreSQL for Production
Edit `/etc/postgresql/14/main/postgresql.conf`:
```ini
# Connection settings
max_connections = 200
shared_buffers = 256MB

# Performance
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200

# Logging
log_statement = 'all'
log_duration = on
log_min_duration_statement = 100ms
```

### 3. Run Database Migrations
```bash
cd /opt/agencydark/agency-dark/backend
source venv/bin/activate
alembic upgrade head
```

## Application Configuration

### 1. Environment Variables
Create `/opt/agencydark/agency-dark/backend/.env.production`:
```env
# Application
ENVIRONMENT=production
APP_NAME=AgencyDark
SECRET_KEY=your-very-secure-secret-key-generate-with-openssl
API_V1_STR=/api/v1

# Database
DATABASE_URL=postgresql+asyncpg://agencydark_user:your_secure_password@localhost/agencydark_prod
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your_redis_password

# Security
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256
BCRYPT_ROUNDS=12

# CORS
CORS_ORIGINS=["https://app.agencydark.com","https://www.agencydark.com"]

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=notifications@agencydark.com
SMTP_PASSWORD=your_smtp_password
EMAILS_FROM_EMAIL=notifications@agencydark.com
EMAILS_FROM_NAME=AgencyDark

# Storage
S3_BUCKET_NAME=agencydark-media
S3_ACCESS_KEY_ID=your_s3_access_key
S3_SECRET_ACCESS_KEY=your_s3_secret_key
S3_REGION=us-east-1
S3_ENDPOINT_URL=https://s3.amazonaws.com

# Monitoring
SENTRY_DSN=your_sentry_dsn
PROMETHEUS_ENABLED=true

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60

# OnlyFans Integration
ONLYFANS_API_BASE_URL=https://onlyfans.com/api2/v2
ONLYFANS_WEBHOOK_SECRET=your_webhook_secret
```

### 2. Generate Secret Keys
```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate database password
openssl rand -base64 32
```

## Docker Deployment (Recommended)

### 1. Build Production Image
Create `Dockerfile.prod`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Run with gunicorn
CMD ["gunicorn", "main_with_auth:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000"]
```

### 2. Docker Compose Production
Create `docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: agencydark_backend
    environment:
      - ENVIRONMENT=production
    env_file:
      - ./backend/.env.production
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:14-alpine
    container_name: agencydark_postgres
    environment:
      POSTGRES_DB: agencydark_prod
      POSTGRES_USER: agencydark_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres/postgresql.conf:/etc/postgresql/postgresql.conf
    ports:
      - "127.0.0.1:5432:5432"
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agencydark_user"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: agencydark_redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  celery:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: agencydark_celery
    command: celery -A core.celery_app worker -l info
    env_file:
      - ./backend/.env.production
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: agencydark_celery_beat
    command: celery -A core.celery_app beat -l info
    env_file:
      - ./backend/.env.production
    depends_on:
      - redis
      - postgres
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### 3. Deploy with Docker
```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d --build

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

## Manual Deployment

### 1. Python Virtual Environment
```bash
cd /opt/agencydark/agency-dark/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Systemd Service
Create `/etc/systemd/system/agencydark.service`:
```ini
[Unit]
Description=AgencyDark Backend
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=agencydark
Group=agencydark
WorkingDirectory=/opt/agencydark/agency-dark/backend
Environment="PATH=/opt/agencydark/agency-dark/backend/venv/bin"
ExecStart=/opt/agencydark/agency-dark/backend/venv/bin/gunicorn main_with_auth:app \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    -b 0.0.0.0:8000 \
    --access-logfile /var/log/agencydark/access.log \
    --error-logfile /var/log/agencydark/error.log \
    --timeout 120

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 3. Celery Services
Create `/etc/systemd/system/agencydark-celery.service`:
```ini
[Unit]
Description=AgencyDark Celery Worker
After=network.target postgresql.service redis.service

[Service]
Type=forking
User=agencydark
Group=agencydark
WorkingDirectory=/opt/agencydark/agency-dark/backend
Environment="PATH=/opt/agencydark/agency-dark/backend/venv/bin"
ExecStart=/opt/agencydark/agency-dark/backend/venv/bin/celery -A core.celery_app worker -l info --detach

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. Start Services
```bash
# Create log directory
sudo mkdir -p /var/log/agencydark
sudo chown agencydark:agencydark /var/log/agencydark

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable agencydark agencydark-celery
sudo systemctl start agencydark agencydark-celery

# Check status
sudo systemctl status agencydark
```

## SSL/TLS Configuration

### 1. Nginx Configuration
Create `/etc/nginx/sites-available/agencydark`:
```nginx
upstream agencydark_backend {
    server 127.0.0.1:8000;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name api.agencydark.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.agencydark.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.agencydark.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.agencydark.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # API endpoints
    location / {
        proxy_pass http://agencydark_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # WebSocket support
    location /api/v1/ws/ {
        proxy_pass http://agencydark_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket timeouts
        proxy_read_timeout 86400;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://agencydark_backend/health;
        access_log off;
    }

    # Static files (if any)
    location /static/ {
        alias /opt/agencydark/agency-dark/backend/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

### 2. Install SSL Certificate
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d api.agencydark.com

# Enable site
sudo ln -s /etc/nginx/sites-available/agencydark /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Monitoring Setup

### 1. Prometheus Configuration
Create `/opt/agencydark/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'agencydark_backend'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/monitoring/metrics'
    bearer_token: 'your_monitoring_api_key'

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']

  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
```

### 2. Grafana Dashboards
Import these dashboard IDs in Grafana:
- PostgreSQL: 9628
- Redis: 763
- Node Exporter: 1860
- Custom AgencyDark dashboard (create from metrics)

### 3. Alerting Rules
Create `/opt/agencydark/alerts.yml`:
```yaml
groups:
  - name: agencydark_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: High error rate detected
          description: "Error rate is {{ $value }} errors per second"

      - alert: DatabaseConnectionFailure
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: PostgreSQL is down
          description: "Cannot connect to PostgreSQL database"

      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High memory usage
          description: "Memory usage is above 90%"
```

## Backup and Recovery

### 1. Database Backup Script
Create `/opt/agencydark/scripts/backup.sh`:
```bash
#!/bin/bash
set -e

# Configuration
BACKUP_DIR="/opt/agencydark/backups"
DB_NAME="agencydark_prod"
DB_USER="agencydark_user"
S3_BUCKET="agencydark-backups"
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Generate filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/agencydark_backup_$TIMESTAMP.sql.gz"

# Perform backup
echo "Starting backup..."
PGPASSWORD=$DB_PASSWORD pg_dump -h localhost -U $DB_USER -d $DB_NAME | gzip > $BACKUP_FILE

# Upload to S3
echo "Uploading to S3..."
aws s3 cp $BACKUP_FILE s3://$S3_BUCKET/postgres/

# Clean old local backups
echo "Cleaning old backups..."
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete

# Clean old S3 backups
aws s3 ls s3://$S3_BUCKET/postgres/ | while read -r line;
do
  createDate=`echo $line|awk {'print $1" "$2'}`
  createDate=`date -d"$createDate" +%s`
  olderThan=`date -d"-$RETENTION_DAYS days" +%s`
  if [[ $createDate -lt $olderThan ]]
  then
    fileName=`echo $line|awk {'print $4'}`
    if [[ $fileName != "" ]]
    then
      aws s3 rm s3://$S3_BUCKET/postgres/$fileName
    fi
  fi
done

echo "Backup completed successfully!"
```

### 2. Automated Backups
Add to crontab:
```bash
# Daily backups at 3 AM
0 3 * * * /opt/agencydark/scripts/backup.sh >> /var/log/agencydark/backup.log 2>&1
```

### 3. Recovery Procedure
```bash
# Download backup from S3
aws s3 cp s3://agencydark-backups/postgres/agencydark_backup_20231125_030000.sql.gz .

# Restore database
gunzip -c agencydark_backup_20231125_030000.sql.gz | psql -h localhost -U agencydark_user -d agencydark_prod
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check PostgreSQL is running: `sudo systemctl status postgresql`
   - Verify credentials in `.env.production`
   - Check PostgreSQL logs: `sudo tail -f /var/log/postgresql/postgresql-14-main.log`

2. **Redis Connection Errors**
   - Check Redis is running: `sudo systemctl status redis`
   - Verify Redis password: `redis-cli -a your_password ping`

3. **High Memory Usage**
   - Check for memory leaks: `ps aux | grep python`
   - Restart services: `sudo systemctl restart agencydark`
   - Review connection pool settings

4. **Slow API Response**
   - Check database query performance
   - Review Nginx access logs
   - Enable query profiling

### Log Locations
- Application logs: `/var/log/agencydark/`
- Nginx logs: `/var/log/nginx/`
- PostgreSQL logs: `/var/log/postgresql/`
- System logs: `journalctl -u agencydark`

### Performance Tuning

1. **Database Optimization**
   ```sql
   -- Update statistics
   ANALYZE;
   
   -- Find slow queries
   SELECT query, calls, mean_exec_time
   FROM pg_stat_statements
   WHERE mean_exec_time > 100
   ORDER BY mean_exec_time DESC;
   ```

2. **Application Optimization**
   - Increase worker processes
   - Enable connection pooling
   - Use Redis caching effectively

## Security Checklist

- [ ] Change all default passwords
- [ ] Enable firewall (ufw/firewalld)
- [ ] Configure fail2ban
- [ ] Set up SSL/TLS certificates
- [ ] Enable audit logging
- [ ] Regular security updates
- [ ] Implement rate limiting
- [ ] Configure CORS properly
- [ ] Enable CSRF protection
- [ ] Secure file uploads
- [ ] Regular security scans

## Contact & Support

For deployment support:
- Documentation: https://docs.agencydark.com
- Email: support@agencydark.com
- Emergency: +1-XXX-XXX-XXXX