#!/usr/bin/env python3
"""
Fix all remaining migration issues comprehensively.
"""
import os
import re
from pathlib import Path

def remove_duplicate_enum_creation(content):
    """Remove duplicate raw CREATE TYPE statements."""
    
    # Find all CREATE TYPE statements
    create_type_pattern = r'op\.execute\s*\(\s*["\']CREATE TYPE\s+(\w+)[^"\']+["\']\s*\)'
    
    # Remove them if they appear after enum check blocks
    lines = content.split('\n')
    new_lines = []
    skip_next_create_type = False
    
    for i, line in enumerate(lines):
        # Check if we just had an enum check
        if 'if not result.fetchone():' in line:
            # Look ahead for CREATE TYPE in next few lines
            for j in range(i+1, min(i+5, len(lines))):
                if 'CREATE TYPE' in lines[j] and 'connection.execute' in lines[j]:
                    skip_next_create_type = True
                    break
        
        # Skip raw op.execute CREATE TYPE lines
        if re.search(r'^\s*op\.execute\s*\(\s*["\']CREATE TYPE', line):
            continue
            
        new_lines.append(line)
    
    return '\n'.join(new_lines)

def fix_all_issues(content):
    """Apply all fixes to a migration file."""
    
    # 1. Remove duplicate enum creations
    content = remove_duplicate_enum_creation(content)
    
    # 2. Fix JSON to JSONB for GIN indexes
    if 'postgresql_using=\'gin\'' in content:
        content = content.replace('sa.JSON()', 'postgresql.JSONB()')
    
    # 3. Ensure all ENUMs use create_type=False
    def add_create_type_false(match):
        enum_def = match.group(0)
        if 'create_type=' not in enum_def:
            return enum_def[:-1] + ', create_type=False)'
        return enum_def
    
    content = re.sub(r'postgresql\.ENUM\([^)]+\)', add_create_type_false, content)
    
    # 4. Replace remaining sa.Enum with postgresql.ENUM
    content = re.sub(r'\bsa\.Enum\(', 'postgresql.ENUM(', content)
    
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
        content = fix_all_issues(content)
        
        if content != original_content:
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"✓ Fixed {filepath.name}")
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} migration files!")

if __name__ == '__main__':
    main()