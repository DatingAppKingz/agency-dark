#!/usr/bin/env python3
"""
Fix all migration revision references to use numeric format only.
"""
import os
import re
from pathlib import Path

def fix_migration_file(filepath):
    """Fix revision references in a single migration file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Extract the numeric part from the filename
    filename = os.path.basename(filepath)
    match = re.match(r'^(\d{3})_', filename)
    if not match:
        print(f"Skipping {filename} - doesn't follow naming convention")
        return
    
    file_number = match.group(1)
    
    # Fix revision identifier
    content = re.sub(
        r"revision = '[^']*'",
        f"revision = '{file_number}'",
        content
    )
    
    # Fix down_revision references with full names (e.g., '022_add_comprehensive_multi_tenant_indexes')
    content = re.sub(
        r"down_revision = '(\d{3})_[^']*'",
        r"down_revision = '\1'",
        content
    )
    
    # For 001, ensure down_revision is None
    if file_number == '001':
        content = re.sub(
            r"down_revision = '[^']*'",
            "down_revision = None",
            content
        )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Fixed {filename}")

def main():
    """Fix all migration files in the versions directory."""
    versions_dir = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Get all Python files that follow the numbering convention
    migration_files = sorted([
        f for f in versions_dir.glob('*.py')
        if re.match(r'^\d{3}_.*\.py$', f.name)
    ])
    
    print(f"Found {len(migration_files)} migration files to fix")
    
    for filepath in migration_files:
        fix_migration_file(filepath)
    
    print("\nAll migrations fixed!")

if __name__ == '__main__':
    main()