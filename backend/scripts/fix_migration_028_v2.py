#!/usr/bin/env python3
"""
Fix migration 028 - handle duplicate tables comprehensively.
"""
from pathlib import Path

def fix_migration_028():
    """Fix migration 028 to check if tables exist."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '028_create_api_keys_table.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Fix the api_key_audit_logs table creation to check existence
    content = content.replace(
        """    # Create api_key_audit_logs table
    op.create_table('api_key_audit_logs',""",
        """    # Create api_key_audit_logs table (if not exists)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_key_audit_logs')"
    ))
    if not result.scalar():
        op.create_table('api_key_audit_logs',"""
    )
    
    # Fix the index creation for api_key_audit_logs to be conditional
    content = content.replace(
        """    # Create index for audit log queries
    op.create_index('idx_api_key_audit_key_created', 'api_key_audit_logs', ['api_key_id', 'created_at'])
    op.create_index('idx_api_key_audit_action', 'api_key_audit_logs', ['action'])""",
        """        # Create index for audit log queries
        op.create_index('idx_api_key_audit_key_created', 'api_key_audit_logs', ['api_key_id', 'created_at'])
        op.create_index('idx_api_key_audit_action', 'api_key_audit_logs', ['action'])"""
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 028 to check api_key_audit_logs table existence")

if __name__ == '__main__':
    fix_migration_028()