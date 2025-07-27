"""Database optimization - add indexes and improve query performance

Revision ID: 004_database_optimization
Revises: 003_add_crypto_payments
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_database_optimization'
down_revision = '003_add_crypto_payments'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes and optimize database performance."""
    
    # Core domain indexes
    
    # Users table - additional indexes for common queries
    op.create_index('idx_users_agency_role', 'users', ['agency_id', 'role'])
    op.create_index('idx_users_active_verified', 'users', ['is_active', 'is_verified'])
    op.create_index('idx_users_last_login', 'users', ['last_login'])
    
    # Sessions table - optimize for cleanup and active sessions
    op.create_index('idx_sessions_expires_active', 'sessions', ['expires_at', 'is_active'])
    
    # Notifications - optimize for unread queries
    op.create_index('idx_notifications_user_read', 'notifications', ['user_id', 'read', 'created_at'])
    
    # Audit logs - composite index for filtering
    op.create_index('idx_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id', 'created_at'])
    
    # Model profiles - optimize lookups
    op.create_index('idx_model_profiles_agency_active', 'model_profiles', ['agency_id', 'is_active'])
    op.create_index('idx_model_profiles_last_sync', 'model_profiles', ['last_sync_at'])
    op.create_index('idx_model_profiles_earnings', 'model_profiles', ['total_earnings'])
    
    # Fans - optimize for engagement queries
    op.create_index('idx_fans_active_subscribers', 'fans', ['model_id', 'is_subscriber', 'is_paying'])
    op.create_index('idx_fans_last_active', 'fans', ['model_id', 'last_active_at'])
    op.create_index('idx_fans_total_spent', 'fans', ['model_id', 'total_spent'])
    
    # Financial optimization
    
    # Financial transactions - composite indexes for common queries
    op.create_index('idx_financial_transactions_model_type_date', 'financial_transactions', 
                   ['model_id', 'type', 'transaction_date'])
    op.create_index('idx_financial_transactions_balance', 'financial_transactions',
                   ['user_id', 'balance_after', 'transaction_date'])
    
    # Billing cycles - optimize for period queries
    op.create_index('idx_billing_cycles_agency_closed', 'billing_cycles', 
                   ['agency_id', 'is_closed', 'cycle_end'])
    
    # Payouts - optimize for processing queries
    op.create_index('idx_payouts_scheduled', 'payouts', 
                   ['status', 'scheduled_at'],
                   postgresql_where="status IN ('pending', 'processing')")
    
    # Payout schedules - optimize for next payout calculation
    op.create_index('idx_payout_schedules_next_active', 'payout_schedules',
                   ['next_payout_date', 'is_active'],
                   postgresql_where='is_active = true')
    
    # Invoices - optimize for outstanding invoices
    op.create_index('idx_invoices_outstanding', 'invoices',
                   ['agency_id', 'status', 'due_date'],
                   postgresql_where="status IN ('sent', 'overdue')")
    
    # Analytics optimization
    
    # Metric snapshots - optimize for time-series queries
    op.create_index('idx_metric_snapshots_model_date_range', 'metric_snapshots',
                   ['model_id', 'timestamp'])
    op.execute("""
        CREATE INDEX idx_metric_snapshots_timestamp_brin 
        ON metric_snapshots USING brin(timestamp)
    """)
    
    # Revenue transactions - optimize for aggregation
    op.create_index('idx_revenue_transactions_model_type_date', 'revenue_transactions',
                   ['model_id', 'transaction_type', 'transaction_date'])
    op.create_index('idx_revenue_transactions_fan_date', 'revenue_transactions',
                   ['fan_id', 'transaction_date'])
    op.execute("""
        CREATE INDEX idx_revenue_transactions_date_brin 
        ON revenue_transactions USING brin(transaction_date)
    """)
    
    # Content performance - optimize for top content queries
    op.create_index('idx_content_performance_revenue', 'content_performance',
                   ['model_id', 'total_revenue', 'published_at'])
    op.create_index('idx_content_performance_engagement', 'content_performance',
                   ['model_id', 'views', 'likes'])
    
    # Fan spending history - optimize for cohort analysis
    op.create_index('idx_fan_spending_total', 'fan_spending_history',
                   ['model_id', 'total_amount', 'period_start'])
    
    # Add partial indexes for active records
    op.create_index('idx_active_model_profiles', 'model_profiles', ['agency_id'],
                   postgresql_where='is_active = true')
    op.create_index('idx_active_users', 'users', ['agency_id'],
                   postgresql_where='is_active = true AND is_verified = true')
    op.create_index('idx_paying_fans', 'fans', ['model_id'],
                   postgresql_where='is_paying = true')
    
    # Create materialized view for model revenue summary
    op.execute("""
        CREATE MATERIALIZED VIEW model_revenue_summary AS
        SELECT 
            m.id as model_id,
            m.agency_id,
            m.onlyfans_username,
            COUNT(DISTINCT f.id) as total_fans,
            COUNT(DISTINCT f.id) FILTER (WHERE f.is_paying = true) as paying_fans,
            COALESCE(SUM(ft.amount) FILTER (WHERE ft.type = 'revenue'), 0) as total_revenue,
            COALESCE(SUM(ft.amount) FILTER (WHERE ft.type = 'revenue' AND 
                ft.transaction_date >= CURRENT_DATE - INTERVAL '30 days'), 0) as revenue_30d,
            COALESCE(SUM(ft.amount) FILTER (WHERE ft.type = 'revenue' AND 
                ft.transaction_date >= CURRENT_DATE - INTERVAL '7 days'), 0) as revenue_7d,
            MAX(ft.transaction_date) as last_transaction_date
        FROM model_profiles m
        LEFT JOIN fans f ON f.model_id = m.id
        LEFT JOIN financial_transactions ft ON ft.model_id = m.id
        WHERE m.is_active = true
        GROUP BY m.id, m.agency_id, m.onlyfans_username
    """)
    
    op.create_index('idx_model_revenue_summary_model', 'model_revenue_summary', ['model_id'])
    op.create_index('idx_model_revenue_summary_agency', 'model_revenue_summary', ['agency_id'])
    
    # Create materialized view for daily metrics
    op.execute("""
        CREATE MATERIALIZED VIEW daily_metrics AS
        SELECT 
            DATE(ms.timestamp) as date,
            ms.model_id,
            MAX(ms.total_subscribers) as subscribers_end,
            MAX(ms.paying_subscribers) as paying_subscribers_end,
            MAX(ms.total_revenue) - MIN(ms.total_revenue) as daily_revenue,
            MAX(ms.new_subscribers) as new_subscribers,
            MAX(ms.lost_subscribers) as lost_subscribers,
            AVG(ms.conversion_rate) as avg_conversion_rate
        FROM metric_snapshots ms
        GROUP BY DATE(ms.timestamp), ms.model_id
    """)
    
    op.create_index('idx_daily_metrics_model_date', 'daily_metrics', ['model_id', 'date'])
    op.create_index('idx_daily_metrics_date', 'daily_metrics', ['date'])
    
    # Add table partitioning for high-volume tables
    
    # Partition revenue_transactions by month
    op.execute("""
        -- Create parent table for partitioned revenue transactions
        CREATE TABLE revenue_transactions_partitioned (LIKE revenue_transactions INCLUDING ALL)
        PARTITION BY RANGE (transaction_date);
        
        -- Create partitions for the last 6 months and next 3 months
        CREATE TABLE revenue_transactions_y2024m07 PARTITION OF revenue_transactions_partitioned
            FOR VALUES FROM ('2024-07-01') TO ('2024-08-01');
        CREATE TABLE revenue_transactions_y2024m08 PARTITION OF revenue_transactions_partitioned
            FOR VALUES FROM ('2024-08-01') TO ('2024-09-01');
        CREATE TABLE revenue_transactions_y2024m09 PARTITION OF revenue_transactions_partitioned
            FOR VALUES FROM ('2024-09-01') TO ('2024-10-01');
        CREATE TABLE revenue_transactions_y2024m10 PARTITION OF revenue_transactions_partitioned
            FOR VALUES FROM ('2024-10-01') TO ('2024-11-01');
        CREATE TABLE revenue_transactions_y2024m11 PARTITION OF revenue_transactions_partitioned
            FOR VALUES FROM ('2024-11-01') TO ('2024-12-01');
        CREATE TABLE revenue_transactions_y2024m12 PARTITION OF revenue_transactions_partitioned
            FOR VALUES FROM ('2024-12-01') TO ('2025-01-01');
        CREATE TABLE revenue_transactions_y2025m01 PARTITION OF revenue_transactions_partitioned
            FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
        CREATE TABLE revenue_transactions_y2025m02 PARTITION OF revenue_transactions_partitioned
            FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
        CREATE TABLE revenue_transactions_y2025m03 PARTITION OF revenue_transactions_partitioned
            FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
    """)
    
    # Add query optimization settings
    op.execute("""
        -- Enable query parallelization for analytics queries
        ALTER TABLE metric_snapshots SET (parallel_workers = 4);
        ALTER TABLE revenue_transactions SET (parallel_workers = 4);
        ALTER TABLE financial_transactions SET (parallel_workers = 4);
        
        -- Increase statistics target for important columns
        ALTER TABLE model_profiles ALTER COLUMN agency_id SET STATISTICS 1000;
        ALTER TABLE fans ALTER COLUMN model_id SET STATISTICS 1000;
        ALTER TABLE financial_transactions ALTER COLUMN model_id SET STATISTICS 1000;
        ALTER TABLE metric_snapshots ALTER COLUMN model_id SET STATISTICS 1000;
        
        -- Update table statistics
        ANALYZE;
    """)
    
    # Create stored procedures for common operations
    
    # Procedure to refresh materialized views
    op.execute("""
        CREATE OR REPLACE PROCEDURE refresh_analytics_views()
        LANGUAGE plpgsql
        AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY model_revenue_summary;
            REFRESH MATERIALIZED VIEW CONCURRENTLY daily_metrics;
        END;
        $$;
    """)
    
    # Function to calculate model balance
    op.execute("""
        CREATE OR REPLACE FUNCTION calculate_model_balance(p_model_id UUID)
        RETURNS NUMERIC
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_balance NUMERIC;
        BEGIN
            SELECT COALESCE(SUM(
                CASE 
                    WHEN type IN ('revenue', 'adjustment') THEN amount - COALESCE(commission_amount, 0)
                    WHEN type = 'payout' THEN -amount
                    ELSE 0
                END
            ), 0)
            INTO v_balance
            FROM financial_transactions
            WHERE model_id = p_model_id;
            
            RETURN v_balance;
        END;
        $$;
    """)
    
    # Function for efficient fan metrics calculation
    op.execute("""
        CREATE OR REPLACE FUNCTION get_fan_metrics(p_model_id UUID, p_date_from DATE, p_date_to DATE)
        RETURNS TABLE (
            total_fans INTEGER,
            paying_fans INTEGER,
            new_fans INTEGER,
            churned_fans INTEGER,
            avg_fan_value NUMERIC
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            WITH fan_stats AS (
                SELECT 
                    COUNT(*) as total_fans,
                    COUNT(*) FILTER (WHERE is_paying = true) as paying_fans,
                    COUNT(*) FILTER (WHERE created_at BETWEEN p_date_from AND p_date_to) as new_fans
                FROM fans
                WHERE model_id = p_model_id
            ),
            revenue_stats AS (
                SELECT 
                    COUNT(DISTINCT fan_id) as revenue_fans,
                    AVG(amount) as avg_transaction
                FROM revenue_transactions
                WHERE model_id = p_model_id
                    AND transaction_date BETWEEN p_date_from AND p_date_to
            ),
            churn_stats AS (
                SELECT COUNT(*) as churned_fans
                FROM fans
                WHERE model_id = p_model_id
                    AND is_subscriber = false
                    AND last_active_at BETWEEN p_date_from AND p_date_to
            )
            SELECT 
                fs.total_fans,
                fs.paying_fans,
                fs.new_fans,
                cs.churned_fans,
                COALESCE(rs.avg_transaction, 0) as avg_fan_value
            FROM fan_stats fs
            CROSS JOIN revenue_stats rs
            CROSS JOIN churn_stats cs;
        END;
        $$;
    """)


