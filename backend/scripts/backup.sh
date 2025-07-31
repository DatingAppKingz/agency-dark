#!/bin/bash

# AgencyDark Backup Script
# This script performs automated backups of the database and media files

set -euo pipefail

# Load environment variables
if [ -f .env.production ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
fi

# Configuration
BACKUP_BASE_DIR="${BACKUP_DIR:-/opt/agencydark/backups}"
DB_NAME="${DB_NAME:-agencydark_prod}"
DB_USER="${DB_USER:-agencydark_user}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
S3_BUCKET="${S3_BACKUP_BUCKET:-agencydark-backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${BACKUP_BASE_DIR}/backup_${TIMESTAMP}.log"

# Create backup directories
mkdir -p "${BACKUP_BASE_DIR}/postgres"
mkdir -p "${BACKUP_BASE_DIR}/redis"
mkdir -p "${BACKUP_BASE_DIR}/media"
mkdir -p "${BACKUP_BASE_DIR}/logs"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check required commands
    for cmd in pg_dump redis-cli aws tar gzip; do
        if ! command -v $cmd &> /dev/null; then
            error_exit "$cmd is not installed"
        fi
    done
    
    # Check database connection
    PGPASSWORD=$DB_PASSWORD pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER || \
        error_exit "Cannot connect to PostgreSQL"
    
    # Check Redis connection
    redis-cli -a $REDIS_PASSWORD ping &> /dev/null || \
        error_exit "Cannot connect to Redis"
    
    # Check S3 access
    aws s3 ls s3://$S3_BUCKET &> /dev/null || \
        error_exit "Cannot access S3 bucket"
    
    log "All prerequisites met"
}

# Database backup
backup_postgres() {
    log "Starting PostgreSQL backup..."
    
    local backup_file="${BACKUP_BASE_DIR}/postgres/postgres_${DB_NAME}_${TIMESTAMP}.sql.gz"
    
    # Perform backup with custom format for faster restore
    PGPASSWORD=$DB_PASSWORD pg_dump \
        -h $DB_HOST \
        -p $DB_PORT \
        -U $DB_USER \
        -d $DB_NAME \
        --format=custom \
        --verbose \
        --no-owner \
        --no-privileges \
        --exclude-table-data='pg_*' \
        --exclude-table-data='information_schema.*' \
        | gzip -9 > "$backup_file"
    
    # Verify backup
    if [ ! -s "$backup_file" ]; then
        error_exit "PostgreSQL backup failed - empty file"
    fi
    
    # Get backup size
    local size=$(du -h "$backup_file" | cut -f1)
    log "PostgreSQL backup completed: $backup_file (${size})"
    
    # Upload to S3
    log "Uploading PostgreSQL backup to S3..."
    aws s3 cp "$backup_file" "s3://${S3_BUCKET}/postgres/" \
        --storage-class STANDARD_IA \
        --metadata "timestamp=${TIMESTAMP},type=postgres,database=${DB_NAME}"
    
    log "PostgreSQL backup uploaded successfully"
}

# Redis backup
backup_redis() {
    log "Starting Redis backup..."
    
    local backup_file="${BACKUP_BASE_DIR}/redis/redis_${TIMESTAMP}.rdb"
    
    # Trigger Redis BGSAVE
    redis-cli -a $REDIS_PASSWORD BGSAVE
    
    # Wait for backup to complete
    while [ $(redis-cli -a $REDIS_PASSWORD LASTSAVE) -eq $(redis-cli -a $REDIS_PASSWORD LASTSAVE) ]; do
        sleep 1
    done
    
    # Copy RDB file
    cp /var/lib/redis/dump.rdb "$backup_file"
    gzip -9 "$backup_file"
    backup_file="${backup_file}.gz"
    
    # Get backup size
    local size=$(du -h "$backup_file" | cut -f1)
    log "Redis backup completed: $backup_file (${size})"
    
    # Upload to S3
    log "Uploading Redis backup to S3..."
    aws s3 cp "$backup_file" "s3://${S3_BUCKET}/redis/" \
        --storage-class STANDARD_IA \
        --metadata "timestamp=${TIMESTAMP},type=redis"
    
    log "Redis backup uploaded successfully"
}

# Media files backup
backup_media() {
    log "Starting media files backup..."
    
    local media_dir="${UPLOAD_DIR:-/opt/agencydark/uploads}"
    local backup_file="${BACKUP_BASE_DIR}/media/media_${TIMESTAMP}.tar.gz"
    
    if [ -d "$media_dir" ] && [ "$(ls -A $media_dir)" ]; then
        # Create compressed archive
        tar -czf "$backup_file" -C "$(dirname $media_dir)" "$(basename $media_dir)"
        
        # Get backup size
        local size=$(du -h "$backup_file" | cut -f1)
        log "Media backup completed: $backup_file (${size})"
        
        # Upload to S3
        log "Uploading media backup to S3..."
        aws s3 cp "$backup_file" "s3://${S3_BUCKET}/media/" \
            --storage-class STANDARD_IA \
            --metadata "timestamp=${TIMESTAMP},type=media"
        
        log "Media backup uploaded successfully"
    else
        log "No media files to backup"
    fi
}

