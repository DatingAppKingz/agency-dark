#!/usr/bin/env python3
"""
Fix migration 029 - handle duplicate webhooks table.
"""
from pathlib import Path

def fix_migration_029():
    """Fix migration 029 to check if webhooks table exists."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '029_create_webhook_tables.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # First fix the ID columns to use UUID
    content = content.replace(
        "sa.Column('id', sa.Integer(), nullable=False),",
        "sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),"
    )
    
    content = content.replace(
        "sa.Column('webhook_id', sa.Integer(), nullable=False),",
        "sa.Column('webhook_id', postgresql.UUID(as_uuid=True), nullable=False),"
    )
    
    # Check if webhooks table exists before creating
    content = content.replace(
        """    # Create webhooks table
    op.create_table('webhooks',""",
        """    # Create webhooks table (if not exists)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'webhooks')"
    ))
    if not result.scalar():
        op.create_table('webhooks',"""
    )
    
    # Fix the create type for webhookevent enum
    content = content.replace(
        """    # Create webhook event enum
    op.execute(\"\"\"
        CREATE TYPE webhookevent AS ENUM (""",
        """    # Create webhook event enum (if not exists)
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'webhookevent'"))
    if not result.fetchone():
        connection.execute(sa.text(\"\"\"
            CREATE TYPE webhookevent AS ENUM ("""
    )
    
    # Close the execute statement properly
    content = content.replace(
        """        )
    \"\"\")""",
        """            )
        \"\"\"))"""
    )
    
    # Fix the webhook indexes to be conditional
    content = content.replace(
        """    # Create indexes
    op.create_index('idx_webhooks_agency', 'webhooks', ['agency_id'])
    op.create_index('idx_webhooks_status', 'webhooks', ['status'])
    op.create_index('idx_webhooks_is_active', 'webhooks', ['is_active'])""",
        """        # Create indexes
        op.create_index('idx_webhooks_agency', 'webhooks', ['agency_id'])
        op.create_index('idx_webhooks_status', 'webhooks', ['status'])
        op.create_index('idx_webhooks_is_active', 'webhooks', ['is_active'])"""
    )
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 029 to check table existence and use UUIDs")

if __name__ == '__main__':
    fix_migration_029()