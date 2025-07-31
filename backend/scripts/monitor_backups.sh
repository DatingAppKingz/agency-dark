#!/bin/bash

# AgencyDark Backup Monitoring Script
# This script monitors backup status and sends alerts for failures

set -euo pipefail

# Load environment variables
if [ -f .env.production ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
fi

# Configuration
BACKUP_BASE_DIR="${BACKUP_DIR:-/opt/agencydark/backups}"
S3_BUCKET="${S3_BACKUP_BUCKET:-agencydark-backups}"
ALERT_EMAIL="${BACKUP_ALERT_EMAIL:-alerts@agencydark.com}"
SLACK_WEBHOOK="${BACKUP_SLACK_WEBHOOK:-}"
MAX_AGE_HOURS="${BACKUP_MAX_AGE_HOURS:-25}"  # Alert if backup older than 25 hours
MIN_SIZE_MB="${BACKUP_MIN_SIZE_MB:-10}"      # Alert if backup smaller than 10MB
LOG_FILE="${BACKUP_BASE_DIR}/monitor_$(date +%Y%m%d).log"

# Create directories
mkdir -p "${BACKUP_BASE_DIR}/logs"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Send alert
send_alert() {
    local level=$1
    local component=$2
    local message=$3
    
    log "ALERT [$level] $component: $message"
    
    # Email alert
    if [ ! -z "${SMTP_HOST:-}" ]; then
        echo -e "Subject: AgencyDark Backup Alert - $level\n\nComponent: $component\nMessage: $message\nTime: $(date)" | \
            mail -s "AgencyDark Backup $level: $component" "$ALERT_EMAIL"
    fi
    
    # Slack alert
    if [ ! -z "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\":warning: Backup Alert [$level]\\nComponent: $component\\nMessage: $message\"}" \
            "$SLACK_WEBHOOK" 2>/dev/null || true
    fi
    
    # Prometheus metric
    if [ ! -z "${PROMETHEUS_PUSHGATEWAY:-}" ]; then
        cat <<EOF | curl --data-binary @- ${PROMETHEUS_PUSHGATEWAY}/metrics/job/backup_monitor
# TYPE backup_alert gauge
backup_alert{component="$component",level="$level"} 1
EOF
    fi
}

# Check backup age
check_backup_age() {
    local component=$1
    local prefix=$2
    
    log "Checking $component backup age..."
    
    # Get latest backup from S3
    local latest_backup=$(aws s3api list-objects-v2 \
        --bucket "$S3_BUCKET" \
        --prefix "$prefix/" \
        --query 'sort_by(Contents, &LastModified)[-1].{Key: Key, LastModified: LastModified}' \
        --output json)
    
    if [ "$latest_backup" == "null" ] || [ -z "$latest_backup" ]; then
        send_alert "CRITICAL" "$component" "No backups found in S3"
        return 1
    fi
    
    local backup_key=$(echo "$latest_backup" | jq -r '.Key')
    local backup_time=$(echo "$latest_backup" | jq -r '.LastModified')
    local backup_age_seconds=$(($(date +%s) - $(date -d "$backup_time" +%s)))
    local backup_age_hours=$((backup_age_seconds / 3600))
    
    log "$component latest backup: $backup_key (age: ${backup_age_hours}h)"
    
    if [ $backup_age_hours -gt $MAX_AGE_HOURS ]; then
        send_alert "WARNING" "$component" "Latest backup is ${backup_age_hours} hours old (threshold: ${MAX_AGE_HOURS}h)"
        return 1
    fi
    
    return 0
}

# Check backup size
check_backup_size() {
    local component=$1
    local prefix=$2
    
    log "Checking $component backup size..."
    
    # Get latest backup size
    local latest_backup=$(aws s3api list-objects-v2 \
        --bucket "$S3_BUCKET" \
        --prefix "$prefix/" \
        --query 'sort_by(Contents, &LastModified)[-1].{Key: Key, Size: Size}' \
        --output json)
    
    if [ "$latest_backup" == "null" ] || [ -z "$latest_backup" ]; then
        return 1  # Already alerted in age check
    fi
    
    local backup_key=$(echo "$latest_backup" | jq -r '.Key')
    local backup_size=$(echo "$latest_backup" | jq -r '.Size')
    local backup_size_mb=$((backup_size / 1024 / 1024))
    
    log "$component backup size: ${backup_size_mb}MB"
    
    if [ $backup_size_mb -lt $MIN_SIZE_MB ]; then
        send_alert "WARNING" "$component" "Backup size is only ${backup_size_mb}MB (minimum: ${MIN_SIZE_MB}MB)"
        return 1
    fi
    
    return 0
}

# Check backup integrity
check_backup_integrity() {
    local component=$1
    local prefix=$2
    
    log "Checking $component backup integrity..."
    
    # For PostgreSQL backups, we can verify the header
    if [ "$component" == "PostgreSQL" ]; then
        local latest_backup=$(aws s3api list-objects-v2 \
            --bucket "$S3_BUCKET" \
            --prefix "$prefix/" \
            --query 'sort_by(Contents, &LastModified)[-1].Key' \
            --output text)
        
        if [ "$latest_backup" != "None" ]; then
            # Download first 1KB to check header
            local temp_file=$(mktemp)
            aws s3api get-object \
                --bucket "$S3_BUCKET" \
                --key "$latest_backup" \
                --range "bytes=0-1024" \
                "$temp_file" >/dev/null 2>&1
            
            # Check if it's a valid gzip file
            if ! gzip -t "$temp_file" 2>/dev/null; then
                send_alert "CRITICAL" "$component" "Backup file appears corrupted"
                rm -f "$temp_file"
                return 1
            fi
            rm -f "$temp_file"
        fi
    fi
    
    return 0
}

# Check disk space
check_disk_space() {
    log "Checking disk space..."
    
    local usage=$(df -h "$BACKUP_BASE_DIR" | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ $usage -gt 90 ]; then
        send_alert "CRITICAL" "Disk Space" "Backup directory is ${usage}% full"
    elif [ $usage -gt 80 ]; then
        send_alert "WARNING" "Disk Space" "Backup directory is ${usage}% full"
    fi
}

# Check backup process
check_backup_process() {
    log "Checking backup process..."
    
    # Check if backup script is running
    if pgrep -f "backup.sh" > /dev/null; then
        log "Backup process is currently running"
        
        # Check if it's been running too long (>2 hours)
        local pid=$(pgrep -f "backup.sh" | head -1)
        local runtime=$(($(date +%s) - $(stat -c %Y /proc/$pid 2>/dev/null || echo 0)))
        
        if [ $runtime -gt 7200 ]; then
            send_alert "WARNING" "Backup Process" "Backup has been running for over 2 hours"
        fi
    fi
}

# Check S3 bucket accessibility
check_s3_access() {
    log "Checking S3 bucket access..."
    
    if ! aws s3 ls "s3://$S3_BUCKET/" >/dev/null 2>&1; then
        send_alert "CRITICAL" "S3 Access" "Cannot access S3 bucket: $S3_BUCKET"
        return 1
    fi
    
    return 0
}

# Generate status report
generate_report() {
    local report_file="${BACKUP_BASE_DIR}/backup_status_$(date +%Y%m%d_%H%M%S).html"
    
    cat > "$report_file" <<EOF
<!DOCTYPE html>
<html>
<head>
    <title>AgencyDark Backup Status Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        .ok { color: green; }
        .warning { color: orange; }
        .critical { color: red; }
    </style>
</head>
<body>
    <h1>AgencyDark Backup Status Report</h1>
    <p>Generated: $(date)</p>
    
    <h2>Backup Status</h2>
    <table>
        <tr>
            <th>Component</th>
            <th>Latest Backup</th>
            <th>Age (hours)</th>
            <th>Size</th>
            <th>Status</th>
        </tr>
EOF

    # Check each component
    for component in "postgres:PostgreSQL" "redis:Redis" "media:Media" "config:Config"; do
        IFS=':' read -r prefix name <<< "$component"
        
        # Get backup info
        local latest=$(aws s3api list-objects-v2 \
            --bucket "$S3_BUCKET" \
            --prefix "$prefix/" \
            --query 'sort_by(Contents, &LastModified)[-1]' \
            --output json)
        
        if [ "$latest" != "null" ] && [ ! -z "$latest" ]; then
            local key=$(echo "$latest" | jq -r '.Key' | xargs basename)
            local modified=$(echo "$latest" | jq -r '.LastModified')
            local size=$(echo "$latest" | jq -r '.Size')
            local age=$(($(date +%s) - $(date -d "$modified" +%s)))
            local age_hours=$((age / 3600))
            local size_mb=$((size / 1024 / 1024))
            
            local status_class="ok"
            local status_text="OK"
            
            if [ $age_hours -gt $MAX_AGE_HOURS ]; then
                status_class="warning"
                status_text="OLD"
            fi
            
            if [ $size_mb -lt $MIN_SIZE_MB ]; then
                status_class="warning"
                status_text="SMALL"
            fi
            
            cat >> "$report_file" <<EOF
        <tr>
            <td>$name</td>
            <td>$key</td>
            <td>$age_hours</td>
            <td>${size_mb}MB</td>
            <td class="$status_class">$status_text</td>
        </tr>
EOF
        else
            cat >> "$report_file" <<EOF
        <tr>
            <td>$name</td>
            <td colspan="3">No backups found</td>
            <td class="critical">MISSING</td>
        </tr>
EOF
        fi
    done
    
    # Complete HTML
    cat >> "$report_file" <<EOF
    </table>
    
    <h2>System Status</h2>
    <ul>
        <li>Disk Usage: $(df -h "$BACKUP_BASE_DIR" | awk 'NR==2 {print $5}')</li>
        <li>S3 Bucket: $S3_BUCKET</li>
        <li>Monitoring Time: $(date)</li>
    </ul>
</body>
</html>
EOF
    
    log "Report generated: $report_file"
    
    # Upload report to S3
    aws s3 cp "$report_file" "s3://$S3_BUCKET/reports/" || true
}

# Main monitoring function
main() {
    log "=== Starting Backup Monitoring ==="
    
    local total_errors=0
    
    # Check S3 access first
    if ! check_s3_access; then
        log "Cannot proceed without S3 access"
        exit 1
    fi
    
    # Check each backup component
    for component in "postgres:PostgreSQL" "redis:Redis" "media:Media" "config:Config"; do
        IFS=':' read -r prefix name <<< "$component"
        
        check_backup_age "$name" "$prefix" || ((total_errors++))
        check_backup_size "$name" "$prefix" || ((total_errors++))
        check_backup_integrity "$name" "$prefix" || ((total_errors++))
    done
    
    # Check system resources
    check_disk_space
    check_backup_process
    
    # Generate report
    generate_report
    
    # Send summary metric
    if [ ! -z "${PROMETHEUS_PUSHGATEWAY:-}" ]; then
        cat <<EOF | curl --data-binary @- ${PROMETHEUS_PUSHGATEWAY}/metrics/job/backup_monitor
# TYPE backup_monitor_errors gauge
backup_monitor_errors $total_errors
# TYPE backup_monitor_last_run gauge
backup_monitor_last_run $(date +%s)
EOF
    fi
    
    if [ $total_errors -eq 0 ]; then
        log "=== Backup monitoring completed successfully ==="
    else
        log "=== Backup monitoring completed with $total_errors errors ==="
        send_alert "WARNING" "Monitor Summary" "Monitoring completed with $total_errors errors"
    fi
    
    exit $total_errors
}

# Run main function
main

exit 0