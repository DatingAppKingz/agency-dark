# AgencyDark Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Environment Configuration](#environment-configuration)
6. [Database Setup](#database-setup)
7. [SSL/TLS Configuration](#ssltls-configuration)
8. [Monitoring](#monitoring)
9. [Backup & Recovery](#backup--recovery)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements
- CPU: 4+ cores recommended
- RAM: 8GB minimum, 16GB recommended
- Storage: 50GB minimum
- OS: Ubuntu 20.04+ or similar Linux distribution

### Software Requirements
- Docker 20.10+
- Docker Compose 2.0+
- Kubernetes 1.25+ (for K8s deployment)
- PostgreSQL 16+
- Redis 7+
- Python 3.11+

## Local Development

### 1. Clone the Repository
```bash
git clone https://github.com/agencydark/agencydark.git
cd agencydark
```

### 2. Set Up Environment
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Using Docker Compose
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 4. Manual Setup (without Docker)
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd backend
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start the application
uvicorn backend.main:app --reload
```

## Docker Deployment

### Building the Image
```bash
cd backend
docker build -t agencydark/backend:latest .
```

### Running with Docker
```bash
# Create network
docker network create agencydark

# Run PostgreSQL
docker run -d \
  --name postgres \
  --network agencydark \
  -e POSTGRES_USER=agencydark \
  -e POSTGRES_PASSWORD=secure_password \
  -e POSTGRES_DB=agencydark \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:16-alpine

# Run Redis
docker run -d \
  --name redis \
  --network agencydark \
  -v redis_data:/data \
  redis:7-alpine

# Run Backend
docker run -d \
  --name backend \
  --network agencydark \
  -p 8000:8000 \
  -e DATABASE_URL=postgresql://agencydark:secure_password@postgres:5432/agencydark \
  -e REDIS_URL=redis://redis:6379/0 \
  -e SECRET_KEY=your_secret_key \
  -v uploads:/app/uploads \
  agencydark/backend:latest
```

## Kubernetes Deployment

### 1. Create Namespace
```bash
kubectl apply -f k8s/namespace.yaml
```

### 2. Configure Secrets
```bash
# Edit k8s/secret.yaml with your values
kubectl apply -f k8s/secret.yaml
```

### 3. Deploy Services
```bash
# Deploy in order
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/ingress.yaml
```

### 4. Verify Deployment
```bash
kubectl get pods -n agencydark
kubectl get services -n agencydark
kubectl logs -n agencydark deployment/backend
```

### 5. Scale Application
```bash
# Manual scaling
kubectl scale deployment/backend -n agencydark --replicas=5

# Auto-scaling is configured in backend.yaml
```

## Environment Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/agencydark

# Redis
REDIS_URL=redis://host:6379/0

# Security
SECRET_KEY=your-secret-key-min-32-chars

# API Keys
INFLOW_API_KEY=your-inflow-api-key
ONLYFANS_API_KEY=your-onlyfans-api-key

# Email (Optional)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=noreply@agencydark.com
SMTP_PASSWORD=smtp-password

# Frontend
FRONTEND_URL=https://app.agencydark.com

# Environment
ENVIRONMENT=production
DEBUG=false
```

### Production Settings

Create `.env.production`:
```bash
# Performance
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=0
REDIS_TTL=3600

# Security
ALLOWED_ORIGINS=https://app.agencydark.com,https://admin.agencydark.com
RATE_LIMIT_CALLS=100
RATE_LIMIT_PERIOD=60

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
```

## Database Setup

### 1. PostgreSQL Installation
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql-16 postgresql-contrib

# Configure PostgreSQL
sudo -u postgres psql
CREATE USER agencydark WITH PASSWORD 'secure_password';
CREATE DATABASE agencydark OWNER agencydark;
GRANT ALL PRIVILEGES ON DATABASE agencydark TO agencydark;
```

### 2. Run Migrations
```bash
cd backend
alembic upgrade head
```

### 3. Create Initial Admin User
```bash
python scripts/create_admin.py \
  --email admin@agencydark.com \
  --username admin \
  --password secure_password
```

## SSL/TLS Configuration

### Using Let's Encrypt with Nginx
```nginx
server {
    listen 80;
    server_name api.agencydark.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.agencydark.com;
    
    ssl_certificate /etc/letsencrypt/live/api.agencydark.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.agencydark.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Obtain Certificate
```bash
sudo certbot --nginx -d api.agencydark.com
```

## Monitoring

### 1. Health Checks
```bash
# Application health
curl https://api.agencydark.com/health

# Database health
kubectl exec -n agencydark deployment/postgres -- pg_isready

# Redis health
kubectl exec -n agencydark deployment/redis -- redis-cli ping
```

### 2. Prometheus Metrics
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'agencydark'
    static_configs:
      - targets: ['api.agencydark.com:8000']
    metrics_path: '/metrics'
```

### 3. Logging
```bash
# View logs
kubectl logs -n agencydark deployment/backend -f

# Log aggregation with ELK
docker run -d \
  --name elasticsearch \
  -e "discovery.type=single-node" \
  elasticsearch:8.11.0
```

## Backup & Recovery

### Database Backup

#### Automated Daily Backup
```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/postgres"
DB_NAME="agencydark"

# Create backup
pg_dump -h localhost -U agencydark -d $DB_NAME > $BACKUP_DIR/backup_$DATE.sql

# Compress
gzip $BACKUP_DIR/backup_$DATE.sql

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR/backup_$DATE.sql.gz s3://agencydark-backups/

# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete
```

#### Restore from Backup
```bash
# Decompress
gunzip backup_20240101_120000.sql.gz

# Restore
psql -h localhost -U agencydark -d agencydark < backup_20240101_120000.sql
```

### Redis Backup
```bash
# Save snapshot
docker exec redis redis-cli BGSAVE

# Copy backup
docker cp redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

### Application Data
```bash
# Backup uploads
tar -czf uploads_backup_$(date +%Y%m%d).tar.gz /app/uploads/

# Restore uploads
tar -xzf uploads_backup_20240101.tar.gz -C /
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Failed
```bash
# Check PostgreSQL status
systemctl status postgresql

# Test connection
psql -h localhost -U agencydark -d agencydark

# Check logs
tail -f /var/log/postgresql/postgresql-*.log
```

#### 2. Redis Connection Failed
```bash
# Check Redis status
redis-cli ping

# Check Redis logs
docker logs redis
```

#### 3. Migration Errors
```bash
# Check current version
alembic current

# Downgrade if needed
alembic downgrade -1

# Re-run migration
alembic upgrade head
```

#### 4. Permission Errors
```bash
# Fix upload directory permissions
chmod 755 /app/uploads
chown -R appuser:appuser /app/uploads
```

### Performance Tuning

#### PostgreSQL
```sql
-- postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 4MB
max_connections = 200
```

#### Redis
```bash
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

#### Application
```python
# Increase workers
uvicorn backend.main:app --workers 8

# Enable response compression
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### Debugging

#### Enable Debug Mode
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

#### View Detailed Logs
```bash
# Application logs
tail -f logs/app.log

# SQL queries
export LOG_SQL=true
```

## Security Checklist

- [ ] Change all default passwords
- [ ] Enable firewall (ufw/iptables)
- [ ] Configure fail2ban
- [ ] Set up SSL/TLS certificates
- [ ] Disable root SSH access
- [ ] Enable audit logging
- [ ] Regular security updates
- [ ] Implement backup encryption
- [ ] Set up monitoring alerts
- [ ] Review security headers

## Support

For deployment assistance:
- Documentation: https://docs.agencydark.com
- Issues: https://github.com/agencydark/agencydark/issues
- Email: support@agencydark.com