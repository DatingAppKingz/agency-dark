#!/usr/bin/env python3
"""
Fix migration 037 - duplicate notifications table.
"""
from pathlib import Path

def fix_migration_037():
    """Fix migration 037 to check if notifications table exists."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '037_notifications.py'
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if table exists before creating
    content = content.replace(
        """    op.create_table('notifications',""",
        """    # Check if notifications table exists (it might have been created in migration 001)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notifications')"
    ))
    if not result.scalar():
        op.create_table('notifications',"""
    )
    
    # Find where the create_table ends and add the closing if
    lines = content.split('\n')
    new_lines = []
    found_create_table = False
    indent_count = 0
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        if "if not result.scalar():" in line and "notifications" in lines[i-2]:
            found_create_table = True
            indent_count = 0
        
        if found_create_table:
            # Count parentheses to find the end of create_table
            indent_count += line.count('(') - line.count(')')
            
            # When we close all parentheses and it's the end of create_table
            if indent_count == 0 and ')' in line and i+1 < len(lines) and 'op.create_' not in lines[i+1]:
                found_create_table = False
                # Check if next line is creating indexes
                if i+1 < len(lines) and 'create_index' in lines[i+1]:
                    # Indent the indexes
                    j = i + 1
                    while j < len(lines) and ('create_index' in lines[j] or lines[j].strip() == ''):
                        if 'create_index' in lines[j]:
                            lines[j] = '    ' + lines[j]
                        j += 1
    
    content = '\n'.join(new_lines)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 037 to check table existence")

if __name__ == '__main__':
    fix_migration_037()