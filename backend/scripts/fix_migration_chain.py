#!/usr/bin/env python3
"""
Fix the migration chain by setting proper down_revision values.
"""
import os
import re
from pathlib import Path

def fix_migration_chain():
    """Fix the down_revision values for all migrations."""
    versions_dir = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Get all Python files that follow the numbering convention
    migration_files = sorted([
        f for f in versions_dir.glob('*.py')
        if re.match(r'^\d{3}_.*\.py$', f.name)
    ])
    
    print(f"Found {len(migration_files)} migration files to fix")
    
    for i, filepath in enumerate(migration_files):
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Extract the numeric part from the filename
        filename = os.path.basename(filepath)
        match = re.match(r'^(\d{3})_', filename)
        if not match:
            continue
        
        file_number = match.group(1)
        
        # Set proper down_revision
        if i == 0:  # First migration
            # Set down_revision to None
            content = re.sub(
                r"down_revision = '[^']*'",
                "down_revision = None",
                content
            )
        else:
            # Set down_revision to previous migration number
            prev_file = migration_files[i-1]
            prev_match = re.match(r'^(\d{3})_', os.path.basename(prev_file))
            if prev_match:
                prev_number = prev_match.group(1)
                content = re.sub(
                    r"down_revision = '[^']*'",
                    f"down_revision = '{prev_number}'",
                    content
                )
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        print(f"Fixed {filename}: revision={file_number}, down_revision={'None' if i == 0 else prev_number}")

if __name__ == '__main__':
    fix_migration_chain()