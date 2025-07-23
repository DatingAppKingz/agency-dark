#!/bin/bash

# AgencyDark Backup Script
# This script performs automated backups of the database and application data

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-agencydark}"
DB_USER="${DB_USER:-agencydark}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
UPLOAD_DIR="${UPLOAD_DIR:-/app/uploads}"
S3_BUCKET="${S3_BUCKET:-agencydark-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "Starting AgencyDark backup at $(date)"

# Function to upload to S3
upload_to_s3() {
    local file=$1
    if [ -n "$AWS_ACCESS_KEY_ID" ]; then
        echo "Uploading $file to S3..."
        aws s3 cp "$file" "s3://$S3_BUCKET/$(basename "$file")"
    fi
}

# 1. Database Backup
echo "Backing up PostgreSQL database..."
DB_BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"

PGPASSWORD=$DB_PASSWORD pg_dump \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --verbose \
    --no-owner \
    --no-acl \
    > "$DB_BACKUP_FILE"

# Compress database backup
gzip "$DB_BACKUP_FILE"
DB_BACKUP_FILE="$DB_BACKUP_FILE.gz"

echo "Database backup completed: $DB_BACKUP_FILE"
upload_to_s3 "$DB_BACKUP_FILE"

# 2. Redis Backup
echo "Backing up Redis data..."
REDIS_BACKUP_FILE="$BACKUP_DIR/redis_backup_$TIMESTAMP.rdb"

# Trigger Redis save
redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" BGSAVE

# Wait for save to complete
while [ $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" LASTSAVE) -eq $(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" LASTSAVE) ]; do
    sleep 1
done

# Copy Redis dump file
if [ -f "/var/lib/redis/dump.rdb" ]; then
    cp "/var/lib/redis/dump.rdb" "$REDIS_BACKUP_FILE"
elif [ -f "/data/dump.rdb" ]; then
    cp "/data/dump.rdb" "$REDIS_BACKUP_FILE"
fi

echo "Redis backup completed: $REDIS_BACKUP_FILE"
upload_to_s3 "$REDIS_BACKUP_FILE"

# 3. Upload Directory Backup
echo "Backing up upload directory..."
UPLOAD_BACKUP_FILE="$BACKUP_DIR/uploads_backup_$TIMESTAMP.tar.gz"

tar -czf "$UPLOAD_BACKUP_FILE" -C "$(dirname "$UPLOAD_DIR")" "$(basename "$UPLOAD_DIR")"

echo "Upload directory backup completed: $UPLOAD_BACKUP_FILE"
upload_to_s3 "$UPLOAD_BACKUP_FILE"

# 4. Configuration Backup
echo "Backing up configuration..."
CONFIG_BACKUP_FILE="$BACKUP_DIR/config_backup_$TIMESTAMP.tar.gz"

# Backup important configuration files
tar -czf "$CONFIG_BACKUP_FILE" \
    /app/.env \
    /app/alembic.ini \
    /app/backend/alembic/versions/ \
    2>/dev/null || true

echo "Configuration backup completed: $CONFIG_BACKUP_FILE"
upload_to_s3 "$CONFIG_BACKUP_FILE"

# 5. Create backup manifest
MANIFEST_FILE="$BACKUP_DIR/manifest_$TIMESTAMP.json"
cat > "$MANIFEST_FILE" <<EOF
{
    "timestamp": "$TIMESTAMP",
    "date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "backups": {
        "database": "$(basename "$DB_BACKUP_FILE")",
        "redis": "$(basename "$REDIS_BACKUP_FILE")",
        "uploads": "$(basename "$UPLOAD_BACKUP_FILE")",
        "config": "$(basename "$CONFIG_BACKUP_FILE")"
    },
    "environment": {
        "db_host": "$DB_HOST",
        "db_name": "$DB_NAME",
        "app_version": "$(git describe --tags --always 2>/dev/null || echo 'unknown')"
    }
}
EOF

upload_to_s3 "$MANIFEST_FILE"

# 6. Cleanup old backups
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -name "*.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.rdb" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.json" -mtime +$RETENTION_DAYS -delete

# Cleanup S3 (if configured)
if [ -n "$AWS_ACCESS_KEY_ID" ]; then
    echo "Cleaning up old S3 backups..."
    aws s3 ls "s3://$S3_BUCKET/" | while read -r line; do
        createDate=$(echo "$line" | awk '{print $1" "$2}')
        createDate=$(date -d "$createDate" +%s)
        olderThan=$(date -d "$RETENTION_DAYS days ago" +%s)
        if [[ $createDate -lt $olderThan ]]; then
            fileName=$(echo "$line" | awk '{print $4}')
            if [ -n "$fileName" ]; then
                aws s3 rm "s3://$S3_BUCKET/$fileName"
            fi
        fi
    done
fi

echo "Backup completed successfully at $(date)"

# Send notification (optional)
if [ -n "$SLACK_WEBHOOK_URL" ]; then
    curl -X POST "$SLACK_WEBHOOK_URL" \
        -H 'Content-Type: application/json' \
        -d "{\"text\":\"AgencyDark backup completed successfully at $(date)\"}"
fi