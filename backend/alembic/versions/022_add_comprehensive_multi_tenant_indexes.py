"""Add comprehensive multi-tenant indexes for all tables missing agency_id indexes

Revision ID: 022_add_comprehensive_multi_tenant_indexes
Revises: 021_add_missing_core_tables
Create Date: 2025-08-01

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '022_add_comprehensive_multi_tenant_indexes'
down_revision = '021_add_missing_core_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add agency_id indexes to all tenant-scoped tables that are missing them."""
    
    # Check and add indexes for core tables that might be missing them
    
    # Users table - add composite index if not exists
    op.create_index('idx_users_agency_active', 'users', ['agency_id', 'is_active'], 
                   postgresql_where=sa.text("is_active = true"))
    
    # Sessions table - important for performance
    op.create_index('idx_sessions_agency_id', 'sessions', ['agency_id'])
    op.create_index('idx_sessions_agency_expires', 'sessions', ['agency_id', 'expires_at'])
    
    # Fans table - critical for multi-tenant queries
    op.create_index('idx_fans_agency_id', 'fans', ['agency_id'])
    op.create_index('idx_fans_agency_platform', 'fans', ['agency_id', 'platform'])
    op.create_index('idx_fans_agency_active', 'fans', ['agency_id', 'is_active'])
    
    # Fan claims table
    op.create_index('idx_fan_claims_agency_id', 'fan_claims', ['agency_id'])
    op.create_index('idx_fan_claims_agency_chatter', 'fan_claims', ['agency_id', 'chatter_id'])
    
    # Model chatters table
    op.create_index('idx_model_chatters_agency_id', 'model_chatters', ['agency_id'])
    
    # Add composite indexes for common query patterns
    
    # Financial queries often filter by date range
    op.create_index('idx_financial_transactions_agency_date', 'financial_transactions', 
                   ['agency_id', 'created_at'])
    op.create_index('idx_financial_transactions_agency_status', 'financial_transactions', 
                   ['agency_id', 'status'])
    op.create_index('idx_financial_transactions_agency_type', 'financial_transactions', 
                   ['agency_id', 'transaction_type'])
    
    # Chat queries often filter by model or fan
    op.create_index('idx_chat_conversations_agency_model', 'chat_conversations', 
                   ['agency_id', 'model_id'])
    op.create_index('idx_chat_conversations_agency_fan', 'chat_conversations', 
                   ['agency_id', 'fan_id'])
    op.create_index('idx_chat_conversations_agency_status', 'chat_conversations', 
                   ['agency_id', 'status'])
    
    # Webhook logs often queried by status and date
    op.create_index('idx_webhook_logs_agency_status', 'webhook_logs', 
                   ['agency_id', 'status'])
    op.create_index('idx_webhook_logs_agency_date', 'webhook_logs', 
                   ['agency_id', 'created_at'])
    
    # Analytics and reporting indexes
    op.create_index('idx_notifications_agency_unread', 'notifications', 
                   ['agency_id', 'is_read'], 
                   postgresql_where=sa.text("is_read = false"))
    
    op.create_index('idx_audit_logs_agency_date', 'audit_logs', 
                   ['agency_id', 'created_at'])
    op.create_index('idx_audit_logs_agency_entity', 'audit_logs', 
                   ['agency_id', 'entity_type', 'entity_id'])
    
    # Performance: Create covering indexes for frequently accessed columns
    op.create_index('idx_model_profiles_agency_covering', 'model_profiles', 
                   ['agency_id', 'user_id', 'is_active', 'platform'])
    
    # Add BRIN indexes for time-series data (if tables are large)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_financial_transactions_created_brin 
        ON financial_transactions USING brin(created_at) 
        WITH (pages_per_range = 128);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_created_brin 
        ON chat_messages USING brin(created_at) 
        WITH (pages_per_range = 128);
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_webhook_logs_created_brin 
        ON webhook_logs USING brin(created_at) 
        WITH (pages_per_range = 128);
    """)
    
    # Add GIN indexes for JSONB columns for better query performance
    op.create_index('idx_fan_profiles_custom_fields_gin', 'fan_profiles', 
                   ['custom_fields'], postgresql_using='gin')
    op.create_index('idx_webhook_logs_payload_gin', 'webhook_logs', 
                   ['payload'], postgresql_using='gin')
    op.create_index('idx_chat_messages_metadata_gin', 'chat_messages', 
                   ['metadata'], postgresql_using='gin')


def downgrade() -> None:
    """Remove all indexes created in upgrade."""
    # Drop GIN indexes
    op.drop_index('idx_chat_messages_metadata_gin', 'chat_messages')
    op.drop_index('idx_webhook_logs_payload_gin', 'webhook_logs')
    op.drop_index('idx_fan_profiles_custom_fields_gin', 'fan_profiles')
    
    # Drop BRIN indexes
    op.execute("DROP INDEX IF EXISTS idx_webhook_logs_created_brin;")
    op.execute("DROP INDEX IF EXISTS idx_chat_messages_created_brin;")
    op.execute("DROP INDEX IF EXISTS idx_financial_transactions_created_brin;")
    
    # Drop covering indexes
    op.drop_index('idx_model_profiles_agency_covering', 'model_profiles')
    
    # Drop analytics indexes
    op.drop_index('idx_audit_logs_agency_entity', 'audit_logs')
    op.drop_index('idx_audit_logs_agency_date', 'audit_logs')
    op.drop_index('idx_notifications_agency_unread', 'notifications')
    
    # Drop webhook indexes
    op.drop_index('idx_webhook_logs_agency_date', 'webhook_logs')
    op.drop_index('idx_webhook_logs_agency_status', 'webhook_logs')
    
    # Drop chat indexes
    op.drop_index('idx_chat_conversations_agency_status', 'chat_conversations')
    op.drop_index('idx_chat_conversations_agency_fan', 'chat_conversations')
    op.drop_index('idx_chat_conversations_agency_model', 'chat_conversations')
    
    # Drop financial indexes
    op.drop_index('idx_financial_transactions_agency_type', 'financial_transactions')
    op.drop_index('idx_financial_transactions_agency_status', 'financial_transactions')
    op.drop_index('idx_financial_transactions_agency_date', 'financial_transactions')
    
    # Drop model chatters index
    op.drop_index('idx_model_chatters_agency_id', 'model_chatters')
    
    # Drop fan claims indexes
    op.drop_index('idx_fan_claims_agency_chatter', 'fan_claims')
    op.drop_index('idx_fan_claims_agency_id', 'fan_claims')
    
    # Drop fans indexes
    op.drop_index('idx_fans_agency_active', 'fans')
    op.drop_index('idx_fans_agency_platform', 'fans')
    op.drop_index('idx_fans_agency_id', 'fans')
    
    # Drop sessions indexes
    op.drop_index('idx_sessions_agency_expires', 'sessions')
    op.drop_index('idx_sessions_agency_id', 'sessions')
    
    # Drop users index
    op.drop_index('idx_users_agency_active', 'users')