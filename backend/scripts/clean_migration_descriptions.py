#!/usr/bin/env python3
"""
Clean migration descriptions to remove confusing revision references.
"""
import os
import re
from pathlib import Path

def clean_migration_file(filepath):
    """Clean migration description to avoid confusion."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Fix the "Revises:" line in the docstring to match actual down_revision
    revision_match = re.search(r"down_revision = '(\w+)'", content)
    if revision_match:
        down_rev = revision_match.group(1)
        if down_rev != 'None':
            # Update the Revises line to just show the number
            content = re.sub(
                r'Revises: [^\n]+',
                f'Revises: {down_rev}',
                content
            )
        else:
            # For the first migration
            content = re.sub(
                r'Revises: [^\n]+',
                'Revises: ',
                content
            )
    
    with open(filepath, 'w') as f:
        f.write(content)

def main():
    """Clean all migration files."""
    versions_dir = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Get all Python files that follow the numbering convention
    migration_files = sorted([
        f for f in versions_dir.glob('*.py')
        if re.match(r'^\d{3}_.*\.py$', f.name)
    ])
    
    print(f"Cleaning {len(migration_files)} migration files")
    
    for filepath in migration_files:
        clean_migration_file(filepath)
        print(f"Cleaned {os.path.basename(filepath)}")

if __name__ == '__main__':
    main()