# AgencyDark Disaster Recovery Guide

This guide provides comprehensive procedures for recovering the AgencyDark system in various disaster scenarios.

## Table of Contents
1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [Recovery Scenarios](#recovery-scenarios)
4. [Step-by-Step Recovery Procedures](#step-by-step-recovery-procedures)
5. [Testing and Validation](#testing-and-validation)
6. [Emergency Contacts](#emergency-contacts)

## Overview

### Recovery Time Objectives (RTO)
- **Critical Services**: 2 hours
- **Full System**: 4 hours
- **Historical Data**: 24 hours

### Recovery Point Objectives (RPO)
- **Database**: 1 hour (hourly backups)
- **Media Files**: 24 hours (daily sync)
- **Configuration**: Real-time (version control)

### Backup Components
1. **PostgreSQL Database**: Complete database dumps
2. **Redis Cache**: Persistent RDB snapshots
3. **Media Files**: User uploads and generated content
4. **Configuration**: Environment files and settings
5. **Application Code**: Git repository

## Backup Strategy

### Automated Backups
```bash
# Backup Schedule (crontab)
0 * * * *     /opt/agencydark/scripts/backup.sh          # Hourly database
0 3 * * *     /opt/agencydark/scripts/backup.sh --full   # Daily full backup
0 4 * * 0     /opt/agencydark/scripts/backup.sh --weekly # Weekly archive
```

### Backup Locations
- **Primary**: AWS S3 (us-east-1)
- **Secondary**: AWS S3 (eu-west-1) - Cross-region replication
- **Tertiary**: On-premise NAS (optional)

### Retention Policy
- **Hourly backups**: 24 hours
- **Daily backups**: 30 days
- **Weekly backups**: 12 weeks
- **Monthly backups**: 12 months

## Recovery Scenarios

### 1. Database Corruption
**Symptoms**: Application errors, data inconsistencies, failed queries

**Recovery Steps**:
```bash
# 1. Stop application
sudo systemctl stop agencydark

# 2. Restore latest database backup
./scripts/restore.sh --restore-postgres postgres_agencydark_prod_20231125_030000.sql.gz

# 3. Verify and start application
./scripts/restore.sh --verify
sudo systemctl start agencydark
```

### 2. Complete Server Failure
**Symptoms**: Server unreachable, hardware failure, catastrophic error

**Recovery Steps**:
1. Provision new server
2. Run initial setup:
```bash
# Clone repository
git clone https://github.com/agencydark/backend.git
cd backend

# Run setup script
./scripts/setup_production.sh

# Restore from latest backup
./scripts/restore.sh --restore-all 20231125_030000
```

### 3. Data Center Outage
**Symptoms**: Region-wide AWS outage

**Recovery Steps**:
1. Activate DR site in alternate region
2. Update DNS to point to DR site
3. Restore from cross-region replicated backups

### 4. Ransomware/Security Breach
**Symptoms**: Encrypted files, suspicious activity, compromised data

**Recovery Steps**:
1. Isolate affected systems
2. Identify clean backup before breach
3. Rebuild infrastructure from scratch
4. Restore from verified clean backup
5. Reset all credentials and API keys

### 5. Accidental Data Deletion
**Symptoms**: Missing records, deleted user data

**Recovery Steps**:
```bash
# For specific table restoration
./scripts/restore.sh --restore-postgres backup.sql.gz data-only

# For point-in-time recovery
pg_restore --table=users --data-only backup.sql
```

## Step-by-Step Recovery Procedures

### Prerequisites Check
```bash
#!/bin/bash
# Run this first to ensure recovery environment is ready

# Check required tools
for tool in aws psql redis-cli docker; do
    which $tool || echo "Missing: $tool"
done

# Verify AWS credentials
aws s3 ls s3://agencydark-backups/ || echo "AWS access failed"

# Check disk space
df -h | grep -E "/$|/opt"
```

### Full System Recovery

#### 1. Infrastructure Setup
```bash
# Create application user
sudo useradd -m -s /bin/bash agencydark
sudo mkdir -p /opt/agencydark
sudo chown agencydark:agencydark /opt/agencydark

# Install dependencies
sudo apt update
sudo apt install -y python3.11 postgresql-client redis-tools nginx
```

#### 2. Database Recovery
```bash
# Create database
sudo -u postgres createdb agencydark_prod
sudo -u postgres createuser agencydark_user

# Restore database
./scripts/restore.sh --restore-postgres postgres_agencydark_prod_TIMESTAMP.sql.gz

# Verify restoration
psql -U agencydark_user -d agencydark_prod -c "SELECT COUNT(*) FROM users;"
```

#### 3. Application Deployment
```bash
# Deploy application
cd /opt/agencydark
git clone https://github.com/agencydark/backend.git
cd backend

# Setup Python environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Restore configuration
./scripts/restore.sh --restore-config config_TIMESTAMP.tar.gz
cp /opt/agencydark/config_restore/.env.production .

# Run migrations
alembic upgrade head
```

#### 4. Media Files Recovery
```bash
# Restore media files
./scripts/restore.sh --restore-media media_TIMESTAMP.tar.gz

# Verify media files
find /opt/agencydark/uploads -type f | wc -l
```

#### 5. Service Startup
```bash
# Start services in order
sudo systemctl start postgresql
sudo systemctl start redis
sudo systemctl start agencydark
sudo systemctl start agencydark-celery
sudo systemctl start nginx

# Verify all services
sudo systemctl status agencydark
curl http://localhost:8000/health
```

### Partial Recovery Procedures

#### Database Table Recovery
```bash
# Extract specific table
pg_restore -t users -d temp_db backup.sql

# Copy to production
pg_dump -t users temp_db | psql agencydark_prod
```

#### Redis Cache Recovery
```bash
# Stop Redis
sudo systemctl stop redis

# Restore RDB file
sudo cp /backup/redis_TIMESTAMP.rdb /var/lib/redis/dump.rdb
sudo chown redis:redis /var/lib/redis/dump.rdb

# Start Redis
sudo systemctl start redis
```

#### Configuration Recovery
```bash
# List available config backups
aws s3 ls s3://agencydark-backups/config/

# Download specific config
aws s3 cp s3://agencydark-backups/config/config_TIMESTAMP.tar.gz .

# Extract and review
tar -xzf config_TIMESTAMP.tar.gz
diff .env.production config_backup/.env.production
```

## Testing and Validation

### Post-Recovery Checklist
- [ ] Database connectivity test
- [ ] Redis connectivity test
- [ ] API health check passes
- [ ] Authentication works
- [ ] Critical endpoints respond
- [ ] Background jobs processing
- [ ] Media files accessible
- [ ] WebSocket connections work
- [ ] Email notifications sending
- [ ] Monitoring alerts active

### Automated Validation Script
```bash
#!/bin/bash
# save as validate_recovery.sh

echo "=== AgencyDark Recovery Validation ==="

# Database check
echo -n "Database: "
PGPASSWORD=$DB_PASSWORD psql -h localhost -U agencydark_user -d agencydark_prod -c "SELECT NOW();" &>/dev/null && echo "OK" || echo "FAILED"

# Redis check
echo -n "Redis: "
redis-cli ping &>/dev/null && echo "OK" || echo "FAILED"

# API check
echo -n "API Health: "
curl -s http://localhost:8000/health | grep -q "healthy" && echo "OK" || echo "FAILED"

# Critical endpoints
for endpoint in auth/login users agencies models; do
    echo -n "Endpoint /$endpoint: "
    status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/$endpoint)
    [ "$status" != "500" ] && echo "OK ($status)" || echo "FAILED ($status)"
done

# Count records
echo -e "\n=== Database Statistics ==="
for table in users agencies models subscribers transactions; do
    count=$(PGPASSWORD=$DB_PASSWORD psql -t -h localhost -U agencydark_user -d agencydark_prod -c "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "0")
    echo "$table: $count records"
done
```

### Recovery Time Tracking
```bash
# Log recovery milestones
echo "$(date): Recovery started" >> recovery.log
echo "$(date): Database restored" >> recovery.log
echo "$(date): Application deployed" >> recovery.log
echo "$(date): Services started" >> recovery.log
echo "$(date): Validation completed" >> recovery.log

# Calculate total recovery time
start=$(head -1 recovery.log | cut -d: -f1-3)
end=$(tail -1 recovery.log | cut -d: -f1-3)
echo "Total recovery time: $(($(date -d "$end" +%s) - $(date -d "$start" +%s))) seconds"
```

## Disaster Recovery Testing

### Monthly DR Drill
1. **Notification**: Alert team of scheduled DR test
2. **Backup Verification**: Ensure recent backups exist
3. **Recovery Execution**: Perform recovery to test environment
4. **Validation**: Run all validation scripts
5. **Documentation**: Update procedures based on findings

### Test Scenarios
- [ ] Database recovery only
- [ ] Full system recovery
- [ ] Cross-region failover
- [ ] Point-in-time recovery
- [ ] Partial data restoration

## Emergency Contacts

### Primary Contacts
- **Infrastructure Lead**: +1-XXX-XXX-XXXX
- **Database Administrator**: +1-XXX-XXX-XXXX
- **Security Officer**: +1-XXX-XXX-XXXX

### Vendor Support
- **AWS Support**: [Premium Support Portal]
- **PostgreSQL Support**: support@postgresql.org
- **Application Support**: support@agencydark.com

### Escalation Path
1. On-call Engineer
2. Team Lead
3. CTO
4. External Consultants

## Recovery Command Reference

### Quick Commands
```bash
# List all backups
./scripts/restore.sh --list

# Restore everything from timestamp
./scripts/restore.sh --restore-all 20231125_030000

# Restore database only
./scripts/restore.sh --restore-postgres postgres_agencydark_prod_20231125_030000.sql.gz

# Verify system
./scripts/restore.sh --verify

# Interactive restoration
./scripts/restore.sh
```

### AWS S3 Commands
```bash
# List backups
aws s3 ls s3://agencydark-backups/ --recursive

# Download backup
aws s3 cp s3://agencydark-backups/postgres/backup.sql.gz .

# Sync media files
aws s3 sync s3://agencydark-backups/media/ /opt/agencydark/uploads/
```

### PostgreSQL Commands
```bash
# Backup current database
pg_dump -h localhost -U agencydark_user agencydark_prod | gzip > emergency_backup.sql.gz

# Restore with progress
pv backup.sql.gz | gunzip | psql -h localhost -U agencydark_user agencydark_prod

# Check database size
psql -U agencydark_user -d agencydark_prod -c "SELECT pg_database_size('agencydark_prod');"
```

## Notes and Best Practices

1. **Always verify backups** before starting recovery
2. **Document every step** during actual recovery
3. **Test recovery procedures** regularly
4. **Keep credentials secure** and updated
5. **Monitor backup success** rates
6. **Maintain multiple backup copies**
7. **Practice recovery scenarios** monthly
8. **Update this guide** after each incident

---
*Last Updated: November 2023*
*Version: 1.0*