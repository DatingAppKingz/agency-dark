#!/usr/bin/env python3
"""
Fix migration 028 - handle duplicate api_keys table.
"""
from pathlib import Path

def fix_migration_028():
    """Fix migration 028 to check if api_keys table exists."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '028_create_api_keys_table.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # First fix the ID columns to use UUID
    content = content.replace(
        "sa.Column('id', sa.Integer(), nullable=False),",
        "sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),"
    )
    
    content = content.replace(
        "sa.Column('api_key_id', sa.Integer(), nullable=False),",
        "sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=False),"
    )
    
    # Replace the api_keys table creation with existence check
    old_section = """    # Create api_keys table
    op.create_table('api_keys',"""
    
    new_section = """    # Create api_keys table (if not exists)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_keys')"
    ))
    if not result.scalar():
        op.create_table('api_keys',"""
    
    content = content.replace(old_section, new_section)
    
    # Find where to close the if statement (after the create_table and indexes)
    lines = content.split('\n')
    new_lines = []
    found_api_keys_table = False
    indent_level = 0
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        if "if not result.scalar():" in line and "api_keys" in lines[i-2]:
            found_api_keys_table = True
            indent_level = len(line) - len(line.lstrip())
        
        if found_api_keys_table:
            # Check if we're at the end of the table and index creation
            if i+1 < len(lines) and line.strip() and (
                "Create api_key_usage table" in lines[i+1] or 
                "op.create_table('api_key_usage'" in lines[i+1]
            ):
                # Close the if block
                found_api_keys_table = False
    
    content = '\n'.join(new_lines)
    
    # Fix the index creation to be conditional too
    content = content.replace(
        """    # Create indexes
    op.create_index('idx_api_keys_agency_provider', 'api_keys', ['agency_id', 'provider'])
    op.create_index('idx_api_keys_status', 'api_keys', ['status'])
    op.create_index('idx_api_keys_expires_at', 'api_keys', ['expires_at'], postgresql_where=sa.text("expires_at IS NOT NULL"))""",
        """        # Create indexes
        op.create_index('idx_api_keys_agency_provider', 'api_keys', ['agency_id', 'provider'])
        op.create_index('idx_api_keys_status', 'api_keys', ['status'])
        op.create_index('idx_api_keys_expires_at', 'api_keys', ['expires_at'], postgresql_where=sa.text("expires_at IS NOT NULL"))"""
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 028 to check table existence and use UUIDs")

if __name__ == '__main__':
    fix_migration_028()