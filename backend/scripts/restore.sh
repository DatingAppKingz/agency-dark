#!/bin/bash

# AgencyDark Recovery Script
# This script performs restoration of database and media files from backups

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
TEMP_DIR="/tmp/agencydark_restore_$$"
LOG_FILE="${BACKUP_BASE_DIR}/restore_$(date +%Y%m%d_%H%M%S).log"

# Create directories
mkdir -p "${BACKUP_BASE_DIR}/logs"
mkdir -p "$TEMP_DIR"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR: $1"
    rm -rf "$TEMP_DIR"
    exit 1
}

# Cleanup on exit
trap 'rm -rf "$TEMP_DIR"' EXIT

# List available backups
list_backups() {
    log "Listing available backups from S3..."
    
    echo -e "\n=== PostgreSQL Backups ==="
    aws s3 ls "s3://${S3_BUCKET}/postgres/" --recursive | sort -r | head -20
    
    echo -e "\n=== Redis Backups ==="
    aws s3 ls "s3://${S3_BUCKET}/redis/" --recursive | sort -r | head -20
    
    echo -e "\n=== Media Backups ==="
    aws s3 ls "s3://${S3_BUCKET}/media/" --recursive | sort -r | head -20
    
    echo -e "\n=== Configuration Backups ==="
    aws s3 ls "s3://${S3_BUCKET}/config/" --recursive | sort -r | head -20
    
    echo -e "\n=== Backup Manifests ==="
    aws s3 ls "s3://${S3_BUCKET}/manifests/" --recursive | sort -r | head -10
}

# Download backup manifest
download_manifest() {
    local manifest_name=$1
    local manifest_path="${TEMP_DIR}/manifest.json"
    
    log "Downloading manifest: $manifest_name"
    aws s3 cp "s3://${S3_BUCKET}/manifests/${manifest_name}" "$manifest_path" || \
        error_exit "Failed to download manifest"
    
    # Display manifest contents
    log "Manifest contents:"
    cat "$manifest_path" | jq '.' || cat "$manifest_path"
    
    echo "$manifest_path"
}

