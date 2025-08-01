#!/usr/bin/env python3
"""
Fix migration Revision ID lines in docstrings to match the numeric convention.
"""
import os
import re
from pathlib import Path

def fix_migration_ids(filepath):
    """Fix Revision ID in migration docstring."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Extract the numeric part from the filename
    filename = os.path.basename(filepath)
    match = re.match(r'^(\d{3})_', filename)
    if not match:
        return
    
    file_number = match.group(1)
    
    # Fix the Revision ID line in the docstring
    content = re.sub(
        r'Revision ID: [^\n]+',
        f'Revision ID: {file_number}',
        content
    )
    
    with open(filepath, 'w') as f:
        f.write(content)

def main():
    """Fix all migration files."""
    versions_dir = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Get all Python files that follow the numbering convention
    migration_files = sorted([
        f for f in versions_dir.glob('*.py')
        if re.match(r'^\d{3}_.*\.py$', f.name)
    ])
    
    print(f"Fixing Revision IDs in {len(migration_files)} migration files")
    
    for filepath in migration_files:
        fix_migration_ids(filepath)
        print(f"Fixed {os.path.basename(filepath)}")

if __name__ == '__main__':
    main()