#!/usr/bin/env python3
"""
Fix ENUM type creation issues in migrations by adding existence checks.
"""
import os
import re
from pathlib import Path

def fix_enum_creation(content):
    """Fix ENUM creation to check for existence first."""
    
    # Pattern to find ENUM type creation
    enum_pattern = r"sa\.Enum\(([^)]+)\)"
    
    # Find all ENUM creations
    enums = re.findall(enum_pattern, content)
    
    # Extract unique enum names
    enum_names = set()
    for enum_def in enums:
        # Look for name parameter
        name_match = re.search(r"name=['\"](\w+)['\"]", enum_def)
        if name_match:
            enum_names.add(name_match.group(1))
    
    if not enum_names:
        return content
    
    # Add enum creation with checks at the beginning of upgrade()
    enum_checks = []
    for enum_name in sorted(enum_names):
        # Find the enum values
        for enum_def in enums:
            if f"name='{enum_name}'" in enum_def or f'name="{enum_name}"' in enum_def:
                # Extract values
                values_match = re.findall(r"['\"]([^'\"]+)['\"]", enum_def.split("name=")[0])
                if values_match:
                    values_str = ", ".join(f"'{v}'" for v in values_match)
                    enum_checks.append(f"""
    # Check and create {enum_name} enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = '{enum_name}'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE {enum_name} AS ENUM ({values_str})"))""")
                    break
    
    if enum_checks:
        # Find the upgrade function and add checks after the docstring
        upgrade_pattern = r"(def upgrade\(\)[^:]*:\s*(?:\"\"\"[^\"]*\"\"\")?\s*)"
        
        def replacement(match):
            return match.group(1) + "\n".join(enum_checks) + "\n    "
        
        content = re.sub(upgrade_pattern, replacement, content)
        
        # Change all Enum usages to use create_type=False
        content = re.sub(
            r"(sa\.Enum\([^)]+name=['\"](\w+)['\"][^)]*)\)",
            r"\1, create_type=False)",
            content
        )
        
        # If postgresql.ENUM is used, ensure create_type=False
        content = re.sub(
            r"(postgresql\.ENUM\([^)]+name=['\"](\w+)['\"][^)]*)\)",
            lambda m: m.group(0) if "create_type=False" in m.group(0) else m.group(1) + ", create_type=False)",
            content
        )
    
    return content

def main():
    """Fix all migration files with ENUM issues."""
    versions_dir = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Process migrations 012 onwards
    migration_files = sorted([
        f for f in versions_dir.glob('*.py')
        if re.match(r'^(\d{3})_.*\.py$', f.name) and int(f.name[:3]) >= 12
    ])
    
    print(f"Processing {len(migration_files)} migration files...")
    
    for filepath in migration_files:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Skip if no Enum usage
        if 'sa.Enum(' not in content and 'postgresql.ENUM(' not in content:
            continue
            
        print(f"Fixing {filepath.name}...")
        fixed_content = fix_enum_creation(content)
        
        if fixed_content != content:
            with open(filepath, 'w') as f:
                f.write(fixed_content)
            print(f"  ✓ Fixed ENUM creation")
        else:
            print(f"  - No changes needed")

if __name__ == '__main__':
    main()