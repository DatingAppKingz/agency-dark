#!/bin/bash

# AgencyDark Restore Script
# This script restores the application from backup files

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

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}AgencyDark Restore Utility${NC}"
echo "================================"

# Function to list available backups
list_backups() {
    echo -e "\n${GREEN}Available backups:${NC}"
    
    if [ -n "$AWS_ACCESS_KEY_ID" ]; then
        echo -e "\n${YELLOW}S3 Backups:${NC}"
        aws s3 ls "s3://$S3_BUCKET/" | grep manifest | sort -r | head -20
    fi
    
    echo -e "\n${YELLOW}Local Backups:${NC}"
    ls -la "$BACKUP_DIR"/manifest_*.json 2>/dev/null | sort -r | head -20 || echo "No local backups found"
}

# Function to download from S3
download_from_s3() {
    local file=$1
    local local_path="$BACKUP_DIR/$file"
    
    if [ ! -f "$local_path" ] && [ -n "$AWS_ACCESS_KEY_ID" ]; then
        echo "Downloading $file from S3..."
        aws s3 cp "s3://$S3_BUCKET/$file" "$local_path"
    fi
}

# Function to restore database
restore_database() {
    local backup_file=$1
    
    echo -e "\n${YELLOW}Restoring database from $backup_file...${NC}"
    
    # Check if file exists
    if [ ! -f "$backup_file" ]; then
        echo -e "${RED}Database backup file not found!${NC}"
        return 1
    fi
    
    # Create restore script
    cat > /tmp/restore_db.sql <<EOF
-- Terminate existing connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();

-- Drop and recreate database
DROP DATABASE IF EXISTS ${DB_NAME}_old;
ALTER DATABASE $DB_NAME RENAME TO ${DB_NAME}_old;
CREATE DATABASE $DB_NAME OWNER $DB_USER;
EOF
    
    # Execute restore script
    PGPASSWORD=$DB_PASSWORD psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d postgres \
        -f /tmp/restore_db.sql
    
    # Restore backup
    gunzip -c "$backup_file" | PGPASSWORD=$DB_PASSWORD psql \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME"
    
    echo -e "${GREEN}Database restored successfully!${NC}"
}

# Function to restore Redis
restore_redis() {
    local backup_file=$1
    
    echo -e "\n${YELLOW}Restoring Redis from $backup_file...${NC}"
    
    # Check if file exists
    if [ ! -f "$backup_file" ]; then
        echo -e "${RED}Redis backup file not found!${NC}"
        return 1
    fi
    
    # Stop Redis writes
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" CONFIG SET stop-writes-on-bgsave-error no
    
    # Clear existing data
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" FLUSHALL
    
    # Copy backup file
    if [ -d "/var/lib/redis" ]; then
        cp "$backup_file" "/var/lib/redis/dump.rdb"
    elif [ -d "/data" ]; then
        cp "$backup_file" "/data/dump.rdb"
    fi
    
    # Restart Redis to load the backup
    if command -v systemctl &> /dev/null; then
        sudo systemctl restart redis
    elif command -v service &> /dev/null; then
        sudo service redis restart
    else
        echo -e "${YELLOW}Please restart Redis manually to complete restore${NC}"
    fi
    
    echo -e "${GREEN}Redis restored successfully!${NC}"
}

# Function to restore uploads
restore_uploads() {
    local backup_file=$1
    
    echo -e "\n${YELLOW}Restoring uploads from $backup_file...${NC}"
    
    # Check if file exists
    if [ ! -f "$backup_file" ]; then
        echo -e "${RED}Uploads backup file not found!${NC}"
        return 1
    fi
    
    # Backup current uploads
    if [ -d "$UPLOAD_DIR" ]; then
        mv "$UPLOAD_DIR" "${UPLOAD_DIR}_old_$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Extract backup
    tar -xzf "$backup_file" -C "$(dirname "$UPLOAD_DIR")"
    
    echo -e "${GREEN}Uploads restored successfully!${NC}"
}

# Main restore process
main() {
    # Check if backup timestamp provided
    if [ -z "$1" ]; then
        list_backups
        echo -e "\n${YELLOW}Usage: $0 <backup_timestamp> [component]${NC}"
        echo "Example: $0 20240101_120000"
        echo "Example: $0 20240101_120000 database"
        echo -e "\nComponents: all, database, redis, uploads, config"
        exit 1
    fi
    
    TIMESTAMP=$1
    COMPONENT=${2:-all}
    
    # Download manifest
    MANIFEST_FILE="$BACKUP_DIR/manifest_$TIMESTAMP.json"
    download_from_s3 "manifest_$TIMESTAMP.json"
    
    if [ ! -f "$MANIFEST_FILE" ]; then
        echo -e "${RED}Manifest file not found for timestamp: $TIMESTAMP${NC}"
        exit 1
    fi
    
    # Parse manifest
    DB_BACKUP=$(jq -r '.backups.database' "$MANIFEST_FILE")
    REDIS_BACKUP=$(jq -r '.backups.redis' "$MANIFEST_FILE")
    UPLOAD_BACKUP=$(jq -r '.backups.uploads' "$MANIFEST_FILE")
    CONFIG_BACKUP=$(jq -r '.backups.config' "$MANIFEST_FILE")
    
    echo -e "\n${GREEN}Restore Summary:${NC}"
    echo "Timestamp: $TIMESTAMP"
    echo "Database: $DB_BACKUP"
    echo "Redis: $REDIS_BACKUP"
    echo "Uploads: $UPLOAD_BACKUP"
    echo "Config: $CONFIG_BACKUP"
    
    # Confirm restore
    echo -e "\n${YELLOW}WARNING: This will overwrite existing data!${NC}"
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        echo "Restore cancelled."
        exit 0
    fi
    
    # Download backup files
    if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "database" ]; then
        download_from_s3 "$DB_BACKUP"
    fi
    if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "redis" ]; then
        download_from_s3 "$REDIS_BACKUP"
    fi
    if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "uploads" ]; then
        download_from_s3 "$UPLOAD_BACKUP"
    fi
    if [ "$COMPONENT" = "all" ] || [ "$COMPONENT" = "config" ]; then
        download_from_s3 "$CONFIG_BACKUP"
    fi
    
    # Perform restore
    case "$COMPONENT" in
        all)
            restore_database "$BACKUP_DIR/$DB_BACKUP"
            restore_redis "$BACKUP_DIR/$REDIS_BACKUP"
            restore_uploads "$BACKUP_DIR/$UPLOAD_BACKUP"
            ;;
        database)
            restore_database "$BACKUP_DIR/$DB_BACKUP"
            ;;
        redis)
            restore_redis "$BACKUP_DIR/$REDIS_BACKUP"
            ;;
        uploads)
            restore_uploads "$BACKUP_DIR/$UPLOAD_BACKUP"
            ;;
        config)
            echo -e "${YELLOW}Extracting configuration backup...${NC}"
            tar -xzf "$BACKUP_DIR/$CONFIG_BACKUP" -C /
            echo -e "${GREEN}Configuration restored!${NC}"
            ;;
        *)
            echo -e "${RED}Unknown component: $COMPONENT${NC}"
            exit 1
            ;;
    esac
    
    echo -e "\n${GREEN}Restore completed successfully!${NC}"
    
    # Post-restore tasks
    echo -e "\n${YELLOW}Post-restore tasks:${NC}"
    echo "1. Restart the application"
    echo "2. Run database migrations if needed: alembic upgrade head"
    echo "3. Clear application caches"
    echo "4. Verify data integrity"
}

# Run main function
main "$@"