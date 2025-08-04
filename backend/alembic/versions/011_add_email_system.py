"""Add email system tables

Revision ID: 011_add_email_system
Revises: 010_add_financial_improvements
Create Date: 2024-01-29 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011_add_email_system'
down_revision = '010_add_financial_improvements'
branch_labels = None
depends_on = None


def upgrade():
    # Create email_queue table
    op.create_table('email_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('to_emails', sa.JSON(), nullable=False),
        sa.Column('cc_emails', sa.JSON(), nullable=True),
        sa.Column('bcc_emails', sa.JSON(), nullable=True),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('html_content', sa.Text(), nullable=True),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('template_id', sa.String(length=100), nullable=True),
        sa.Column('template_data', sa.JSON(), nullable=True),
        sa.Column('from_email', sa.String(length=255), nullable=True),
        sa.Column('from_name', sa.String(length=255), nullable=True),
        sa.Column('reply_to', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='normal'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('scheduled_at', sa.String(length=30), nullable=True),
        sa.Column('sent_at', sa.String(length=30), nullable=True),
        sa.Column('next_retry_at', sa.String(length=30), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('provider_message_id', sa.String(length=255), nullable=True),
        sa.Column('provider_response', sa.JSON(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('related_object_type', sa.String(length=50), nullable=True),
        sa.Column('related_object_id', sa.Integer(), nullable=True),
        sa.Column('track_opens', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('track_clicks', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('attachments', sa.JSON(), nullable=True),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for email_queue
    op.create_index('idx_email_queue_status', 'email_queue', ['status'])
    op.create_index('idx_email_queue_priority', 'email_queue', ['priority'])
    op.create_index('idx_email_queue_status_priority', 'email_queue', ['status', 'priority'])
    op.create_index('idx_email_queue_scheduled', 'email_queue', ['status', 'scheduled_at'])
    op.create_index('idx_email_queue_retry', 'email_queue', ['status', 'next_retry_at'])
    op.create_index('idx_email_queue_user', 'email_queue', ['user_id', 'status'])
    op.create_index('idx_email_queue_related', 'email_queue', ['related_object_type', 'related_object_id'])
    
    # Create email_logs table
    op.create_table('email_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_queue_id', sa.Integer(), nullable=True),
        sa.Column('to_email', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('event_timestamp', sa.String(length=30), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('provider_event_id', sa.String(length=255), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for email_logs
    op.create_index('idx_email_logs_queue_id', 'email_logs', ['email_queue_id'])
    op.create_index('idx_email_logs_to_email', 'email_logs', ['to_email'])
    op.create_index('idx_email_logs_event_type', 'email_logs', ['event_type'])
    op.create_index('idx_email_logs_user_id', 'email_logs', ['user_id'])
    op.create_index('idx_email_log_email_event', 'email_logs', ['to_email', 'event_type'])
    op.create_index('idx_email_log_timestamp', 'email_logs', ['event_timestamp'])
    
    # Create email_preferences table
    op.create_table('email_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('email_address', sa.String(length=255), nullable=True),
        sa.Column('account_updates', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('security_alerts', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('model_approval', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('model_updates', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('payout_created', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('payout_approved', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('payout_completed', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('invoice_created', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('payment_received', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('daily_summary', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('weekly_report', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('monthly_statement', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('product_updates', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tips_and_tricks', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('promotional_offers', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('chat_notifications', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('mention_notifications', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notification_frequency', sa.String(length=20), nullable=False, server_default='realtime'),
        sa.Column('quiet_hours_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('quiet_hours_start', sa.String(length=5), nullable=True),
        sa.Column('quiet_hours_end', sa.String(length=5), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='UTC'),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('unsubscribe_token', sa.String(length=255), nullable=True),
        sa.Column('unsubscribed_at', sa.String(length=30), nullable=True),
        sa.Column('unsubscribe_reason', sa.String(length=500), nullable=True),
        sa.Column('custom_preferences', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_email_preferences_user'),
        sa.UniqueConstraint('unsubscribe_token', name='uq_email_preferences_token')
    )
    
    # Create index for email_preferences
    op.create_index('idx_email_preferences_user_id', 'email_preferences', ['user_id'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_email_preferences_user_id', 'email_preferences')
    
    op.drop_index('idx_email_log_timestamp', 'email_logs')
    op.drop_index('idx_email_log_email_event', 'email_logs')
    op.drop_index('idx_email_logs_user_id', 'email_logs')
    op.drop_index('idx_email_logs_event_type', 'email_logs')
    op.drop_index('idx_email_logs_to_email', 'email_logs')
    op.drop_index('idx_email_logs_queue_id', 'email_logs')
    
    op.drop_index('idx_email_queue_related', 'email_queue')
    op.drop_index('idx_email_queue_user', 'email_queue')
    op.drop_index('idx_email_queue_retry', 'email_queue')
    op.drop_index('idx_email_queue_scheduled', 'email_queue')
    op.drop_index('idx_email_queue_status_priority', 'email_queue')
    op.drop_index('idx_email_queue_priority', 'email_queue')
    op.drop_index('idx_email_queue_status', 'email_queue')
    
    # Drop tables
    op.drop_table('email_preferences')
    op.drop_table('email_logs')
    op.drop_table('email_queue')