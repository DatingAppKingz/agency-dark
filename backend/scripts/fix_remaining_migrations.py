#!/usr/bin/env python3
"""
Fix all remaining migration issues in one go.
"""
from pathlib import Path
import re

def fix_migration_032():
    """Fix migration 032 - duplicate api_key_audit_logs table."""
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '032_add_api_key_audit_logs.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Fix ID columns to UUID
    content = content.replace(
        "sa.Column('id', sa.Integer(), nullable=False),",
        "sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),"
    )
    
    # Check if table exists before creating
    content = content.replace(
        """    # Create audit logs table
    op.create_table('api_key_audit_logs',""",
        """    # Create audit logs table (if not exists)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_key_audit_logs')"
    ))
    if not result.scalar():
        op.create_table('api_key_audit_logs',"""
    )
    
    # Fix the indexes to be conditional
    content = content.replace(
        """    # Create indexes
    op.create_index('idx_api_key_audit_logs_api_key', 'api_key_audit_logs', ['api_key_id'])
    op.create_index('idx_api_key_audit_logs_agency', 'api_key_audit_logs', ['agency_id'])
    op.create_index('idx_api_key_audit_logs_action', 'api_key_audit_logs', ['action'])
    op.create_index('idx_api_key_audit_logs_created', 'api_key_audit_logs', ['created_at'])
    op.create_index('idx_api_key_audit_logs_request_id', 'api_key_audit_logs', ['request_id'])""",
        """        # Create indexes
        op.create_index('idx_api_key_audit_logs_api_key', 'api_key_audit_logs', ['api_key_id'])
        op.create_index('idx_api_key_audit_logs_agency', 'api_key_audit_logs', ['agency_id'])
        op.create_index('idx_api_key_audit_logs_action', 'api_key_audit_logs', ['action'])
        op.create_index('idx_api_key_audit_logs_created', 'api_key_audit_logs', ['created_at'])
        op.create_index('idx_api_key_audit_logs_request_id', 'api_key_audit_logs', ['request_id'])"""
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 032")

def fix_all_remaining_integer_ids():
    """Fix all remaining migrations that use INTEGER instead of UUID for IDs."""
    migrations_path = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # List of migrations to check
    migrations_to_check = [
        '030_add_delta_sync_trackers.py',
        '031_add_sync_fields_to_api_keys.py',
        '033_add_task_results_table.py',
        '034_fix_chat_tables_structure.py',
        '035_create_chat_system_simple.py',
        '036_add_translation_tables.py',
        '037_notifications.py',
        '038_saved_searches.py'
    ]
    
    for migration_file in migrations_to_check:
        filepath = migrations_path / migration_file
        if not filepath.exists():
            continue
            
        with open(filepath, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Replace INTEGER IDs with UUIDs
        replacements = [
            # Primary keys
            (r"sa\.Column\('id', sa\.Integer\(\), nullable=False\)",
             "sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False)"),
            
            # Foreign keys - various patterns
            (r"sa\.Column\('(\w+_id)', sa\.Integer\(\), nullable=(True|False)\)",
             r"sa.Column('\1', postgresql.UUID(as_uuid=True), nullable=\2)"),
        ]
        
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)
        
        if content != original_content:
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"Fixed INTEGER to UUID in {migration_file}")

def check_duplicate_tables():
    """Check for potential duplicate table creations in remaining migrations."""
    migrations_path = Path(__file__).parent.parent / 'alembic' / 'versions'
    
    # Tables that might be duplicated
    tables_to_check = [
        'chat_conversations',
        'chat_messages',
        'notifications',
        'task_results',
        'translations',
        'saved_searches',
        'delta_sync_trackers'
    ]
    
    # Find which migrations create which tables
    table_migrations = {}
    
    for migration_file in sorted(migrations_path.glob('*.py')):
        if migration_file.name == '__pycache__':
            continue
            
        with open(migration_file, 'r') as f:
            content = f.read()
        
        for table in tables_to_check:
            if f"op.create_table('{table}'," in content:
                if table not in table_migrations:
                    table_migrations[table] = []
                table_migrations[table].append(migration_file.name)
    
    # Report duplicates
    for table, migrations in table_migrations.items():
        if len(migrations) > 1:
            print(f"\nWARNING: Table '{table}' is created in multiple migrations:")
            for m in migrations:
                print(f"  - {m}")

if __name__ == '__main__':
    print("Fixing remaining migration issues...")
    fix_migration_032()
    fix_all_remaining_integer_ids()
    check_duplicate_tables()
    print("\nDone!")