# Restore PostgreSQL database
restore_postgres() {
    local backup_file=$1
    local restore_mode=${2:-"full"}  # full, schema-only, data-only
    
    log "Starting PostgreSQL restoration from: $backup_file"
    
    # Download backup
    local local_file="${TEMP_DIR}/postgres_backup.sql.gz"
    log "Downloading PostgreSQL backup from S3..."
    aws s3 cp "s3://${S3_BUCKET}/postgres/${backup_file}" "$local_file" || \
        error_exit "Failed to download PostgreSQL backup"
    
    # Verify backup file
    if [ ! -s "$local_file" ]; then
        error_exit "Downloaded PostgreSQL backup is empty"
    fi
    
    # Create restoration database
    local restore_db="${DB_NAME}_restore_$(date +%Y%m%d_%H%M%S)"
    
    if [ "$restore_mode" == "full" ]; then
        # Prompt for confirmation
        echo -e "\n⚠️  WARNING: This will replace the current database!"
        echo "Current database: $DB_NAME"
        echo "Backup file: $backup_file"
        read -p "Are you sure you want to continue? (yes/no): " confirm
        
        if [ "$confirm" != "yes" ]; then
            log "Restoration cancelled by user"
            return 1
        fi
        
        # Stop application services
        log "Stopping application services..."
        if command -v systemctl &> /dev/null; then
            sudo systemctl stop agencydark || true
            sudo systemctl stop agencydark-celery || true
        fi
        if command -v docker-compose &> /dev/null; then
            docker-compose -f docker-compose.prod.yml stop backend celery || true
        fi
        
        # Create backup of current database
        log "Creating backup of current database..."
        local current_backup="${BACKUP_BASE_DIR}/postgres/current_before_restore_$(date +%Y%m%d_%H%M%S).sql.gz"
        PGPASSWORD=$DB_PASSWORD pg_dump \
            -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME \
            --format=custom --verbose | gzip -9 > "$current_backup"
        log "Current database backed up to: $current_backup"
    fi
    
    # Create temporary restoration database
    log "Creating temporary restoration database: $restore_db"
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \
        "CREATE DATABASE \"$restore_db\" WITH OWNER = $DB_USER;"
    
    # Restore to temporary database
    log "Restoring backup to temporary database..."
    gunzip -c "$local_file" | PGPASSWORD=$DB_PASSWORD pg_restore \
        -h $DB_HOST -p $DB_PORT -U $DB_USER -d "$restore_db" \
        --no-owner --no-privileges --verbose \
        $([ "$restore_mode" == "schema-only" ] && echo "--schema-only") \
        $([ "$restore_mode" == "data-only" ] && echo "--data-only")
    
    # Verify restoration
    log "Verifying restoration..."
    local table_count=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d "$restore_db" -t -c \
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
    log "Restored database has $table_count tables"
    
    if [ "$restore_mode" == "full" ]; then
        # Rename databases
        log "Swapping databases..."
        PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres <<EOF
-- Terminate existing connections
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();

-- Rename current database
ALTER DATABASE "$DB_NAME" RENAME TO "${DB_NAME}_old_$(date +%Y%m%d_%H%M%S)";

-- Rename restored database
ALTER DATABASE "$restore_db" RENAME TO "$DB_NAME";
EOF
        
        # Run post-restore migrations
        log "Running database migrations..."
        cd /opt/agencydark/agency-dark/backend
        source venv/bin/activate
        alembic upgrade head
        
        # Start application services
        log "Starting application services..."
        if command -v systemctl &> /dev/null; then
            sudo systemctl start agencydark
            sudo systemctl start agencydark-celery
        fi
        if command -v docker-compose &> /dev/null; then
            docker-compose -f docker-compose.prod.yml start backend celery
        fi
        
        log "PostgreSQL restoration completed successfully!"
    else
        log "PostgreSQL $restore_mode restoration completed to: $restore_db"
        log "To use this database, update your DATABASE_URL to point to: $restore_db"
    fi
}

# Restore Redis data
restore_redis() {
    local backup_file=$1
    
    log "Starting Redis restoration from: $backup_file"
    
    # Download backup
    local local_file="${TEMP_DIR}/redis_backup.rdb.gz"
    log "Downloading Redis backup from S3..."
    aws s3 cp "s3://${S3_BUCKET}/redis/${backup_file}" "$local_file" || \
        error_exit "Failed to download Redis backup"
    
    # Decompress
    gunzip "$local_file"
    local_file="${TEMP_DIR}/redis_backup.rdb"
    
    # Stop Redis
    log "Stopping Redis server..."
    if command -v systemctl &> /dev/null; then
        sudo systemctl stop redis
    else
        redis-cli -a $REDIS_PASSWORD SHUTDOWN SAVE
    fi
    
    # Backup current Redis data
    local redis_dir="/var/lib/redis"
    if [ -f "$redis_dir/dump.rdb" ]; then
        log "Backing up current Redis data..."
        sudo cp "$redis_dir/dump.rdb" "$redis_dir/dump.rdb.backup.$(date +%Y%m%d_%H%M%S)"
    fi
    
    # Restore Redis data
    log "Restoring Redis data..."
    sudo cp "$local_file" "$redis_dir/dump.rdb"
    sudo chown redis:redis "$redis_dir/dump.rdb"
    sudo chmod 660 "$redis_dir/dump.rdb"
    
    # Start Redis
    log "Starting Redis server..."
    if command -v systemctl &> /dev/null; then
        sudo systemctl start redis
    else
        redis-server --daemonize yes
    fi
    
    # Verify restoration
    sleep 2
    if redis-cli -a $REDIS_PASSWORD ping &> /dev/null; then
        local db_size=$(redis-cli -a $REDIS_PASSWORD DBSIZE | awk '{print $1}')
        log "Redis restoration completed. Database contains $db_size keys"
    else
        error_exit "Redis restoration failed - cannot connect to Redis"
    fi
}

