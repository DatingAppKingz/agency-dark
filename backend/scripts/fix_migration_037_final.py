#!/usr/bin/env python3
"""
Fix migration 037 - handle existing notifications table from migration 001.
The notifications table in migration 001 doesn't have a status column,
so we need to either add it or skip the status index.
"""
from pathlib import Path

def fix_migration_037():
    """Fix migration 037 to handle existing notifications table properly."""
    
    filepath = Path(__file__).parent.parent / 'alembic' / 'versions' / '037_notifications.py'
    
    new_content = '''"""Add notification tables

Revision ID: 037
Revises: 036
Create Date: 2025-01-08 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '037'
down_revision = '036'
branch_labels = None
depends_on = None


def upgrade() -> None:
    
    # Check and create notificationpriority enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'notificationpriority'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE notificationpriority AS ENUM ('low', 'normal', 'high', 'urgent')"))

    # Check and create notificationstatus enum
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'notificationstatus'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE notificationstatus AS ENUM ('pending', 'sent', 'delivered', 'failed', 'bounced', 'opened', 'clicked')"))

    # Check and create notificationtype enum if not exists
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'notificationtype'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE notificationtype AS ENUM ('email', 'sms', 'push', 'in_app', 'webhook')"))
    
    # Check if notifications table exists
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notifications')"
    ))
    notifications_exists = result.scalar()
    
    if notifications_exists:
        # The table exists from migration 001, need to add missing columns
        # Check which columns exist
        result = conn.execute(sa.text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'notifications'
        """))
        existing_columns = [row[0] for row in result]
        
        # Add missing columns
        if 'status' not in existing_columns:
            op.add_column('notifications', 
                sa.Column('status', postgresql.ENUM('pending', 'sent', 'delivered', 'failed', 'bounced', 'opened', 'clicked', name='notificationstatus', create_type=False), nullable=False, server_default='pending'))
        
        if 'priority' not in existing_columns:
            op.add_column('notifications', 
                sa.Column('priority', postgresql.ENUM('low', 'normal', 'high', 'urgent', name='notificationpriority', create_type=False), nullable=False, server_default='normal'))
        
        if 'email' not in existing_columns:
            op.add_column('notifications', sa.Column('email', sa.String(length=255), nullable=True))
        
        if 'phone' not in existing_columns:
            op.add_column('notifications', sa.Column('phone', sa.String(length=20), nullable=True))
        
        if 'subject' not in existing_columns:
            op.add_column('notifications', sa.Column('subject', sa.String(length=500), nullable=True))
        
        if 'content' not in existing_columns:
            op.add_column('notifications', sa.Column('content', sa.Text(), nullable=True))
        
        if 'html_content' not in existing_columns:
            op.add_column('notifications', sa.Column('html_content', sa.Text(), nullable=True))
        
        if 'template_id' not in existing_columns:
            op.add_column('notifications', sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True))
        
        if 'template_data' not in existing_columns:
            op.add_column('notifications', sa.Column('template_data', sa.JSON(), nullable=True))
        
        if 'metadata' not in existing_columns:
            op.add_column('notifications', sa.Column('metadata', sa.JSON(), nullable=True))
        
        if 'tags' not in existing_columns:
            op.add_column('notifications', sa.Column('tags', sa.JSON(), nullable=True))
        
        if 'scheduled_at' not in existing_columns:
            op.add_column('notifications', sa.Column('scheduled_at', sa.DateTime(), nullable=True))
        
        if 'sent_at' not in existing_columns:
            op.add_column('notifications', sa.Column('sent_at', sa.DateTime(), nullable=True))
        
        if 'delivered_at' not in existing_columns:
            op.add_column('notifications', sa.Column('delivered_at', sa.DateTime(), nullable=True))
        
        if 'opened_at' not in existing_columns:
            op.add_column('notifications', sa.Column('opened_at', sa.DateTime(), nullable=True))
        
        if 'clicked_at' not in existing_columns:
            op.add_column('notifications', sa.Column('clicked_at', sa.DateTime(), nullable=True))
        
        if 'retry_count' not in existing_columns:
            op.add_column('notifications', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
        
        if 'max_retries' not in existing_columns:
            op.add_column('notifications', sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'))
        
        if 'error_message' not in existing_columns:
            op.add_column('notifications', sa.Column('error_message', sa.Text(), nullable=True))
        
        if 'external_id' not in existing_columns:
            op.add_column('notifications', sa.Column('external_id', sa.String(length=255), nullable=True))
        
        if 'callback_url' not in existing_columns:
            op.add_column('notifications', sa.Column('callback_url', sa.String(length=500), nullable=True))
        
        if 'updated_at' not in existing_columns:
            op.add_column('notifications', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))
    else:
        # Create the full notifications table
        op.create_table('notifications',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('type', postgresql.ENUM('email', 'sms', 'push', 'in_app', 'webhook', name='notificationtype', create_type=False), nullable=False),
            sa.Column('status', postgresql.ENUM('pending', 'sent', 'delivered', 'failed', 'bounced', 'opened', 'clicked', name='notificationstatus', create_type=False), nullable=False),
            sa.Column('priority', postgresql.ENUM('low', 'normal', 'high', 'urgent', name='notificationpriority', create_type=False), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('phone', sa.String(length=20), nullable=True),
            sa.Column('subject', sa.String(length=500), nullable=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('html_content', sa.Text(), nullable=True),
            sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('template_data', sa.JSON(), nullable=True),
            sa.Column('metadata', sa.JSON(), nullable=True),
            sa.Column('tags', sa.JSON(), nullable=True),
            sa.Column('scheduled_at', sa.DateTime(), nullable=True),
            sa.Column('sent_at', sa.DateTime(), nullable=True),
            sa.Column('delivered_at', sa.DateTime(), nullable=True),
            sa.Column('opened_at', sa.DateTime(), nullable=True),
            sa.Column('clicked_at', sa.DateTime(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('external_id', sa.String(length=255), nullable=True),
            sa.Column('callback_url', sa.String(length=500), nullable=True),
            sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
            sa.ForeignKeyConstraint(['template_id'], ['notification_templates.id'], ),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
    
    # Create notification_templates table if not exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notification_templates')"
    ))
    if not result.scalar():
        op.create_table('notification_templates',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('type', postgresql.ENUM('email', 'sms', 'push', 'in_app', 'webhook', name='notificationtype', create_type=False), nullable=False),
            sa.Column('subject_template', sa.String(length=500), nullable=True),
            sa.Column('content_template', sa.Text(), nullable=False),
            sa.Column('html_template', sa.Text(), nullable=True),
            sa.Column('variables_schema', sa.JSON(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes for notification_templates
        op.create_index(op.f('ix_notification_templates_agency_id'), 'notification_templates', ['agency_id'], unique=False)
        op.create_index(op.f('ix_notification_templates_type'), 'notification_templates', ['type'], unique=False)
    
    # Create notification_preferences table if not exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notification_preferences')"
    ))
    if not result.scalar():
        op.create_table('notification_preferences',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('sms_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('push_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('in_app_enabled', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('categories', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('digest_enabled', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('digest_frequency', sa.String(length=20), nullable=True, server_default='daily'),
            sa.Column('quiet_hours_enabled', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('quiet_hours_start', sa.String(length=5), nullable=True),
            sa.Column('quiet_hours_end', sa.String(length=5), nullable=True),
            sa.Column('timezone', sa.String(length=50), nullable=False, server_default='UTC'),
            sa.Column('preferred_email', sa.String(length=255), nullable=True),
            sa.Column('preferred_phone', sa.String(length=20), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
        )
    
    # Create notification_events table if not exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'notification_events')"
    ))
    if not result.scalar():
        op.create_table('notification_events',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('notification_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('event_data', sa.JSON(), nullable=True),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.String(length=500), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes for notification_events
        op.create_index(op.f('ix_notification_events_notification_id'), 'notification_events', ['notification_id'], unique=False)
        op.create_index(op.f('ix_notification_events_event_type'), 'notification_events', ['event_type'], unique=False)
    
    # Create indices for notifications table
    # Only create indexes if they don't exist
    
    # Check if ix_notifications_user_id exists
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_notifications_user_id'"
    ))
    if not result.fetchone():
        op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    
    # Check if ix_notifications_agency_id exists
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_notifications_agency_id'"
    ))
    if not result.fetchone():
        op.create_index(op.f('ix_notifications_agency_id'), 'notifications', ['agency_id'], unique=False)
    
    # Check if ix_notifications_type exists
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_notifications_type'"
    ))
    if not result.fetchone():
        op.create_index(op.f('ix_notifications_type'), 'notifications', ['type'], unique=False)
    
    # Only create status index if status column exists
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'notifications' AND column_name = 'status'
    """))
    if result.fetchone():
        # Check if ix_notifications_status exists
        result = conn.execute(sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_notifications_status'"
        ))
        if not result.fetchone():
            op.create_index(op.f('ix_notifications_status'), 'notifications', ['status'], unique=False)
    
    # Only create scheduled_at index if column exists
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'notifications' AND column_name = 'scheduled_at'
    """))
    if result.fetchone():
        # Check if ix_notifications_scheduled_at exists
        result = conn.execute(sa.text(
            "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_notifications_scheduled_at'"
        ))
        if not result.fetchone():
            op.create_index(op.f('ix_notifications_scheduled_at'), 'notifications', ['scheduled_at'], unique=False)
    
    # Check if ix_notifications_created_at exists
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE indexname = 'ix_notifications_created_at'"
    ))
    if not result.fetchone():
        op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop indices
    op.drop_index(op.f('ix_notification_events_event_type'), table_name='notification_events')
    op.drop_index(op.f('ix_notification_events_notification_id'), table_name='notification_events')
    
    op.drop_index(op.f('ix_notification_templates_type'), table_name='notification_templates')
    op.drop_index(op.f('ix_notification_templates_agency_id'), table_name='notification_templates')
    
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_scheduled_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_status'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_agency_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    
    # Drop tables
    op.drop_table('notification_events')
    op.drop_table('notification_preferences')
    op.drop_table('notifications')
    op.drop_table('notification_templates')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS notificationtype')
    op.execute('DROP TYPE IF EXISTS notificationstatus')
    op.execute('DROP TYPE IF EXISTS notificationpriority')
'''
    
    with open(filepath, 'w') as f:
        f.write(new_content)
    
    print("Fixed migration 037 to handle existing notifications table properly")

if __name__ == '__main__':
    fix_migration_037()