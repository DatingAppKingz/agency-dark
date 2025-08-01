#!/usr/bin/env python3
"""
Fix all VARCHAR columns that should be UUID in migrations.
This includes primary keys, foreign keys, and any ID columns.
"""
import os
import re
from pathlib import Path

def fix_varchar_to_uuid(content):
    """Replace VARCHAR with UUID for all ID columns."""
    
    # Fix column definitions - match any ID column that uses sa.String() or VARCHAR
    # Pattern 1: sa.Column('xxx_id', sa.String(), ...)
    content = re.sub(
        r"sa\.Column\((['\"][^'\"]*(?:_id|Id)['\"])\s*,\s*sa\.String\(\)[^)]*\)",
        lambda m: m.group(0).replace('sa.String()', 'postgresql.UUID(as_uuid=True)'),
        content
    )
    
    # Pattern 2: Direct VARCHAR usage in CREATE TABLE statements
    content = re.sub(
        r"(\w+_id|id)\s+VARCHAR",
        r"\1 UUID",
        content,
        flags=re.IGNORECASE
    )
    
    # Pattern 3: layout_id, widget_id, etc. that are used as foreign keys
    special_id_columns = [
        'layout_id', 'widget_id', 'dashboard_id', 'report_id', 'template_id',
        'experiment_id', 'variant_id', 'participant_id', 'event_id',
        'webhook_id', 'schedule_id', 'execution_id', 'source_id', 'target_id'
    ]
    
    for col in special_id_columns:
        # Fix sa.Column definitions
        pattern = rf"sa\.Column\(['\"]({col})['\"],\s*sa\.String\(\)"
        replacement = rf"sa.Column('\1', postgresql.UUID(as_uuid=True)"
        content = re.sub(pattern, replacement, content)
    
    # Ensure postgresql is imported if UUID is used
    if 'postgresql.UUID' in content and 'from sqlalchemy.dialects import postgresql' not in content:
        # Add import after other imports
        import_pattern = r"(from alembic import op\nimport sqlalchemy as sa)"
        replacement = r"\1\nfrom sqlalchemy.dialects import postgresql"
        content = re.sub(import_pattern, replacement, content)
    
    return content

def main():
    """Fix all migration files."""
    versions_dir = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Process all migration files
    migration_files = sorted([
        f for f in versions_dir.glob('*.py')
        if re.match(r'^(\d{3})_.*\.py$', f.name)
    ])
    
    print(f"Processing {len(migration_files)} migration files...")
    
    fixed_count = 0
    for filepath in migration_files:
        with open(filepath, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Apply fixes
        content = fix_varchar_to_uuid(content)
        
        if content != original_content:
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"✓ Fixed {filepath.name}")
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} migration files!")

if __name__ == '__main__':
    main()