#!/bin/bash
set -euo pipefail

# Database Recovery Script
# Usage: ./recover-database.sh <recovery-point> [environment]

RECOVERY_POINT=${1:-latest}
ENVIRONMENT=${2:-production}
NAMESPACE=${ENVIRONMENT}

# Configuration
BACKUP_BUCKET="s3://agency-backups"
TEMP_DIR="/tmp/db-recovery-$$"
LOG_FILE="/tmp/db-recovery-$(date +%Y%m%d-%H%M%S).log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging
log_info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} INFO: $1" | tee -a $LOG_FILE
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} SUCCESS: $1" | tee -a $LOG_FILE
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} ERROR: $1" | tee -a $LOG_FILE
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} WARNING: $1" | tee -a $LOG_FILE
}

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary files..."
    rm -rf $TEMP_DIR
}

trap cleanup EXIT

# Find backup file
find_backup() {
    local recovery_point=$1
    
    if [[ "$recovery_point" == "latest" ]]; then
        log_info "Finding latest backup..."
        BACKUP_FILE=$(aws s3 ls $BACKUP_BUCKET/postgres/ --recursive | grep ".sql" | sort | tail -n 1 | awk '{print $4}')
    else
        log_info "Finding backup for recovery point: $recovery_point"
        BACKUP_FILE=$(aws s3 ls $BACKUP_BUCKET/postgres/ --recursive | grep "$recovery_point" | grep ".sql" | head -n 1 | awk '{print $4}')
    fi
    
    if [[ -z "$BACKUP_FILE" ]]; then
        log_error "No backup found for recovery point: $recovery_point"
        exit 1
    fi
    
    log_success "Found backup: $BACKUP_FILE"
    echo $BACKUP_FILE
}

# Stop application services
stop_services() {
    log_info "Stopping application services..."
    
    # Scale down deployments
    kubectl scale deployment -n $NAMESPACE -l app=agency-backend --replicas=0
    
    # Wait for pods to terminate
    kubectl wait --for=delete pod -n $NAMESPACE -l app=agency-backend --timeout=300s || true
    
    log_success "Application services stopped"
}

# Start application services
start_services() {
    log_info "Starting application services..."
    
    # Scale up deployments
    kubectl scale deployment -n $NAMESPACE -l app=agency-backend --replicas=3
    
    # Wait for pods to be ready
    kubectl wait --for=condition=ready pod -n $NAMESPACE -l app=agency-backend --timeout=300s
    
    log_success "Application services started"
}

