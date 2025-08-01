"""add performance indexes

Revision ID: 015_add_performance_indexes
Revises: 014_add_rate_limit_fields
Create Date: 2025-01-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '015_add_performance_indexes'
down_revision = '014_add_rate_limit_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance indexes for commonly queried fields"""
    
    # User table indexes
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_agency_id', 'users', ['agency_id'])
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_is_active', 'users', ['is_active'])
    op.create_index('idx_users_last_login', 'users', ['last_login'])
    op.create_index('idx_users_created_at', 'users', ['created_at'])
    
    # Composite indexes for common queries
    op.create_index('idx_users_agency_role', 'users', ['agency_id', 'role'])
    op.create_index('idx_users_active_agency', 'users', ['is_active', 'agency_id'])
    
    # Model profiles indexes
    op.create_index('idx_model_profiles_user_id', 'model_profiles', ['user_id'])
    op.create_index('idx_model_profiles_agency_id', 'model_profiles', ['agency_id'])
    op.create_index('idx_model_profiles_platform', 'model_profiles', ['platform'])
    op.create_index('idx_model_profiles_is_active', 'model_profiles', ['is_active'])
    op.create_index('idx_model_profiles_created_at', 'model_profiles', ['created_at'])
    
    # Composite index for platform queries
    op.create_index('idx_model_profiles_agency_platform', 'model_profiles', ['agency_id', 'platform'])
    
    # Transactions indexes
    op.create_index('idx_transactions_model_id', 'transactions', ['model_id'])
    op.create_index('idx_transactions_agency_id', 'transactions', ['agency_id'])
    op.create_index('idx_transactions_type', 'transactions', ['type'])
    op.create_index('idx_transactions_status', 'transactions', ['status'])
    op.create_index('idx_transactions_date', 'transactions', ['date'])
    op.create_index('idx_transactions_created_at', 'transactions', ['created_at'])
    
    # Composite indexes for financial queries
    op.create_index('idx_transactions_model_date', 'transactions', ['model_id', 'date'])
    op.create_index('idx_transactions_agency_date', 'transactions', ['agency_id', 'date'])
    op.create_index('idx_transactions_type_status', 'transactions', ['type', 'status'])
    
    # Messages indexes
    op.create_index('idx_messages_sender_id', 'messages', ['sender_id'])
    op.create_index('idx_messages_recipient_id', 'messages', ['recipient_id'])
    op.create_index('idx_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('idx_messages_platform', 'messages', ['platform'])
    op.create_index('idx_messages_is_read', 'messages', ['is_read'])
    op.create_index('idx_messages_created_at', 'messages', ['created_at'])
    
    # Composite indexes for message queries
    op.create_index('idx_messages_conversation_created', 'messages', ['conversation_id', 'created_at'])
    op.create_index('idx_messages_recipient_read', 'messages', ['recipient_id', 'is_read'])
    
    # Webhooks indexes
    op.create_index('idx_webhooks_agency_id', 'webhooks', ['agency_id'])
    op.create_index('idx_webhooks_is_active', 'webhooks', ['is_active'])
    op.create_index('idx_webhooks_created_at', 'webhooks', ['created_at'])
    
    # Webhook deliveries indexes
    op.create_index('idx_webhook_deliveries_webhook_id', 'webhook_deliveries', ['webhook_id'])
    op.create_index('idx_webhook_deliveries_status', 'webhook_deliveries', ['status'])
    op.create_index('idx_webhook_deliveries_created_at', 'webhook_deliveries', ['created_at'])
    
    # API keys indexes
    op.create_index('idx_api_keys_agency_id', 'api_keys', ['agency_id'])
    op.create_index('idx_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('idx_api_keys_key_prefix', 'api_keys', ['key_prefix'])
    op.create_index('idx_api_keys_is_active', 'api_keys', ['is_active'])
    op.create_index('idx_api_keys_created_at', 'api_keys', ['created_at'])
    
    # Composite index for API key lookup
    op.create_index('idx_api_keys_prefix_active', 'api_keys', ['key_prefix', 'is_active'])
    
    # Analytics events indexes
    op.create_index('idx_analytics_events_model_id', 'analytics_events', ['model_id'])
    op.create_index('idx_analytics_events_agency_id', 'analytics_events', ['agency_id'])
    op.create_index('idx_analytics_events_event_type', 'analytics_events', ['event_type'])
    op.create_index('idx_analytics_events_platform', 'analytics_events', ['platform'])
    op.create_index('idx_analytics_events_created_at', 'analytics_events', ['created_at'])
    
    # Composite indexes for analytics queries
    op.create_index('idx_analytics_events_model_type_date', 'analytics_events', ['model_id', 'event_type', 'created_at'])
    op.create_index('idx_analytics_events_agency_type_date', 'analytics_events', ['agency_id', 'event_type', 'created_at'])
    
    # Fans/Subscribers indexes
    op.create_index('idx_fans_model_id', 'fans', ['model_id'])
    op.create_index('idx_fans_platform', 'fans', ['platform'])
    op.create_index('idx_fans_is_active', 'fans', ['is_active'])
    op.create_index('idx_fans_subscription_tier', 'fans', ['subscription_tier'])
    op.create_index('idx_fans_created_at', 'fans', ['created_at'])
    op.create_index('idx_fans_last_interaction', 'fans', ['last_interaction'])
    
    # Composite indexes for fan queries
    op.create_index('idx_fans_model_active', 'fans', ['model_id', 'is_active'])
    op.create_index('idx_fans_model_tier', 'fans', ['model_id', 'subscription_tier'])
    
    # Scheduled messages indexes
    if op.get_bind().dialect.has_table(op.get_bind(), 'scheduled_messages'):
        op.create_index('idx_scheduled_messages_model_id', 'scheduled_messages', ['model_id'])
        op.create_index('idx_scheduled_messages_status', 'scheduled_messages', ['status'])
        op.create_index('idx_scheduled_messages_scheduled_for', 'scheduled_messages', ['scheduled_for'])
        op.create_index('idx_scheduled_messages_created_at', 'scheduled_messages', ['created_at'])
        
        # Composite index for pending messages
        op.create_index('idx_scheduled_messages_status_time', 'scheduled_messages', ['status', 'scheduled_for'])
    
    # Bulk operations indexes
    if op.get_bind().dialect.has_table(op.get_bind(), 'bulk_operations'):
        op.create_index('idx_bulk_operations_agency_id', 'bulk_operations', ['agency_id'])
        op.create_index('idx_bulk_operations_created_by', 'bulk_operations', ['created_by'])
        op.create_index('idx_bulk_operations_status', 'bulk_operations', ['status'])
        op.create_index('idx_bulk_operations_operation_type', 'bulk_operations', ['operation_type'])
        op.create_index('idx_bulk_operations_created_at', 'bulk_operations', ['created_at'])
    
    # ML predictions indexes
    if op.get_bind().dialect.has_table(op.get_bind(), 'ml_predictions'):
        op.create_index('idx_ml_predictions_model_id', 'ml_predictions', ['model_id'])
        op.create_index('idx_ml_predictions_prediction_type', 'ml_predictions', ['prediction_type'])
        op.create_index('idx_ml_predictions_created_at', 'ml_predictions', ['created_at'])
        
        # Composite index for recent predictions
        op.create_index('idx_ml_predictions_model_type_date', 'ml_predictions', ['model_id', 'prediction_type', 'created_at'])
    
    # Add GIN indexes for JSONB columns (PostgreSQL specific)
    op.execute("CREATE INDEX idx_users_preferences_gin ON users USING GIN (preferences) WHERE preferences IS NOT NULL")
    op.execute("CREATE INDEX idx_users_metadata_gin ON users USING GIN (metadata) WHERE metadata IS NOT NULL")
    op.execute("CREATE INDEX idx_model_profiles_settings_gin ON model_profiles USING GIN (settings) WHERE settings IS NOT NULL")
    op.execute("CREATE INDEX idx_webhooks_custom_headers_gin ON webhooks USING GIN (custom_headers) WHERE custom_headers IS NOT NULL")
    
    # Add text search indexes (PostgreSQL specific)
    op.execute("CREATE INDEX idx_messages_content_trgm ON messages USING GIN (content gin_trgm_ops)")
    op.execute("CREATE INDEX idx_users_full_name_trgm ON users USING GIN (full_name gin_trgm_ops)")
    op.execute("CREATE INDEX idx_fans_username_trgm ON fans USING GIN (username gin_trgm_ops)")
    
    # Add partial indexes for common filters
    op.create_index('idx_users_active_only', 'users', ['id'], postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_model_profiles_active_only', 'model_profiles', ['id'], postgresql_where=sa.text('is_active = true'))
    op.create_index('idx_transactions_pending', 'transactions', ['id', 'created_at'], postgresql_where=sa.text("status = 'pending'"))
    op.create_index('idx_messages_unread', 'messages', ['recipient_id', 'created_at'], postgresql_where=sa.text('is_read = false'))
    
    # Add covering indexes for common queries
    op.execute("""
        CREATE INDEX idx_transactions_covering 
        ON transactions (agency_id, date, type) 
        INCLUDE (amount, status)
    """)
    
    op.execute("""
        CREATE INDEX idx_messages_covering 
        ON messages (conversation_id, created_at) 
        INCLUDE (sender_id, recipient_id, content, is_read)
    """)


def downgrade() -> None:
    """Remove performance indexes"""
    
    # Drop covering indexes
    op.execute("DROP INDEX IF EXISTS idx_transactions_covering")
    op.execute("DROP INDEX IF EXISTS idx_messages_covering")
    
    # Drop partial indexes
    op.drop_index('idx_users_active_only', 'users')
    op.drop_index('idx_model_profiles_active_only', 'model_profiles')
    op.drop_index('idx_transactions_pending', 'transactions')
    op.drop_index('idx_messages_unread', 'messages')
    
    # Drop text search indexes
    op.execute("DROP INDEX IF EXISTS idx_messages_content_trgm")
    op.execute("DROP INDEX IF EXISTS idx_users_full_name_trgm")
    op.execute("DROP INDEX IF EXISTS idx_fans_username_trgm")
    
    # Drop GIN indexes
    op.execute("DROP INDEX IF EXISTS idx_users_preferences_gin")
    op.execute("DROP INDEX IF EXISTS idx_users_metadata_gin")
    op.execute("DROP INDEX IF EXISTS idx_model_profiles_settings_gin")
    op.execute("DROP INDEX IF EXISTS idx_webhooks_custom_headers_gin")
    
    # Drop all other indexes (in reverse order)
    # ... (all the drop_index calls for the indexes created above)