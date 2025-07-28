"""Add performance indexes

Revision ID: 007_performance_indexes
Revises: 006_scheduled_reports
Create Date: 2025-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '007_performance_indexes'
down_revision = '006_scheduled_reports'
branch_labels = None
depends_on = None


def upgrade():
    # Users table indexes
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_created_at', 'users', ['created_at'])
    op.create_index('idx_users_is_active', 'users', ['is_active'])
    
    # Agencies table indexes
    op.create_index('idx_agencies_created_at', 'agencies', ['created_at'])
    op.create_index('idx_agencies_is_active', 'agencies', ['is_active'])
    
    # Models table indexes
    op.create_index('idx_models_agency_id', 'models', ['agency_id'])
    op.create_index('idx_models_onlyfans_id', 'models', ['onlyfans_id'])
    op.create_index('idx_models_created_at', 'models', ['created_at'])
    op.create_index('idx_models_is_active', 'models', ['is_active'])
    
    # Fans table indexes
    op.create_index('idx_fans_model_id', 'fans', ['model_id'])
    op.create_index('idx_fans_onlyfans_id', 'fans', ['onlyfans_id'])
    op.create_index('idx_fans_created_at', 'fans', ['created_at'])
    op.create_index('idx_fans_last_activity', 'fans', ['last_activity'])
    op.create_index('idx_fans_subscription_status', 'fans', ['subscription_status'])
    op.create_index('idx_fans_total_spent', 'fans', ['total_spent'])
    
    # Compound index for fan lookups
    op.create_index('idx_fans_model_status', 'fans', ['model_id', 'subscription_status'])
    op.create_index('idx_fans_model_spent', 'fans', ['model_id', 'total_spent'])
    
    # Messages table indexes
    op.create_index('idx_messages_model_id', 'messages', ['model_id'])
    op.create_index('idx_messages_fan_id', 'messages', ['fan_id'])
    op.create_index('idx_messages_created_at', 'messages', ['created_at'])
    op.create_index('idx_messages_is_read', 'messages', ['is_read'])
    op.create_index('idx_messages_message_type', 'messages', ['message_type'])
    
    # Compound indexes for message queries
    op.create_index('idx_messages_model_fan', 'messages', ['model_id', 'fan_id'])
    op.create_index('idx_messages_fan_created', 'messages', ['fan_id', 'created_at'])
    op.create_index('idx_messages_model_unread', 'messages', ['model_id', 'is_read'])
    
    # Payments table indexes
    op.create_index('idx_payments_model_id', 'payments', ['model_id'])
    op.create_index('idx_payments_fan_id', 'payments', ['fan_id'])
    op.create_index('idx_payments_created_at', 'payments', ['created_at'])
    op.create_index('idx_payments_payment_type', 'payments', ['payment_type'])
    op.create_index('idx_payments_status', 'payments', ['status'])
    op.create_index('idx_payments_stripe_payment_id', 'payments', ['stripe_payment_id'])
    
    # Compound indexes for payment analytics
    op.create_index('idx_payments_model_date', 'payments', ['model_id', 'created_at'])
    op.create_index('idx_payments_model_type', 'payments', ['model_id', 'payment_type'])
    
    # Analytics table indexes
    op.create_index('idx_analytics_model_id', 'analytics', ['model_id'])
    op.create_index('idx_analytics_date', 'analytics', ['date'])
    op.create_index('idx_analytics_metric_type', 'analytics', ['metric_type'])
    
    # Compound index for analytics queries
    op.create_index('idx_analytics_model_date_type', 'analytics', ['model_id', 'date', 'metric_type'])
    
    # Transactions table indexes
    op.create_index('idx_transactions_agency_id', 'transactions', ['agency_id'])
    op.create_index('idx_transactions_model_id', 'transactions', ['model_id'])
    op.create_index('idx_transactions_created_at', 'transactions', ['created_at'])
    op.create_index('idx_transactions_transaction_type', 'transactions', ['transaction_type'])
    op.create_index('idx_transactions_status', 'transactions', ['status'])
    
    # Compound indexes for financial queries
    op.create_index('idx_transactions_agency_date', 'transactions', ['agency_id', 'created_at'])
    op.create_index('idx_transactions_model_date', 'transactions', ['model_id', 'created_at'])
    
    # Commission tiers indexes
    op.create_index('idx_commission_tiers_agency_id', 'commission_tiers', ['agency_id'])
    op.create_index('idx_commission_tiers_min_revenue', 'commission_tiers', ['min_revenue'])
    
    # Payment gateways indexes
    op.create_index('idx_payment_gateways_agency_id', 'payment_gateways', ['agency_id'])
    op.create_index('idx_payment_gateways_is_active', 'payment_gateways', ['is_active'])
    
    # Payouts indexes
    op.create_index('idx_payouts_agency_id', 'payouts', ['agency_id'])
    op.create_index('idx_payouts_model_id', 'payouts', ['model_id'])
    op.create_index('idx_payouts_created_at', 'payouts', ['created_at'])
    op.create_index('idx_payouts_status', 'payouts', ['status'])
    op.create_index('idx_payouts_scheduled_date', 'payouts', ['scheduled_date'])
    
    # Scheduled messages indexes
    op.create_index('idx_scheduled_messages_model_id', 'scheduled_messages', ['model_id'])
    op.create_index('idx_scheduled_messages_scheduled_time', 'scheduled_messages', ['scheduled_time'])
    op.create_index('idx_scheduled_messages_status', 'scheduled_messages', ['status'])
    
    # Message templates indexes
    op.create_index('idx_message_templates_agency_id', 'message_templates', ['agency_id'])
    op.create_index('idx_message_templates_category', 'message_templates', ['category'])
    op.create_index('idx_message_templates_is_active', 'message_templates', ['is_active'])
    
    # AI response history indexes
    op.create_index('idx_ai_response_history_model_id', 'ai_response_history', ['model_id'])
    op.create_index('idx_ai_response_history_fan_id', 'ai_response_history', ['fan_id'])
    op.create_index('idx_ai_response_history_created_at', 'ai_response_history', ['created_at'])
    
    # Canned responses indexes
    op.create_index('idx_canned_responses_agency_id', 'canned_responses', ['agency_id'])
    op.create_index('idx_canned_responses_category', 'canned_responses', ['category'])
    op.create_index('idx_canned_responses_is_active', 'canned_responses', ['is_active'])
    
    # Export jobs indexes
    op.create_index('idx_export_jobs_user_id', 'export_jobs', ['user_id'])
    op.create_index('idx_export_jobs_created_at', 'export_jobs', ['created_at'])
    op.create_index('idx_export_jobs_status', 'export_jobs', ['status'])
    
    # Custom reports indexes
    op.create_index('idx_custom_reports_user_id', 'custom_reports', ['user_id'])
    op.create_index('idx_custom_reports_is_public', 'custom_reports', ['is_public'])
    op.create_index('idx_custom_reports_created_at', 'custom_reports', ['created_at'])
    
    # Scheduled reports indexes
    op.create_index('idx_scheduled_reports_user_id', 'scheduled_reports', ['user_id'])
    op.create_index('idx_scheduled_reports_is_active', 'scheduled_reports', ['is_active'])
    op.create_index('idx_scheduled_reports_next_run', 'scheduled_reports', ['next_run'])
    
    # Full-text search indexes (PostgreSQL specific)
    op.execute("""
        CREATE INDEX idx_fans_search ON fans 
        USING gin(to_tsvector('english', COALESCE(display_name, '') || ' ' || COALESCE(bio, '')))
    """)
    
    op.execute("""
        CREATE INDEX idx_messages_search ON messages 
        USING gin(to_tsvector('english', content))
    """)
    
    op.execute("""
        CREATE INDEX idx_models_search ON models 
        USING gin(to_tsvector('english', COALESCE(display_name, '') || ' ' || COALESCE(bio, '')))
    """)
    
    # Partial indexes for common queries
    op.create_index('idx_messages_unread', 'messages', ['model_id', 'fan_id'], 
                    postgresql_where=sa.text('is_read = false'))
    
    op.create_index('idx_fans_active_subs', 'fans', ['model_id', 'last_activity'], 
                    postgresql_where=sa.text("subscription_status = 'active'"))
    
    op.create_index('idx_payments_completed', 'payments', ['model_id', 'created_at'], 
                    postgresql_where=sa.text("status = 'completed'"))
    
    op.create_index('idx_scheduled_messages_pending', 'scheduled_messages', ['scheduled_time'], 
                    postgresql_where=sa.text("status = 'pending'"))
    
    # BRIN indexes for time-series data (PostgreSQL specific)
    op.execute("CREATE INDEX idx_analytics_date_brin ON analytics USING brin(date)")
    op.execute("CREATE INDEX idx_messages_created_brin ON messages USING brin(created_at)")
    op.execute("CREATE INDEX idx_payments_created_brin ON payments USING brin(created_at)")
    op.execute("CREATE INDEX idx_transactions_created_brin ON transactions USING brin(created_at)")


def downgrade():
    # Drop all indexes in reverse order
    
    # BRIN indexes
    op.execute("DROP INDEX IF EXISTS idx_transactions_created_brin")
    op.execute("DROP INDEX IF EXISTS idx_payments_created_brin")
    op.execute("DROP INDEX IF EXISTS idx_messages_created_brin")
    op.execute("DROP INDEX IF EXISTS idx_analytics_date_brin")
    
    # Partial indexes
    op.drop_index('idx_scheduled_messages_pending', 'scheduled_messages')
    op.drop_index('idx_payments_completed', 'payments')
    op.drop_index('idx_fans_active_subs', 'fans')
    op.drop_index('idx_messages_unread', 'messages')
    
    # Full-text search indexes
    op.execute("DROP INDEX IF EXISTS idx_models_search")
    op.execute("DROP INDEX IF EXISTS idx_messages_search")
    op.execute("DROP INDEX IF EXISTS idx_fans_search")
    
    # Regular indexes (in reverse order of creation)
    op.drop_index('idx_scheduled_reports_next_run', 'scheduled_reports')
    op.drop_index('idx_scheduled_reports_is_active', 'scheduled_reports')
    op.drop_index('idx_scheduled_reports_user_id', 'scheduled_reports')
    
    op.drop_index('idx_custom_reports_created_at', 'custom_reports')
    op.drop_index('idx_custom_reports_is_public', 'custom_reports')
    op.drop_index('idx_custom_reports_user_id', 'custom_reports')
    
    op.drop_index('idx_export_jobs_status', 'export_jobs')
    op.drop_index('idx_export_jobs_created_at', 'export_jobs')
    op.drop_index('idx_export_jobs_user_id', 'export_jobs')
    
    op.drop_index('idx_canned_responses_is_active', 'canned_responses')
    op.drop_index('idx_canned_responses_category', 'canned_responses')
    op.drop_index('idx_canned_responses_agency_id', 'canned_responses')
    
    op.drop_index('idx_ai_response_history_created_at', 'ai_response_history')
    op.drop_index('idx_ai_response_history_fan_id', 'ai_response_history')
    op.drop_index('idx_ai_response_history_model_id', 'ai_response_history')
    
    op.drop_index('idx_message_templates_is_active', 'message_templates')
    op.drop_index('idx_message_templates_category', 'message_templates')
    op.drop_index('idx_message_templates_agency_id', 'message_templates')
    
    op.drop_index('idx_scheduled_messages_status', 'scheduled_messages')
    op.drop_index('idx_scheduled_messages_scheduled_time', 'scheduled_messages')
    op.drop_index('idx_scheduled_messages_model_id', 'scheduled_messages')
    
    op.drop_index('idx_payouts_scheduled_date', 'payouts')
    op.drop_index('idx_payouts_status', 'payouts')
    op.drop_index('idx_payouts_created_at', 'payouts')
    op.drop_index('idx_payouts_model_id', 'payouts')
    op.drop_index('idx_payouts_agency_id', 'payouts')
    
    op.drop_index('idx_payment_gateways_is_active', 'payment_gateways')
    op.drop_index('idx_payment_gateways_agency_id', 'payment_gateways')
    
    op.drop_index('idx_commission_tiers_min_revenue', 'commission_tiers')
    op.drop_index('idx_commission_tiers_agency_id', 'commission_tiers')
    
    op.drop_index('idx_transactions_model_date', 'transactions')
    op.drop_index('idx_transactions_agency_date', 'transactions')
    op.drop_index('idx_transactions_status', 'transactions')
    op.drop_index('idx_transactions_transaction_type', 'transactions')
    op.drop_index('idx_transactions_created_at', 'transactions')
    op.drop_index('idx_transactions_model_id', 'transactions')
    op.drop_index('idx_transactions_agency_id', 'transactions')
    
    op.drop_index('idx_analytics_model_date_type', 'analytics')
    op.drop_index('idx_analytics_metric_type', 'analytics')
    op.drop_index('idx_analytics_date', 'analytics')
    op.drop_index('idx_analytics_model_id', 'analytics')
    
    op.drop_index('idx_payments_model_type', 'payments')
    op.drop_index('idx_payments_model_date', 'payments')
    op.drop_index('idx_payments_stripe_payment_id', 'payments')
    op.drop_index('idx_payments_status', 'payments')
    op.drop_index('idx_payments_payment_type', 'payments')
    op.drop_index('idx_payments_created_at', 'payments')
    op.drop_index('idx_payments_fan_id', 'payments')
    op.drop_index('idx_payments_model_id', 'payments')
    
    op.drop_index('idx_messages_model_unread', 'messages')
    op.drop_index('idx_messages_fan_created', 'messages')
    op.drop_index('idx_messages_model_fan', 'messages')
    op.drop_index('idx_messages_message_type', 'messages')
    op.drop_index('idx_messages_is_read', 'messages')
    op.drop_index('idx_messages_created_at', 'messages')
    op.drop_index('idx_messages_fan_id', 'messages')
    op.drop_index('idx_messages_model_id', 'messages')
    
    op.drop_index('idx_fans_model_spent', 'fans')
    op.drop_index('idx_fans_model_status', 'fans')
    op.drop_index('idx_fans_total_spent', 'fans')
    op.drop_index('idx_fans_subscription_status', 'fans')
    op.drop_index('idx_fans_last_activity', 'fans')
    op.drop_index('idx_fans_created_at', 'fans')
    op.drop_index('idx_fans_onlyfans_id', 'fans')
    op.drop_index('idx_fans_model_id', 'fans')
    
    op.drop_index('idx_models_is_active', 'models')
    op.drop_index('idx_models_created_at', 'models')
    op.drop_index('idx_models_onlyfans_id', 'models')
    op.drop_index('idx_models_agency_id', 'models')
    
    op.drop_index('idx_agencies_is_active', 'agencies')
    op.drop_index('idx_agencies_created_at', 'agencies')
    
    op.drop_index('idx_users_is_active', 'users')
    op.drop_index('idx_users_created_at', 'users')
    op.drop_index('idx_users_username', 'users')
    op.drop_index('idx_users_email', 'users')