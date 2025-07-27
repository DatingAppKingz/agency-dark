# Docker Volume Configuration

## Volume Structure

The application uses several Docker volumes for persistent data storage:

### 1. Database Volume (`postgres_data`)
- **Purpose**: PostgreSQL data persistence
- **Mount**: `/var/lib/postgresql/data`
- **Backup Strategy**: Daily automated backups to S3/external storage
- **Retention**: 30 days of backups

### 2. Redis Volume (`redis_data`)
- **Purpose**: Redis data persistence (AOF + RDB)
- **Mount**: `/data`
- **Backup Strategy**: Hourly RDB snapshots
- **Retention**: 7 days of snapshots

### 3. Application Logs (`./backend/logs`)
- **Purpose**: Application log files
- **Mount**: `/app/logs`
- **Files**:
  - `app.log` - General application logs (100MB max, 5 rotations)
  - `error.log` - Error logs only (50MB max, 5 rotations)
  - `access.log` - HTTP access logs
- **Retention**: 30 days

### 4. User Uploads (`./backend/uploads`)
- **Purpose**: User-uploaded files (images, videos, documents)
- **Mount**: `/app/uploads`
- **Structure**:
  ```
  uploads/
  ├── avatars/
  ├── content/
  ├── documents/
  └── temp/
  ```
- **Backup**: Sync to S3/CDN
- **Cleanup**: Temp files older than 24 hours

### 5. ML Models (`./backend/ml_models`)
- **Purpose**: Trained ML model storage
- **Mount**: `/app/ml_models`
- **Structure**:
  ```
  ml_models/
  ├── revenue_forecast/
  ├── churn_prediction/
  ├── content_optimization/
  └── fan_ltv/
  ```
- **Versioning**: Keep last 5 versions of each model

### 6. Caddy Volumes
- **Data**: `/data` - Caddy certificates and configuration
- **Config**: `/config` - Caddy runtime configuration

## Volume Management

### Creating Volumes
```bash
# Create named volumes
docker volume create agencydark_postgres_data
docker volume create agencydark_redis_data
docker volume create agencydark_caddy_data
docker volume create agencydark_caddy_config

# Create directories for bind mounts
mkdir -p ./backend/{logs,uploads,ml_models}
chmod 777 ./backend/{logs,uploads}  # Allow container write access
```

### Backup Commands
```bash
# Backup PostgreSQL
docker exec agencydark-db-prod pg_dump -U agencydark agencydark | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Backup Redis
docker exec agencydark-redis-prod redis-cli --pass $REDIS_PASSWORD BGSAVE
docker cp agencydark-redis-prod:/data/dump.rdb redis_backup_$(date +%Y%m%d_%H%M%S).rdb

# Backup uploads to S3
aws s3 sync ./backend/uploads s3://agencydark-backups/uploads/ --delete
```

### Restore Commands
```bash
# Restore PostgreSQL
gunzip -c backup_20240101_120000.sql.gz | docker exec -i agencydark-db-prod psql -U agencydark agencydark

# Restore Redis
docker cp redis_backup_20240101_120000.rdb agencydark-redis-prod:/data/dump.rdb
docker exec agencydark-redis-prod redis-cli --pass $REDIS_PASSWORD SHUTDOWN NOSAVE
docker restart agencydark-redis-prod

# Restore uploads from S3
aws s3 sync s3://agencydark-backups/uploads/ ./backend/uploads/
```

### Volume Inspection
```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect agencydark_postgres_data

# Check volume size
docker system df -v

# Clean unused volumes
docker volume prune -f
```

## Permissions

### File Ownership
- Container user: `appuser:appgroup` (1000:1000)
- Logs: `777` (world-writable for container access)
- Uploads: `777` (world-writable for file uploads)
- ML Models: `755` (read/execute for all, write for owner)

### Security Considerations
1. Use named volumes for sensitive data (database, redis)
2. Bind mounts only for logs and uploads that need host access
3. Regular backups to external storage
4. Encrypt backups before storing externally
5. Rotate logs to prevent disk exhaustion

## Monitoring

### Disk Usage Alerts
Set up alerts when:
- Any volume exceeds 80% capacity
- Log rotation fails
- Backup jobs fail
- Upload directory exceeds quota

### Health Checks
- Database volume: Check write permissions
- Redis volume: Verify AOF/RDB writes
- Upload volume: Test file creation/deletion
- Log volume: Verify rotation working