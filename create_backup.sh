#!/bin/bash
# Comprehensive backup before RBAC fix

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/rbac_fix_${TIMESTAMP}"

echo "Creating backup directory: ${BACKUP_DIR}"
mkdir -p ${BACKUP_DIR}

# 1. Git state backup
echo "Backing up git state..."
git stash list > "${BACKUP_DIR}/git_stash_list.txt"
git branch -a > "${BACKUP_DIR}/git_branches.txt"
git status > "${BACKUP_DIR}/git_status.txt"

# 2. Database backup
echo "Backing up database..."
/opt/homebrew/opt/postgresql@16/bin/pg_dump agencydark_dev > "${BACKUP_DIR}/database_backup.sql" 2>/dev/null || echo "Database backup skipped (may not exist)"

# 3. Redis backup (if running)
echo "Checking Redis..."
redis-cli ping > /dev/null 2>&1 && redis-cli --rdb "${BACKUP_DIR}/redis_backup.rdb" || echo "Redis backup skipped (not running)"

# 4. Configuration files backup
echo "Backing up configuration files..."
cp .env "${BACKUP_DIR}/.env.backup" 2>/dev/null || echo "No .env file found"
cp backend/.env "${BACKUP_DIR}/backend.env.backup" 2>/dev/null || true
cp frontend/.env.local "${BACKUP_DIR}/frontend.env.backup" 2>/dev/null || true

# 5. Current file list
echo "Creating file inventory..."
find . -type f -name "*.py" | grep -E "(security|auth|rbac)" > "${BACKUP_DIR}/security_files.txt"

# 6. Create backup manifest
cat > "${BACKUP_DIR}/manifest.json" << EOF
{
  "timestamp": "${TIMESTAMP}",
  "git_commit": "$(git rev-parse HEAD)",
  "git_branch": "$(git branch --show-current)",
  "database": "agencydark_dev",
  "backed_up_items": [
    "git_state",
    "database (if available)",
    "redis (if running)",
    "configuration_files",
    "security_file_list"
  ]
}
EOF

echo "✅ Backup complete: ${BACKUP_DIR}"
echo "To restore, run: ./restore_backup.sh ${BACKUP_DIR}"