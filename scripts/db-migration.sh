#!/bin/bash
set -euo pipefail

# Database Migration Automation Script
# Usage: ./db-migration.sh <environment> <action> [options]

ENVIRONMENT=${1:-staging}
ACTION=${2:-upgrade}
MIGRATION_TARGET=${3:-head}
NAMESPACE=${ENVIRONMENT}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BACKUP_BUCKET="s3://agency-backups/migrations"
MIGRATION_POD_PREFIX="db-migration"
MIGRATION_IMAGE="agency/backend:latest"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Create backup before migration
create_backup() {
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_name="pre-migration-${ENVIRONMENT}-${timestamp}.sql"
    
    log_info "Creating database backup: $backup_name"
    
    # Run backup job
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: db-backup-${timestamp}
  namespace: $NAMESPACE
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: backup
        image: postgres:16-alpine
        command:
        - sh
        - -c
        - |
          pg_dump \$DATABASE_URL > /tmp/$backup_name
          aws s3 cp /tmp/$backup_name $BACKUP_BUCKET/$backup_name
          echo "Backup created: $backup_name"
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: database-url
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: aws-access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: aws-secret-access-key
EOF
    
    # Wait for backup to complete
    kubectl wait --for=condition=complete job/db-backup-${timestamp} -n $NAMESPACE --timeout=600s
    
    # Check if backup was successful
    if kubectl logs job/db-backup-${timestamp} -n $NAMESPACE | grep -q "Backup created"; then
        log_success "Database backup completed: $backup_name"
        echo $backup_name
    else
        log_error "Database backup failed"
        kubectl delete job/db-backup-${timestamp} -n $NAMESPACE
        exit 1
    fi
    
    # Clean up job
    kubectl delete job/db-backup-${timestamp} -n $NAMESPACE
}

# Run migration
run_migration() {
    local action=$1
    local target=$2
    local timestamp=$(date +%Y%m%d-%H%M%S)
    
    log_info "Running migration: alembic $action $target"
    
    # Create migration job
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration-${timestamp}
  namespace: $NAMESPACE
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: migration
        image: $MIGRATION_IMAGE
        command:
        - sh
        - -c
        - |
          echo "Starting migration..."
          cd /app
          
          # Show current migration status
          alembic current
          
          # Show migration history
          alembic history
          
          # Run migration
          alembic $action $target
          
          # Show new status
          alembic current
          
          echo "Migration completed successfully"
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: database-url
        - name: ENVIRONMENT
          value: $ENVIRONMENT
EOF
    
    # Stream logs from migration job
    log_info "Streaming migration logs..."
    kubectl logs -f job/db-migration-${timestamp} -n $NAMESPACE
    
    # Wait for migration to complete
    kubectl wait --for=condition=complete job/db-migration-${timestamp} -n $NAMESPACE --timeout=600s
    
    # Check migration status
    local exit_code=$(kubectl get job/db-migration-${timestamp} -n $NAMESPACE -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}')
    
    if [[ "$exit_code" == "True" ]]; then
        log_error "Migration failed"
        kubectl delete job/db-migration-${timestamp} -n $NAMESPACE
        return 1
    else
        log_success "Migration completed successfully"
        kubectl delete job/db-migration-${timestamp} -n $NAMESPACE
        return 0
    fi
}

# Rollback migration
rollback_migration() {
    local steps=${1:-1}
    
    log_warning "Rolling back migration by $steps steps"
    run_migration "downgrade" "-$steps"
}

# Restore from backup
restore_backup() {
    local backup_name=$1
    
    log_info "Restoring database from backup: $backup_name"
    
    # Create restore job
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: db-restore-$(date +%Y%m%d-%H%M%S)
  namespace: $NAMESPACE
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: restore
        image: postgres:16-alpine
        command:
        - sh
        - -c
        - |
          # Download backup
          aws s3 cp $BACKUP_BUCKET/$backup_name /tmp/$backup_name
          
          # Drop existing connections
          psql \$DATABASE_URL -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();"
          
          # Restore database
          psql \$DATABASE_URL < /tmp/$backup_name
          
          echo "Database restored from: $backup_name"
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: database-url
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: aws-access-key-id
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: aws-secret-access-key
EOF
    
    log_success "Database restored from backup"
}

# Validate migration
validate_migration() {
    log_info "Validating migration..."
    
    # Run validation checks
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: db-validate-$(date +%Y%m%d-%H%M%S)
  namespace: $NAMESPACE
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: validate
        image: $MIGRATION_IMAGE
        command:
        - python
        - -c
        - |
          import asyncio
          from sqlalchemy import text
          from app.core.database import get_db_engine
          
          async def validate():
              engine = get_db_engine()
              async with engine.connect() as conn:
                  # Check if all tables exist
                  result = await conn.execute(text("""
                      SELECT table_name 
                      FROM information_schema.tables 
                      WHERE table_schema = 'public'
                      ORDER BY table_name
                  """))
                  tables = [row[0] for row in result]
                  print(f"Found {len(tables)} tables")
                  
                  # Check migration version
                  result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                  version = result.scalar()
                  print(f"Current migration version: {version}")
                  
                  # Run basic queries
                  for table in ['users', 'clients', 'campaigns', 'tasks']:
                      if table in tables:
                          result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                          count = result.scalar()
                          print(f"Table {table}: {count} records")
                  
                  print("Validation completed successfully")
          
          asyncio.run(validate())
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: database-url
EOF
    
    log_success "Migration validation completed"
}

# Main function
main() {
    case $ACTION in
        "upgrade")
            log_info "Starting database migration upgrade to $MIGRATION_TARGET"
            
            # Create backup
            BACKUP_FILE=$(create_backup)
            
            # Run migration
            if run_migration "upgrade" "$MIGRATION_TARGET"; then
                validate_migration
                log_success "Migration completed successfully"
            else
                log_error "Migration failed, consider restoring from backup: $BACKUP_FILE"
                exit 1
            fi
            ;;
            
        "downgrade")
            log_info "Starting database migration downgrade"
            
            # Create backup
            BACKUP_FILE=$(create_backup)
            
            # Run rollback
            if rollback_migration "${MIGRATION_TARGET:-1}"; then
                validate_migration
                log_success "Rollback completed successfully"
            else
                log_error "Rollback failed"
                exit 1
            fi
            ;;
            
        "validate")
            validate_migration
            ;;
            
        "backup")
            create_backup
            ;;
            
        "restore")
            if [[ -z "$MIGRATION_TARGET" ]]; then
                log_error "Backup file name required for restore"
                exit 1
            fi
            restore_backup "$MIGRATION_TARGET"
            ;;
            
        *)
            log_error "Unknown action: $ACTION"
            echo "Usage: $0 <environment> <action> [target]"
            echo "Actions: upgrade, downgrade, validate, backup, restore"
            exit 1
            ;;
    esac
}

# Run main function
main