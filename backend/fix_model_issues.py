#!/usr/bin/env python3
"""Fix SQLAlchemy metadata and Pydantic regex issues."""

import os
import re
import sys
from pathlib import Path

def fix_metadata_columns(file_path):
    """Fix metadata column names in SQLAlchemy models."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Only fix simple metadata column declarations, not compound names
    # This pattern matches: metadata = Column(...) but not transaction_metadata = Column(...)
    pattern = r'^(\s*)metadata\s*=\s*Column\('
    replacement = r'\1extra_metadata = Column('
    
    lines = content.split('\n')
    new_lines = []
    
    for line in lines:
        if re.match(pattern, line):
            new_line = re.sub(pattern, replacement, line)
            new_lines.append(new_line)
            print(f"Fixed metadata column in {file_path}")
        else:
            new_lines.append(line)
    
    new_content = '\n'.join(new_lines)
    
    if new_content != original_content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        return True
    return False

def fix_pydantic_regex(file_path):
    """Fix deprecated regex parameter in Pydantic fields."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Replace regex= with pattern=
    content = re.sub(r'\bregex\s*=', 'pattern=', content)
    
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed pydantic regex in {file_path}")
        return True
    return False

def main():
    backend_dir = Path(__file__).parent
    
    # Files with metadata columns to fix
    metadata_files = [
        "services/sync/delta_sync.py",
        "core/domain/api_key_models.py",
        "core/security/audit_logging.py",
        "services/api_audit_logger.py",
        "core/audit.py",
        "models/external_api.py",
        "models/notification.py",
        "models/media.py",
        "modules/ab_testing/domain/models.py",
        "modules/notifications/models.py",
        "modules/financial/domain/models.py",
        "api/v1/endpoints/media_upload_advanced.py"
    ]
    
    # Files with pydantic regex to fix
    pydantic_files = [
        "schemas/pagination.py",
        "schemas/notification.py",
        "schemas/tasks.py",
        "schemas/media.py",
        "api/v1/mobile/analytics.py",
        "api/v1/experiments.py",
        "api/v1/endpoints/push_notifications.py",
        "api/v1/endpoints/api_usage.py",
        "api/v1/endpoints/chat.py",
        "api/v1/endpoints/sync_error_monitoring.py",
        "core/documentation/schemas.py",
        "api/v1/endpoints/conversations.py",
        "api/v1/endpoints/ml_insights_advanced.py",
        "api/v1/endpoints/models.py",
        "api/v1/endpoints/translations.py",
        "api/v1/endpoints/tasks.py",
        "api/v1/endpoints/analytics.py",
        "api/v1/endpoints/media.py",
        "api/v1/endpoints/sync_dashboard.py",
        "api/v1/endpoints/search.py",
        "api/v1/analytics_dashboard.py"
    ]
    
    print("Fixing SQLAlchemy metadata columns...")
    for file_path in metadata_files:
        full_path = backend_dir / file_path
        if full_path.exists():
            fix_metadata_columns(full_path)
    
    print("\nFixing Pydantic regex parameters...")
    for file_path in pydantic_files:
        full_path = backend_dir / file_path
        if full_path.exists():
            fix_pydantic_regex(full_path)
    
    print("\nDone!")

if __name__ == "__main__":
    main()