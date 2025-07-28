#!/bin/bash

# AgencyDark Backup Script
# This script performs manual backups of the application data

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
BACKUP_TYPE=${2:-full}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PROJECT_NAME="agencydark"
BACKUP_DIR="/tmp/${PROJECT_NAME}_backup_${TIMESTAMP}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to backup database
backup_database() {
    print_status "Backing up database..."
    
    # Get database credentials from environment or AWS Secrets Manager
    if [ "$ENVIRONMENT" == "production" ]; then
        # Get from AWS Secrets Manager
        DB_SECRET=$(aws secretsmanager get-secret-value --secret-id ${PROJECT_NAME}/db/${ENVIRONMENT} --query SecretString --output text)
        DB_HOST=$(echo $DB_SECRET | jq -r .host)
        DB_NAME=$(echo $DB_SECRET | jq -r .database)
        DB_USER=$(echo $DB_SECRET | jq -r .username)
        DB_PASSWORD=$(echo $DB_SECRET | jq -r .password)
    else
        # Use local environment variables
        DB_HOST=${DB_HOST:-localhost}
        DB_NAME=${DB_NAME:-agencydark}
        DB_USER=${DB_USER:-postgres}
        DB_PASSWORD=${DB_PASSWORD:-postgres}
    fi
    
    # Create backup directory
    mkdir -p $BACKUP_DIR
    
    # Perform database dump
    PGPASSWORD=$DB_PASSWORD pg_dump \
        -h $DB_HOST \
        -U $DB_USER \
        -d $DB_NAME \
        -f $BACKUP_DIR/database_${TIMESTAMP}.sql \
        --verbose \
        --no-owner \
        --no-acl
    
    # Compress the dump
    gzip $BACKUP_DIR/database_${TIMESTAMP}.sql
    
    print_status "Database backup completed: database_${TIMESTAMP}.sql.gz"
}

# Function to backup uploads
backup_uploads() {
    print_status "Backing up uploaded files..."
    
    if [ "$ENVIRONMENT" == "production" ]; then
        # Sync from S3
        S3_BUCKET="${PROJECT_NAME}-uploads-${ENVIRONMENT}"
        aws s3 sync s3://$S3_BUCKET $BACKUP_DIR/uploads/
    else
        # Copy local uploads
        cp -r backend/uploads $BACKUP_DIR/
    fi
    
    # Create tar archive
    tar -czf $BACKUP_DIR/uploads_${TIMESTAMP}.tar.gz -C $BACKUP_DIR uploads/
    rm -rf $BACKUP_DIR/uploads
    
    print_status "Uploads backup completed: uploads_${TIMESTAMP}.tar.gz"
}

# Function to backup configurations
backup_configs() {
    print_status "Backing up configurations..."
    
    # Create configs directory
    mkdir -p $BACKUP_DIR/configs
    
    # Backup environment variables
    if [ "$ENVIRONMENT" == "production" ]; then
        # Export from AWS Systems Manager Parameter Store
        aws ssm get-parameters-by-path \
            --path "/${PROJECT_NAME}/${ENVIRONMENT}" \
            --recursive \
            --with-decryption \
            --query "Parameters[*].[Name,Value]" \
            --output json > $BACKUP_DIR/configs/parameters_${TIMESTAMP}.json
    else
        # Copy local .env files
        cp backend/.env $BACKUP_DIR/configs/backend.env 2>/dev/null || true
        cp frontend/.env $BACKUP_DIR/configs/frontend.env 2>/dev/null || true
    fi
    
    # Create tar archive
    tar -czf $BACKUP_DIR/configs_${TIMESTAMP}.tar.gz -C $BACKUP_DIR configs/
    rm -rf $BACKUP_DIR/configs
    
    print_status "Configuration backup completed: configs_${TIMESTAMP}.tar.gz"
}