def downgrade() -> None:
    """Remove optimization indexes and objects."""
    
    # Drop stored procedures and functions
    op.execute("DROP FUNCTION IF EXISTS get_fan_metrics(UUID, DATE, DATE)")
    op.execute("DROP FUNCTION IF EXISTS calculate_model_balance(UUID)")
    op.execute("DROP PROCEDURE IF EXISTS refresh_analytics_views()")
    
    # Drop materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS daily_metrics")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS model_revenue_summary")
    
    # Drop partitioned table
    op.execute("DROP TABLE IF EXISTS revenue_transactions_partitioned CASCADE")
    
    # Drop indexes in reverse order
    
    # Analytics indexes
    op.drop_index('idx_fan_spending_total', 'fan_spending_history')
    op.drop_index('idx_content_performance_engagement', 'content_performance')
    op.drop_index('idx_content_performance_revenue', 'content_performance')
    op.drop_index('idx_revenue_transactions_date_brin', 'revenue_transactions')
    op.drop_index('idx_revenue_transactions_fan_date', 'revenue_transactions')
    op.drop_index('idx_revenue_transactions_model_type_date', 'revenue_transactions')
    op.drop_index('idx_metric_snapshots_timestamp_brin', 'metric_snapshots')
    op.drop_index('idx_metric_snapshots_model_date_range', 'metric_snapshots')
    
    # Financial indexes
    op.drop_index('idx_invoices_outstanding', 'invoices')
    op.drop_index('idx_payout_schedules_next_active', 'payout_schedules')
    op.drop_index('idx_payouts_scheduled', 'payouts')
    op.drop_index('idx_billing_cycles_agency_closed', 'billing_cycles')
    op.drop_index('idx_financial_transactions_balance', 'financial_transactions')
    op.drop_index('idx_financial_transactions_model_type_date', 'financial_transactions')
    
    # Core domain indexes
    op.drop_index('idx_paying_fans', 'fans')
    op.drop_index('idx_active_users', 'users')
    op.drop_index('idx_active_model_profiles', 'model_profiles')
    op.drop_index('idx_fans_total_spent', 'fans')
    op.drop_index('idx_fans_last_active', 'fans')
    op.drop_index('idx_fans_active_subscribers', 'fans')
    op.drop_index('idx_model_profiles_earnings', 'model_profiles')
    op.drop_index('idx_model_profiles_last_sync', 'model_profiles')
    op.drop_index('idx_model_profiles_agency_active', 'model_profiles')
    op.drop_index('idx_audit_logs_resource', 'audit_logs')
    op.drop_index('idx_notifications_user_read', 'notifications')
    op.drop_index('idx_sessions_expires_active', 'sessions')
    op.drop_index('idx_users_last_login', 'users')
    op.drop_index('idx_users_active_verified', 'users')
    op.drop_index('idx_users_agency_role', 'users')