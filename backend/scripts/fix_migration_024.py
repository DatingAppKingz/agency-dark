#!/usr/bin/env python3
"""
Fix migration 024 - change INTEGER to UUID for all ID and foreign key columns.
"""
from pathlib import Path

def fix_migration_024():
    """Fix migration 024 to use UUID instead of INTEGER for IDs."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '024_add_missing_financial_tables.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace all INTEGER IDs with UUIDs
    replacements = [
        # Primary keys
        ("sa.Column('id', sa.Integer(), nullable=False),", 
         "sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),"),
        
        # Foreign keys
        ("sa.Column('agency_id', sa.Integer(), nullable=False),", 
         "sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),"),
        
        ("sa.Column('model_id', sa.Integer(), nullable=False),", 
         "sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),"),
        
        ("sa.Column('user_id', sa.Integer(), nullable=False),", 
         "sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),"),
        
        ("sa.Column('approved_by', sa.Integer(), nullable=True),", 
         "sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),"),
        
        ("sa.Column('agency_id', sa.Integer(), nullable=True),", 
         "sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),"),
    ]
    
    for old, new in replacements:
        content = content.replace(old, new)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 024 to use UUID instead of INTEGER")

if __name__ == '__main__':
    fix_migration_024()