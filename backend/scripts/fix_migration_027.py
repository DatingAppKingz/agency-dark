#!/usr/bin/env python3
"""
Fix migration 027 - check if commission_rules table exists before creating.
"""
from pathlib import Path

def fix_migration_027():
    """Fix migration 027 to check if commission_rules table exists and fix ID types."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '027_add_commission_tracking.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # First fix all INTEGER IDs to UUIDs
    replacements = [
        ("sa.Column('id', sa.Integer(), nullable=False),", 
         "sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),"),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    # Replace the commission_rules table creation with existence check
    old_commission_rules_section = """    # Create commission_rules table for custom commission structures
    op.create_table('commission_rules',"""
    
    new_commission_rules_section = """    # Create commission_rules table for custom commission structures (if not exists)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'commission_rules')"
    ))
    if not result.scalar():
        op.create_table('commission_rules',"""
    
    content = content.replace(old_commission_rules_section, new_commission_rules_section)
    
    # Add closing brace for the if statement after the create_table
    lines = content.split('\n')
    new_lines = []
    found_create_table = False
    brace_count = 0
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        if "if not result.scalar():" in line and "commission_rules" in lines[i-2]:
            found_create_table = True
            brace_count = 0
        
        if found_create_table:
            # Count parentheses to find the end of create_table
            brace_count += line.count('(') - line.count(')')
            
            # When we close all parentheses and it's the end of create_table
            if brace_count == 0 and ')' in line and 'sa.Column' not in lines[i+1] if i+1 < len(lines) else True:
                found_create_table = False
                # Add proper indentation for the index creation
                if i+1 < len(lines) and 'create_index' in lines[i+1]:
                    # The index creation should also be inside the if block
                    continue
    
    # Also need to fix the index creation to be conditional
    content = '\n'.join(new_lines)
    content = content.replace(
        "    # Create index for active rules lookup\n    op.create_index('idx_commission_rules_active', 'commission_rules', ['agency_id', 'is_active'])",
        "        # Create index for active rules lookup\n        op.create_index('idx_commission_rules_active', 'commission_rules', ['agency_id', 'is_active'])"
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 027 to check table existence")

if __name__ == '__main__':
    fix_migration_027()