# Function to upload backup to S3
upload_to_s3() {
    print_status "Uploading backups to S3..."
    
    S3_BACKUP_BUCKET="${PROJECT_NAME}-backups-${ENVIRONMENT}"
    S3_PREFIX="manual/${TIMESTAMP}"
    
    # Upload all backup files
    for file in $BACKUP_DIR/*.{gz,tar.gz}; do
        if [ -f "$file" ]; then
            filename=$(basename "$file")
            aws s3 cp $file s3://$S3_BACKUP_BUCKET/$S3_PREFIX/$filename \
                --storage-class STANDARD_IA \
                --metadata "backup-type=${BACKUP_TYPE},environment=${ENVIRONMENT},timestamp=${TIMESTAMP}"
            print_status "Uploaded: $filename"
        fi
    done
    
    print_status "All backups uploaded to S3."
}

# Function to create backup manifest
create_manifest() {
    print_status "Creating backup manifest..."
    
    cat > $BACKUP_DIR/manifest_${TIMESTAMP}.json <<EOF
{
    "timestamp": "${TIMESTAMP}",
    "environment": "${ENVIRONMENT}",
    "backup_type": "${BACKUP_TYPE}",
    "files": [
        "database_${TIMESTAMP}.sql.gz",
        "uploads_${TIMESTAMP}.tar.gz",
        "configs_${TIMESTAMP}.tar.gz"
    ],
    "metadata": {
        "project": "${PROJECT_NAME}",
        "created_by": "$(whoami)",
        "host": "$(hostname)"
    }
}
EOF
    
    print_status "Manifest created: manifest_${TIMESTAMP}.json"
}

# Function to cleanup local files
cleanup() {
    print_status "Cleaning up local backup files..."
    rm -rf $BACKUP_DIR
    print_status "Cleanup completed."
}

# Function to list existing backups
list_backups() {
    print_status "Listing existing backups..."
    
    S3_BACKUP_BUCKET="${PROJECT_NAME}-backups-${ENVIRONMENT}"
    
    aws s3 ls s3://$S3_BACKUP_BUCKET/manual/ --recursive | grep -E '\.(gz|json)$' | sort -r | head -20
}

# Function to restore from backup
restore_backup() {
    BACKUP_TIMESTAMP=$1
    
    if [ -z "$BACKUP_TIMESTAMP" ]; then
        print_error "Please provide a backup timestamp to restore"
        exit 1
    fi
    
    print_warning "Restoring from backup: $BACKUP_TIMESTAMP"
    print_warning "This will overwrite existing data. Are you sure? (yes/no)"
    read -r response
    
    if [ "$response" != "yes" ]; then
        print_status "Restore cancelled."
        exit 0
    fi
    
    # Download backup files from S3
    S3_BACKUP_BUCKET="${PROJECT_NAME}-backups-${ENVIRONMENT}"
    S3_PREFIX="manual/${BACKUP_TIMESTAMP}"
    RESTORE_DIR="/tmp/${PROJECT_NAME}_restore_${BACKUP_TIMESTAMP}"
    
    mkdir -p $RESTORE_DIR
    aws s3 sync s3://$S3_BACKUP_BUCKET/$S3_PREFIX/ $RESTORE_DIR/
    
    # Restore database
    if [ -f "$RESTORE_DIR/database_${BACKUP_TIMESTAMP}.sql.gz" ]; then
        print_status "Restoring database..."
        gunzip -c $RESTORE_DIR/database_${BACKUP_TIMESTAMP}.sql.gz | \
            PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME
    fi
    
    # Restore uploads
    if [ -f "$RESTORE_DIR/uploads_${BACKUP_TIMESTAMP}.tar.gz" ]; then
        print_status "Restoring uploads..."
        tar -xzf $RESTORE_DIR/uploads_${BACKUP_TIMESTAMP}.tar.gz -C /tmp/
        if [ "$ENVIRONMENT" == "production" ]; then
            aws s3 sync /tmp/uploads/ s3://${PROJECT_NAME}-uploads-${ENVIRONMENT}/
        else
            cp -r /tmp/uploads/* backend/uploads/
        fi
    fi
    
    print_status "Restore completed."
    rm -rf $RESTORE_DIR
}

# Main function
main() {
    case $BACKUP_TYPE in
        full)
            backup_database
            backup_uploads
            backup_configs
            create_manifest
            upload_to_s3
            cleanup
            print_status "Full backup completed successfully!"
            ;;
            
        database)
            backup_database
            create_manifest
            upload_to_s3
            cleanup
            print_status "Database backup completed successfully!"
            ;;
            
        uploads)
            backup_uploads
            create_manifest
            upload_to_s3
            cleanup
            print_status "Uploads backup completed successfully!"
            ;;
            
        list)
            list_backups
            ;;
            
        restore)
            restore_backup $3
            ;;
            
        *)
            print_error "Unknown backup type: $BACKUP_TYPE"
            echo "Usage: $0 [environment] [backup_type] [timestamp_for_restore]"
            echo "Backup types: full, database, uploads, list, restore"
            exit 1
            ;;
    esac
}

# Run main function
main