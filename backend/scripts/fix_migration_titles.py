#!/usr/bin/env python3
"""
Fix migration titles to avoid confusing Alembic.
"""
import os
import re
from pathlib import Path

def fix_migration_title(filepath):
    """Fix migration title to avoid arrow notation."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Fix the first line (title)
    if lines and '->' in lines[0]:
        # Remove anything that looks like a revision chain
        lines[0] = re.sub(r'\s*->\s*[^,\n]+', '', lines[0])
    
    with open(filepath, 'w') as f:
        f.writelines(lines)

def main():
    """Fix all migration files."""
    versions_dir = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Get all Python files that follow the numbering convention
    migration_files = sorted([
        f for f in versions_dir.glob('*.py')
        if re.match(r'^\d{3}_.*\.py$', f.name)
    ])
    
    print(f"Fixing titles in {len(migration_files)} migration files")
    
    for filepath in migration_files:
        fix_migration_title(filepath)
        print(f"Fixed {os.path.basename(filepath)}")

if __name__ == '__main__':
    main()