# Application config backup
backup_config() {
    log "Starting configuration backup..."
    
    local backup_file="${BACKUP_BASE_DIR}/config/config_${TIMESTAMP}.tar.gz"
    mkdir -p "${BACKUP_BASE_DIR}/config"
    
    # Create temporary directory for configs
    local temp_dir=$(mktemp -d)
    
    # Copy configuration files
    cp .env.production "$temp_dir/" 2>/dev/null || true
    cp -r alembic "$temp_dir/" 2>/dev/null || true
    cp docker-compose.prod.yml "$temp_dir/" 2>/dev/null || true
    cp nginx.conf "$temp_dir/" 2>/dev/null || true
    
    # Create archive
    tar -czf "$backup_file" -C "$temp_dir" .
    rm -rf "$temp_dir"
    
    # Upload to S3
    log "Uploading config backup to S3..."
    aws s3 cp "$backup_file" "s3://${S3_BUCKET}/config/" \
        --storage-class STANDARD \
        --server-side-encryption AES256 \
        --metadata "timestamp=${TIMESTAMP},type=config"
    
    log "Configuration backup uploaded successfully"
}

# Clean old backups
cleanup_old_backups() {
    log "Cleaning up old backups..."
    
    # Clean local backups older than 7 days
    find "$BACKUP_BASE_DIR" -type f -name "*.gz" -mtime +7 -delete
    
    # Clean S3 backups older than retention period
    for prefix in postgres redis media config; do
        aws s3api list-objects-v2 \
            --bucket "$S3_BUCKET" \
            --prefix "$prefix/" \
            --query "Contents[?LastModified<='$(date -d "-$RETENTION_DAYS days" -Iseconds)'].Key" \
            --output text | \
        while read -r key; do
            if [ ! -z "$key" ]; then
                log "Deleting old backup: $key"
                aws s3 rm "s3://${S3_BUCKET}/${key}"
            fi
        done
    done
    
    log "Cleanup completed"
}

# Send notification
send_notification() {
    local status=$1
    local message=$2
    
    # Send email notification (if configured)
    if [ ! -z "${SMTP_HOST:-}" ]; then
        echo "$message" | mail -s "AgencyDark Backup $status" "${BACKUP_NOTIFICATION_EMAIL:-admin@agencydark.com}"
    fi
    
    # Send to monitoring system
    if [ ! -z "${PROMETHEUS_PUSHGATEWAY:-}" ]; then
        cat <<EOF | curl --data-binary @- ${PROMETHEUS_PUSHGATEWAY}/metrics/job/backup
# TYPE backup_status gauge
backup_status{type="postgres"} $([ "$status" == "SUCCESS" ] && echo 1 || echo 0)
# TYPE backup_timestamp gauge
backup_timestamp $(date +%s)
EOF
    fi
}

# Main backup process
main() {
    log "=== Starting AgencyDark Backup ==="
    log "Timestamp: $TIMESTAMP"
    
    # Check prerequisites
    check_prerequisites
    
    # Perform backups
    backup_postgres
    backup_redis
    backup_media
    backup_config
    
    # Cleanup old backups
    cleanup_old_backups
    
    # Create backup manifest
    cat > "${BACKUP_BASE_DIR}/manifest_${TIMESTAMP}.json" <<EOF
{
    "timestamp": "${TIMESTAMP}",
    "date": "$(date -Iseconds)",
    "components": {
        "postgres": {
            "database": "${DB_NAME}",
            "size": "$(du -h ${BACKUP_BASE_DIR}/postgres/postgres_${DB_NAME}_${TIMESTAMP}.sql.gz | cut -f1)",
            "s3_path": "s3://${S3_BUCKET}/postgres/postgres_${DB_NAME}_${TIMESTAMP}.sql.gz"
        },
        "redis": {
            "size": "$(du -h ${BACKUP_BASE_DIR}/redis/redis_${TIMESTAMP}.rdb.gz | cut -f1)",
            "s3_path": "s3://${S3_BUCKET}/redis/redis_${TIMESTAMP}.rdb.gz"
        },
        "media": {
            "size": "$(du -h ${BACKUP_BASE_DIR}/media/media_${TIMESTAMP}.tar.gz 2>/dev/null | cut -f1 || echo 'N/A')",
            "s3_path": "s3://${S3_BUCKET}/media/media_${TIMESTAMP}.tar.gz"
        }
    },
    "retention_days": ${RETENTION_DAYS}
}
EOF
    
    # Upload manifest
    aws s3 cp "${BACKUP_BASE_DIR}/manifest_${TIMESTAMP}.json" "s3://${S3_BUCKET}/manifests/"
    
    log "=== Backup completed successfully ==="
    send_notification "SUCCESS" "Backup completed successfully at ${TIMESTAMP}"
}

# Error handler
trap 'error_exit "Backup failed at line $LINENO"' ERR

# Run main process
main

exit 0