# Create recovery job
create_recovery_job() {
    local backup_file=$1
    local job_name="db-recovery-$(date +%Y%m%d-%H%M%S)"
    
    log_info "Creating recovery job: $job_name"
    
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: $job_name
  namespace: $NAMESPACE
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: recovery
        image: postgres:16-alpine
        command:
        - sh
        - -c
        - |
          set -e
          
          echo "Starting database recovery..."
          
          # Install AWS CLI
          apk add --no-cache aws-cli
          
          # Create temp directory
          mkdir -p /tmp/recovery
          cd /tmp/recovery
          
          # Download backup
          echo "Downloading backup: $backup_file"
          aws s3 cp $BACKUP_BUCKET/$backup_file backup.sql
          
          # Get database connection info
          DB_HOST=\$(echo \$DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
          DB_NAME=\$(echo \$DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
          
          # Create recovery point
          echo "Creating recovery point..."
          pg_dump \$DATABASE_URL > pre-recovery-$(date +%Y%m%d-%H%M%S).sql
          aws s3 cp pre-recovery-*.sql $BACKUP_BUCKET/recovery-points/
          
          # Terminate existing connections
          echo "Terminating existing connections..."
          psql \$DATABASE_URL -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '\$DB_NAME' AND pid <> pg_backend_pid();"
          
          # Drop and recreate database
          echo "Recreating database..."
          psql \$DATABASE_URL -c "DROP DATABASE IF EXISTS \${DB_NAME}_recovery;"
          psql \$DATABASE_URL -c "CREATE DATABASE \${DB_NAME}_recovery;"
          
          # Restore backup
          echo "Restoring backup..."
          psql postgresql://\${DATABASE_URL#postgresql://}/../\${DB_NAME}_recovery < backup.sql
          
          # Verify restoration
          echo "Verifying restoration..."
          TABLES=\$(psql postgresql://\${DATABASE_URL#postgresql://}/../\${DB_NAME}_recovery -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
          echo "Restored \$TABLES tables"
          
          # Swap databases
          echo "Swapping databases..."
          psql \$DATABASE_URL <<-EOSQL
            ALTER DATABASE \$DB_NAME RENAME TO \${DB_NAME}_old;
            ALTER DATABASE \${DB_NAME}_recovery RENAME TO \$DB_NAME;
          EOSQL
          
          echo "Database recovery completed successfully"
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
        - name: AWS_DEFAULT_REGION
          value: us-east-1
EOF
    
    # Stream logs
    log_info "Streaming recovery logs..."
    kubectl logs -f job/$job_name -n $NAMESPACE | tee -a $LOG_FILE
    
    # Wait for completion
    kubectl wait --for=condition=complete job/$job_name -n $NAMESPACE --timeout=3600s
    
    # Check status
    local failed=$(kubectl get job/$job_name -n $NAMESPACE -o jsonpath='{.status.failed}')
    if [[ "$failed" == "1" ]]; then
        log_error "Recovery job failed"
        kubectl delete job/$job_name -n $NAMESPACE
        return 1
    fi
    
    log_success "Recovery job completed"
    kubectl delete job/$job_name -n $NAMESPACE
    return 0
}

# Verify database
verify_database() {
    log_info "Verifying database integrity..."
    
    local job_name="db-verify-$(date +%Y%m%d-%H%M%S)"
    
    cat <<EOF | kubectl apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: $job_name
  namespace: $NAMESPACE
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
      - name: verify
        image: agency/backend:latest
        command:
        - python
        - -c
        - |
          import asyncio
          from sqlalchemy import text
          from app.core.database import get_db_engine
          
          async def verify():
              engine = get_db_engine()
              async with engine.connect() as conn:
                  # Check tables
                  result = await conn.execute(text("""
                      SELECT COUNT(*) FROM information_schema.tables 
                      WHERE table_schema = 'public'
                  """))
                  table_count = result.scalar()
                  print(f"Tables found: {table_count}")
                  
                  # Check critical tables
                  critical_tables = ['users', 'clients', 'campaigns', 'tasks']
                  for table in critical_tables:
                      result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                      count = result.scalar()
                      print(f"Table {table}: {count} records")
                  
                  # Check constraints
                  result = await conn.execute(text("""
                      SELECT COUNT(*) FROM information_schema.table_constraints
                      WHERE constraint_schema = 'public'
                  """))
                  constraint_count = result.scalar()
                  print(f"Constraints found: {constraint_count}")
                  
                  print("Database verification completed")
          
          asyncio.run(verify())
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: agency-backend-secret
              key: database-url
EOF
    
    kubectl wait --for=condition=complete job/$job_name -n $NAMESPACE --timeout=300s
    kubectl logs job/$job_name -n $NAMESPACE | tee -a $LOG_FILE
    kubectl delete job/$job_name -n $NAMESPACE
    
    log_success "Database verification completed"
}

# Main recovery process
main() {
    log_info "Starting database recovery process"
    log_info "Environment: $ENVIRONMENT"
    log_info "Recovery Point: $RECOVERY_POINT"
    
    # Create temp directory
    mkdir -p $TEMP_DIR
    
    # Find backup file
    BACKUP_FILE=$(find_backup $RECOVERY_POINT)
    
    # Confirm recovery
    echo -e "${YELLOW}WARNING: This will replace the current database with the backup.${NC}"
    echo -e "Backup file: ${BLUE}$BACKUP_FILE${NC}"
    read -p "Continue with recovery? (yes/no): " confirm
    
    if [[ "$confirm" != "yes" ]]; then
        log_warning "Recovery cancelled by user"
        exit 0
    fi
    
    # Stop services
    stop_services
    
    # Perform recovery
    if create_recovery_job $BACKUP_FILE; then
        log_success "Database recovery successful"
        
        # Verify database
        verify_database
        
        # Start services
        start_services
        
        log_success "Recovery process completed successfully"
        echo -e "${GREEN}Recovery log saved to: $LOG_FILE${NC}"
    else
        log_error "Database recovery failed"
        log_warning "Services remain stopped. Manual intervention required."
        exit 1
    fi
}

# Run main function
main