# Restore media files
restore_media() {
    local backup_file=$1
    local media_dir="${UPLOAD_DIR:-/opt/agencydark/uploads}"
    
    log "Starting media files restoration from: $backup_file"
    
    # Download backup
    local local_file="${TEMP_DIR}/media_backup.tar.gz"
    log "Downloading media backup from S3..."
    aws s3 cp "s3://${S3_BUCKET}/media/${backup_file}" "$local_file" || \
        error_exit "Failed to download media backup"
    
    # Backup current media files
    if [ -d "$media_dir" ] && [ "$(ls -A $media_dir)" ]; then
        log "Backing up current media files..."
        local media_backup_dir="${media_dir}_backup_$(date +%Y%m%d_%H%M%S)"
        sudo mv "$media_dir" "$media_backup_dir"
        log "Current media files backed up to: $media_backup_dir"
    fi
    
    # Create media directory
    sudo mkdir -p "$media_dir"
    
    # Extract media files
    log "Extracting media files..."
    sudo tar -xzf "$local_file" -C "$(dirname $media_dir)"
    
    # Set permissions
    sudo chown -R agencydark:agencydark "$media_dir"
    
    # Count restored files
    local file_count=$(find "$media_dir" -type f | wc -l)
    log "Media restoration completed. Restored $file_count files"
}

# Restore configuration
restore_config() {
    local backup_file=$1
    local config_backup_dir="${BACKUP_BASE_DIR}/config_restore_$(date +%Y%m%d_%H%M%S)"
    
    log "Starting configuration restoration from: $backup_file"
    
    # Download backup
    local local_file="${TEMP_DIR}/config_backup.tar.gz"
    log "Downloading configuration backup from S3..."
    aws s3 cp "s3://${S3_BUCKET}/config/${backup_file}" "$local_file" || \
        error_exit "Failed to download configuration backup"
    
    # Create restoration directory
    mkdir -p "$config_backup_dir"
    
    # Extract configuration files
    log "Extracting configuration files..."
    tar -xzf "$local_file" -C "$config_backup_dir"
    
    log "Configuration files restored to: $config_backup_dir"
    log "Please review and manually copy the needed configuration files"
    
    # List restored files
    log "Restored configuration files:"
    ls -la "$config_backup_dir"
}

# Verify system after restoration
verify_system() {
    log "Verifying system after restoration..."
    
    # Check database connection
    log "Checking database connection..."
    if PGPASSWORD=$DB_PASSWORD pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER; then
        log "✓ Database connection OK"
    else
        log "✗ Database connection FAILED"
    fi
    
    # Check Redis connection
    log "Checking Redis connection..."
    if redis-cli -a $REDIS_PASSWORD ping &> /dev/null; then
        log "✓ Redis connection OK"
    else
        log "✗ Redis connection FAILED"
    fi
    
    # Check application health
    log "Checking application health..."
    if curl -f http://localhost:8000/health &> /dev/null; then
        log "✓ Application health check OK"
    else
        log "✗ Application health check FAILED"
    fi
    
    # Check critical tables
    log "Checking critical database tables..."
    for table in users agencies models subscribers transactions; do
        local count=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c \
            "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "0")
        log "  Table '$table': $count records"
    done
}

