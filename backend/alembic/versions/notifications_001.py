"""Add notification tables

Revision ID: notifications_001
Revises: saved_searches_001
Create Date: 2025-01-08 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'notifications_001'
down_revision = 'saved_searches_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create notifications table
    op.create_table('notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', sa.Enum('email', 'sms', 'push', 'in_app', 'webhook', name='notificationtype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'sent', 'delivered', 'failed', 'bounced', 'opened', 'clicked', name='notificationstatus'), nullable=False),
        sa.Column('priority', sa.Enum('low', 'normal', 'high', 'urgent', name='notificationpriority'), nullable=False),
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
    
    # Create notification_templates table
    op.create_table('notification_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type', sa.Enum('email', 'sms', 'push', 'in_app', 'webhook', name='notificationtype'), nullable=False),
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
    
    # Create notification_preferences table
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
    
    # Create notification_events table
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
    
    # Create indices
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_agency_id'), 'notifications', ['agency_id'], unique=False)
    op.create_index(op.f('ix_notifications_type'), 'notifications', ['type'], unique=False)
    op.create_index(op.f('ix_notifications_status'), 'notifications', ['status'], unique=False)
    op.create_index(op.f('ix_notifications_scheduled_at'), 'notifications', ['scheduled_at'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)
    
    op.create_index(op.f('ix_notification_templates_agency_id'), 'notification_templates', ['agency_id'], unique=False)
    op.create_index(op.f('ix_notification_templates_type'), 'notification_templates', ['type'], unique=False)
    
    op.create_index(op.f('ix_notification_events_notification_id'), 'notification_events', ['notification_id'], unique=False)
    op.create_index(op.f('ix_notification_events_event_type'), 'notification_events', ['event_type'], unique=False)


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