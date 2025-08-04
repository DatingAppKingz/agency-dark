"""Database optimizations for performance

Revision ID: 013_database_optimizations
Revises: 012_enhance_chat_system
Create Date: 2024-01-29 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '013_database_optimizations'
down_revision = '012_enhance_chat_system'
branch_labels = None
depends_on = None


def upgrade():
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgstattuple")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # For text search optimization
    
    # Create composite indexes for common query patterns
    
    # Messages table indexes
    op.create_index(
        'idx_messages_conversation_created',
        'messages',
        ['conversation_id', 'created_at'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_messages_sender_type_created',
        'messages',
        ['sender_type', 'created_at'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_messages_conversation_sender',
        'messages',
        ['conversation_id', 'sender_id', 'sender_type'],
        postgresql_where=sa.text('is_deleted = false'),
        postgresql_using='btree'
    )
    
    # Conversations table indexes
    op.create_index(
        'idx_conversations_model_status_last_msg',
        'conversations',
        ['model_id', 'status', 'last_message_at'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_conversations_assigned_status',
        'conversations',
        ['assigned_chatter_id', 'status'],
        postgresql_where=sa.text('assigned_chatter_id IS NOT NULL'),
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_conversations_fan_username_trgm',
        'conversations',
        ['fan_username'],
        postgresql_using='gin',
        postgresql_ops={'fan_username': 'gin_trgm_ops'}
    )
    
    # Financial tables indexes
    op.create_index(
        'idx_transactions_model_date',
        'transactions',
        ['model_id', 'created_at'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_transactions_type_status',
        'transactions',
        ['transaction_type', 'status'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_payouts_model_status_date',
        'payouts',
        ['model_id', 'status', 'created_at'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_earnings_model_period',
        'earnings',
        ['model_id', 'period_start', 'period_end'],
        postgresql_using='btree'
    )
    
    # User/Model indexes
    op.create_index(
        'idx_users_email_lower',
        'users',
        [sa.text('LOWER(email)')],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_users_agency_role_active',
        'users',
        ['agency_id', 'role', 'is_active'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_models_agency_active_approved',
        'models',
        ['agency_id', 'is_active', 'approval_status'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_models_stage_name_trgm',
        'models',
        ['stage_name'],
        postgresql_using='gin',
        postgresql_ops={'stage_name': 'gin_trgm_ops'}
    )
    
    # Email system indexes
    op.create_index(
        'idx_email_queue_status_priority_scheduled',
        'email_queue',
        ['status', 'priority', 'scheduled_at'],
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_email_logs_email_event',
        'email_logs',
        ['to_email', 'event_type', 'event_timestamp'],
        postgresql_using='btree'
    )
    
    # Create partial indexes for boolean flags
    op.create_index(
        'idx_messages_unread_fan',
        'messages',
        ['conversation_id'],
        postgresql_where=sa.text("sender_type = 'fan' AND read_at IS NULL"),
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_messages_flagged',
        'messages',
        ['created_at'],
        postgresql_where=sa.text('is_flagged = true'),
        postgresql_using='btree'
    )
    
    # Create function for updating updated_at timestamps
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Add triggers for updated_at on tables that have it
    tables_with_updated_at = [
        'users', 'models', 'conversations', 'messages',
        'transactions', 'payouts', 'email_queue', 'email_preferences'
    ]
    
    for table in tables_with_updated_at:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at 
            BEFORE UPDATE ON {table}
            FOR EACH ROW 
            EXECUTE PROCEDURE update_updated_at_column();
        """)
    
    # Create materialized views for expensive queries
    
    # Daily model statistics
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_model_stats AS
        SELECT 
            m.id as model_id,
            m.stage_name,
            DATE(msg.created_at) as date,
            COUNT(DISTINCT c.id) as active_conversations,
            COUNT(msg.id) as total_messages,
            SUM(CASE WHEN msg.sender_type = 'fan' THEN 1 ELSE 0 END) as fan_messages,
            SUM(CASE WHEN msg.type = 'tip' AND msg.is_paid THEN msg.amount ELSE 0 END) as tips_revenue,
            SUM(CASE WHEN msg.type = 'ppv' AND msg.is_paid THEN msg.amount ELSE 0 END) as ppv_revenue
        FROM models m
        LEFT JOIN conversations c ON c.model_id = m.id
        LEFT JOIN messages msg ON msg.conversation_id = c.id
        WHERE msg.created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY m.id, m.stage_name, DATE(msg.created_at)
    """)
    
    op.create_index(
        'idx_mv_daily_model_stats_model_date',
        'mv_daily_model_stats',
        ['model_id', 'date'],
        postgresql_using='btree'
    )
    
    # Conversation summary view
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_conversation_summary AS
        SELECT 
            c.id as conversation_id,
            c.model_id,
            c.fan_username,
            COUNT(m.id) as message_count,
            MAX(m.created_at) as last_message_at,
            SUM(CASE WHEN m.sender_type = 'fan' THEN 1 ELSE 0 END) as fan_message_count,
            SUM(CASE WHEN m.is_paid THEN m.amount ELSE 0 END) as total_revenue
        FROM conversations c
        LEFT JOIN messages m ON m.conversation_id = c.id
        WHERE c.status = 'active'
        GROUP BY c.id, c.model_id, c.fan_username
    """)
    
    op.create_index(
        'idx_mv_conversation_summary_model',
        'mv_conversation_summary',
        ['model_id'],
        postgresql_using='btree'
    )
    
    # Financial summary view
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_financial_summary AS
        SELECT 
            m.id as model_id,
            m.stage_name,
            DATE_TRUNC('month', t.created_at) as month,
            COUNT(t.id) as transaction_count,
            SUM(t.amount) as gross_revenue,
            SUM(t.platform_fee_amount) as platform_fees,
            SUM(t.agency_fee_amount) as agency_fees,
            SUM(t.model_earnings) as net_earnings
        FROM models m
        JOIN transactions t ON t.model_id = m.id
        WHERE t.status = 'completed'
        GROUP BY m.id, m.stage_name, DATE_TRUNC('month', t.created_at)
    """)
    
    op.create_index(
        'idx_mv_financial_summary_model_month',
        'mv_financial_summary',
        ['model_id', 'month'],
        postgresql_using='btree'
    )
    
    # Create archive table for old messages
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages_archive (
            LIKE messages INCLUDING ALL
        ) PARTITION BY RANGE (created_at)
    """)
    
    # Update table statistics targets for important columns
    op.execute("ALTER TABLE conversations ALTER COLUMN model_id SET STATISTICS 1000")
    op.execute("ALTER TABLE conversations ALTER COLUMN status SET STATISTICS 1000")
    op.execute("ALTER TABLE messages ALTER COLUMN conversation_id SET STATISTICS 1000")
    op.execute("ALTER TABLE messages ALTER COLUMN sender_type SET STATISTICS 1000")
    op.execute("ALTER TABLE transactions ALTER COLUMN model_id SET STATISTICS 1000")
    op.execute("ALTER TABLE users ALTER COLUMN agency_id SET STATISTICS 1000")
    
    # Configure autovacuum for high-activity tables
    op.execute("""
        ALTER TABLE messages SET (
            autovacuum_vacuum_scale_factor = 0.1,
            autovacuum_analyze_scale_factor = 0.05
        )
    """)
    
    op.execute("""
        ALTER TABLE conversations SET (
            autovacuum_vacuum_scale_factor = 0.1,
            autovacuum_analyze_scale_factor = 0.05
        )
    """)
    
    op.execute("""
        ALTER TABLE email_queue SET (
            autovacuum_vacuum_scale_factor = 0.1,
            autovacuum_analyze_scale_factor = 0.05
        )
    """)
    
    # Create monitoring function
    op.execute("""
        CREATE OR REPLACE FUNCTION get_table_sizes()
        RETURNS TABLE(
            table_name text,
            total_size text,
            table_size text,
            indexes_size text,
            toast_size text
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT 
                schemaname||'.'||tablename AS table_name,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
                pg_size_pretty(pg_table_size(schemaname||'.'||tablename)) AS table_size,
                pg_size_pretty(pg_indexes_size(schemaname||'.'||tablename)) AS indexes_size,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - 
                               pg_table_size(schemaname||'.'||tablename) - 
                               pg_indexes_size(schemaname||'.'||tablename)) AS toast_size
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade():
    # Drop monitoring function
    op.execute("DROP FUNCTION IF EXISTS get_table_sizes()")
    
    # Drop materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_financial_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_conversation_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_model_stats CASCADE")
    
    # Drop archive table
    op.execute("DROP TABLE IF EXISTS messages_archive CASCADE")
    
    # Drop triggers
    tables_with_updated_at = [
        'users', 'models', 'conversations', 'messages',
        'transactions', 'payouts', 'email_queue', 'email_preferences'
    ]
    for table in tables_with_updated_at:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table}")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    
    # Drop indexes (in reverse order)
    op.drop_index('idx_messages_flagged', 'messages')
    op.drop_index('idx_messages_unread_fan', 'messages')
    op.drop_index('idx_email_logs_email_event', 'email_logs')
    op.drop_index('idx_email_queue_status_priority_scheduled', 'email_queue')
    op.drop_index('idx_models_stage_name_trgm', 'models')
    op.drop_index('idx_models_agency_active_approved', 'models')
    op.drop_index('idx_users_agency_role_active', 'users')
    op.drop_index('idx_users_email_lower', 'users')
    op.drop_index('idx_earnings_model_period', 'earnings')
    op.drop_index('idx_payouts_model_status_date', 'payouts')
    op.drop_index('idx_transactions_type_status', 'transactions')
    op.drop_index('idx_transactions_model_date', 'transactions')
    op.drop_index('idx_conversations_fan_username_trgm', 'conversations')
    op.drop_index('idx_conversations_assigned_status', 'conversations')
    op.drop_index('idx_conversations_model_status_last_msg', 'conversations')
    op.drop_index('idx_messages_conversation_sender', 'messages')
    op.drop_index('idx_messages_sender_type_created', 'messages')
    op.drop_index('idx_messages_conversation_created', 'messages')