# Interactive restoration menu
interactive_restore() {
    while true; do
        echo -e "\n=== AgencyDark Restoration Menu ==="
        echo "1. List available backups"
        echo "2. Restore from specific timestamp"
        echo "3. Restore PostgreSQL only"
        echo "4. Restore Redis only"
        echo "5. Restore media files only"
        echo "6. Restore configuration only"
        echo "7. Verify system status"
        echo "8. Exit"
        
        read -p "Select option (1-8): " option
        
        case $option in
            1)
                list_backups
                ;;
            2)
                read -p "Enter backup timestamp (YYYYMMDD_HHMMSS): " timestamp
                
                # Download and show manifest
                if aws s3 ls "s3://${S3_BUCKET}/manifests/manifest_${timestamp}.json" &> /dev/null; then
                    manifest_path=$(download_manifest "manifest_${timestamp}.json")
                    
                    read -p "Restore all components? (yes/no): " restore_all
                    if [ "$restore_all" == "yes" ]; then
                        restore_postgres "postgres_${DB_NAME}_${timestamp}.sql.gz" "full"
                        restore_redis "redis_${timestamp}.rdb.gz"
                        restore_media "media_${timestamp}.tar.gz"
                        verify_system
                    fi
                else
                    log "No manifest found for timestamp: $timestamp"
                fi
                ;;
            3)
                list_backups | grep "postgres/" | head -10
                read -p "Enter PostgreSQL backup filename: " pg_backup
                read -p "Restore mode (full/schema-only/data-only) [full]: " mode
                mode=${mode:-full}
                restore_postgres "$pg_backup" "$mode"
                ;;
            4)
                list_backups | grep "redis/" | head -10
                read -p "Enter Redis backup filename: " redis_backup
                restore_redis "$redis_backup"
                ;;
            5)
                list_backups | grep "media/" | head -10
                read -p "Enter media backup filename: " media_backup
                restore_media "$media_backup"
                ;;
            6)
                list_backups | grep "config/" | head -10
                read -p "Enter config backup filename: " config_backup
                restore_config "$config_backup"
                ;;
            7)
                verify_system
                ;;
            8)
                log "Exiting restoration tool"
                exit 0
                ;;
            *)
                echo "Invalid option"
                ;;
        esac
    done
}

# Main function
main() {
    log "=== Starting AgencyDark Recovery Tool ==="
    
    # Check prerequisites
    for cmd in aws psql redis-cli jq curl; do
        if ! command -v $cmd &> /dev/null; then
            error_exit "$cmd is not installed"
        fi
    done
    
    # Parse command line arguments
    case "${1:-}" in
        --list)
            list_backups
            ;;
        --restore-all)
            if [ -z "${2:-}" ]; then
                error_exit "Timestamp required for --restore-all"
            fi
            manifest_path=$(download_manifest "manifest_${2}.json")
            restore_postgres "postgres_${DB_NAME}_${2}.sql.gz" "full"
            restore_redis "redis_${2}.rdb.gz"
            restore_media "media_${2}.tar.gz"
            verify_system
            ;;
        --restore-postgres)
            if [ -z "${2:-}" ]; then
                error_exit "Backup filename required for --restore-postgres"
            fi
            restore_postgres "${2}" "${3:-full}"
            ;;
        --restore-redis)
            if [ -z "${2:-}" ]; then
                error_exit "Backup filename required for --restore-redis"
            fi
            restore_redis "${2}"
            ;;
        --restore-media)
            if [ -z "${2:-}" ]; then
                error_exit "Backup filename required for --restore-media"
            fi
            restore_media "${2}"
            ;;
        --verify)
            verify_system
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --list                    List available backups"
            echo "  --restore-all TIMESTAMP   Restore all components from timestamp"
            echo "  --restore-postgres FILE   Restore PostgreSQL backup"
            echo "  --restore-redis FILE      Restore Redis backup"
            echo "  --restore-media FILE      Restore media files backup"
            echo "  --verify                  Verify system status"
            echo "  --help                    Show this help message"
            echo ""
            echo "Interactive mode: Run without arguments"
            ;;
        *)
            interactive_restore
            ;;
    esac
    
    log "=== Recovery process completed ==="
}

# Run main function
main "$@"

exit 0