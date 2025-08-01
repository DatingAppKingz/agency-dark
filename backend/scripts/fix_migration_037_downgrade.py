#!/usr/bin/env python3
"""
Fix migration 037 downgrade function to handle existing notifications table.
"""
from pathlib import Path

def fix_migration_037_downgrade():
    """Fix migration 037 downgrade to handle existing notifications table properly."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '037_notifications.py'
    
    # Read the original file
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Replace the downgrade function with a safer version
    new_downgrade = '''def downgrade() -> None:
    conn = op.get_bind()
    
    # Drop indices if they exist
    indexes_to_drop = [
        ('ix_notification_events_event_type', 'notification_events'),
        ('ix_notification_events_notification_id', 'notification_events'),
        ('ix_notification_templates_type', 'notification_templates'),
        ('ix_notification_templates_agency_id', 'notification_templates'),
        ('ix_notifications_created_at', 'notifications'),
        ('ix_notifications_scheduled_at', 'notifications'),
        ('ix_notifications_status', 'notifications'),
        ('ix_notifications_type', 'notifications'),
        ('ix_notifications_agency_id', 'notifications'),
        ('ix_notifications_user_id', 'notifications')
    ]
    
    for index_name, table_name in indexes_to_drop:
        result = conn.execute(sa.text(
            f"SELECT 1 FROM pg_indexes WHERE indexname = '{index_name}'"
        ))
        if result.fetchone():
            op.drop_index(op.f(index_name), table_name=table_name)
    
    # Drop tables if they exist
    tables_to_drop = [
        'notification_events',
        'notification_preferences',
        'notification_templates'
    ]
    
    for table_name in tables_to_drop:
        result = conn.execute(sa.text(
            f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')"
        ))
        if result.scalar():
            op.drop_table(table_name)
    
    # For notifications table, we need to be careful
    # Check if the notifications table existed before this migration
    result = conn.execute(sa.text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'notifications'
    """))
    columns = [row[0] for row in result]
    
    # If it has columns we added, remove them. Otherwise leave the table alone
    columns_to_drop = [
        'status', 'priority', 'email', 'phone', 'subject', 'content', 
        'html_content', 'template_id', 'template_data', 'metadata', 'tags',
        'scheduled_at', 'sent_at', 'delivered_at', 'opened_at', 'clicked_at',
        'retry_count', 'max_retries', 'error_message', 'external_id', 
        'callback_url', 'updated_at'
    ]
    
    for col in columns_to_drop:
        if col in columns:
            try:
                op.drop_column('notifications', col)
            except:
                pass  # Column might have dependencies
    
    # Don't drop the notifications table if it existed before
    # (it was created in migration 001)
    
    # Drop enums only if they're not used elsewhere
    enums_to_check = [
        'notificationtype',
        'notificationstatus', 
        'notificationpriority'
    ]
    
    for enum_name in enums_to_check:
        # Check if enum is used in any remaining tables
        result = conn.execute(sa.text(f"""
            SELECT COUNT(*)
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            JOIN pg_depend d ON t.oid = d.objid
            WHERE t.typname = '{enum_name}'
            AND d.deptype = 'n'
        """))
        
        if result.scalar() == 0:
            op.execute(f'DROP TYPE IF EXISTS {enum_name}')'''
    
    # Find the downgrade function and replace it
    import re
    pattern = r'def downgrade\(\) -> None:.*?(?=\n(?:def|$))'
    content = re.sub(pattern, new_downgrade, content, flags=re.DOTALL)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print("Fixed migration 037 downgrade function")

if __name__ == '__main__':
    fix_migration_037_downgrade()