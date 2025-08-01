"""Add performance indexes

Revision ID: 040_add_performance_indexes
Revises: 039_add_scheduled_tasks
Create Date: 2024-01-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '040_add_performance_indexes'
down_revision = '039_add_scheduled_tasks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing performance indexes."""
    
    # Scheduled tasks indexes
    op.create_index(
        'idx_scheduled_tasks_cron_expression', 
        'scheduled_tasks', 
        ['cron_expression'],
        postgresql_using='btree'
    )
    
    # External API credentials compound index
    op.create_index(
        'idx_external_api_credentials_provider_active', 
        'external_api_credentials', 
        ['provider', 'is_active'],
        postgresql_using='btree'
    )
    
    # API call logs indexes
    op.create_index(
        'idx_api_call_logs_created_at_provider', 
        'api_call_logs', 
        ['created_at', 'provider'],
        postgresql_using='btree'
    )
    
    # Notification indexes
    op.create_index(
        'idx_notification_user_created', 
        'notifications', 
        ['user_id', 'created_at'],
        postgresql_using='btree'
    )
    
    # User push tokens index
    op.create_index(
        'idx_user_push_token_user_active', 
        'user_push_tokens', 
        ['user_id', 'is_active'],
        postgresql_using='btree'
    )
    
    # Messages indexes for chat performance
    op.create_index(
        'idx_message_conversation_created', 
        'messages', 
        ['conversation_id', 'created_at'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_message_sender_created', 
        'messages', 
        ['sender_id', 'created_at'],
        postgresql_using='btree'
    )
    
    # Financial transactions indexes
    op.create_index(
        'idx_financial_transaction_date_type', 
        'financial_transactions', 
        ['transaction_date', 'type'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_financial_transaction_model_date', 
        'financial_transactions', 
        ['model_id', 'transaction_date'],
        postgresql_using='btree'
    )
    
    # Analytics metrics indexes
    op.create_index(
        'idx_metric_snapshot_period_type', 
        'metric_snapshots', 
        ['period_start', 'metric_type'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_metric_snapshot_agency_period', 
        'metric_snapshots', 
        ['agency_id', 'period_start'],
        postgresql_using='btree'
    )
    
    # API keys index for lookups
    op.create_index(
        'idx_api_key_hash_active', 
        'api_keys', 
        ['key_hash', 'is_active'],
        postgresql_using='btree'
    )
    
    # Session indexes for authentication
    op.create_index(
        'idx_session_token_active', 
        'sessions', 
        ['token', 'is_active'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_session_expires_active', 
        'sessions', 
        ['expires_at', 'is_active'],
        postgresql_using='btree'
    )


def downgrade() -> None:
    """Remove performance indexes."""
    
    # Drop all indexes in reverse order
    op.drop_index('idx_session_expires_active', 'sessions')
    op.drop_index('idx_session_token_active', 'sessions')
    op.drop_index('idx_api_key_hash_active', 'api_keys')
    op.drop_index('idx_metric_snapshot_agency_period', 'metric_snapshots')
    op.drop_index('idx_metric_snapshot_period_type', 'metric_snapshots')
    op.drop_index('idx_financial_transaction_model_date', 'financial_transactions')
    op.drop_index('idx_financial_transaction_date_type', 'financial_transactions')
    op.drop_index('idx_message_sender_created', 'messages')
    op.drop_index('idx_message_conversation_created', 'messages')
    op.drop_index('idx_user_push_token_user_active', 'user_push_tokens')
    op.drop_index('idx_notification_user_created', 'notifications')
    op.drop_index('idx_api_call_logs_created_at_provider', 'api_call_logs')
    op.drop_index('idx_external_api_credentials_provider_active', 'external_api_credentials')
    op.drop_index('idx_scheduled_tasks_cron_expression', 'scheduled_tasks')