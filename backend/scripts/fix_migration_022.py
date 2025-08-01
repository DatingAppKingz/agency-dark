#!/usr/bin/env python3
"""
Fix migration 022 - only create indexes on existing columns.
"""
from pathlib import Path

def fix_migration_022():
    """Fix migration 022 to skip indexes on non-existent columns."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '022_add_comprehensive_multi_tenant_indexes.py'
    
    # Tables that don't have agency_id based on migration 001
    tables_without_agency_id = [
        'sessions',  # only has user_id
        'fans',      # only has model_id  
        'fan_claims', # only has model_id and fan_id
        'model_chatters', # only has model_id and chatter_id
    ]
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Comment out indexes for tables without agency_id
    for table in tables_without_agency_id:
        # Comment out all lines that create indexes on these tables
        lines = content.split('\n')
        new_lines = []
        
        for line in lines:
            if f"'{table}'" in line and 'op.create_index' in line:
                new_lines.append(f"    # SKIP - {table} doesn't have agency_id: {line.strip()}")
            else:
                new_lines.append(line)
        
        content = '\n'.join(new_lines)
    
    # Also check if the tables exist at all
    tables_that_might_not_exist = [
        'financial_transactions',
        'chat_conversations',
        'chat_messages',
        'webhook_logs',
        'fan_profiles'
    ]
    
    for table in tables_that_might_not_exist:
        lines = content.split('\n')
        new_lines = []
        
        for line in lines:
            if f"'{table}'" in line and 'op.create_index' in line:
                new_lines.append(f"    # TODO: Check if {table} exists - {line.strip()}")
            else:
                new_lines.append(line)
        
        content = '\n'.join(new_lines)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 022")

if __name__ == '__main__':
    fix_migration_022()