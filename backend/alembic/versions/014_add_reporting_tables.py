"""Add advanced reporting tables

Revision ID: 014_add_reporting_tables
Revises: 008_add_bulk_operations_tables
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '014_add_reporting_tables'
down_revision = '012_add_bulk_operations_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add reporting tables."""
    
    # Create enums
    op.execute("CREATE TYPE reporttype AS ENUM ('revenue', 'user_activity', 'model_performance', 'transaction', 'payout', 'engagement', 'conversion', 'custom', 'executive')")
    op.execute("CREATE TYPE reportformat AS ENUM ('pdf', 'excel', 'csv', 'json', 'html')")
    op.execute("CREATE TYPE reportstatus AS ENUM ('draft', 'pending', 'generating', 'completed', 'failed', 'scheduled')")
    
    # Create reports table
    op.create_table('reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', sa.Enum('revenue', 'user_activity', 'model_performance', 'transaction', 'payout', 'engagement', 'conversion', 'custom', 'executive', name='reporttype'), nullable=False),
        sa.Column('query_config', sa.JSON(), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('columns', sa.JSON(), nullable=True),
        sa.Column('grouping', sa.JSON(), nullable=True),
        sa.Column('sorting', sa.JSON(), nullable=True),
        sa.Column('aggregations', sa.JSON(), nullable=True),
        sa.Column('chart_config', sa.JSON(), nullable=True),
        sa.Column('layout_config', sa.JSON(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('is_template', sa.Boolean(), nullable=True),
        sa.Column('template_category', sa.String(length=50), nullable=True),
        sa.Column('cache_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('estimated_runtime_seconds', sa.Integer(), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for reports
    op.create_index('idx_report_agency', 'reports', ['agency_id'], unique=False)
    op.create_index('idx_report_type', 'reports', ['report_type'], unique=False)
    op.create_index('idx_report_template', 'reports', ['is_template'], unique=False)
    op.create_index('idx_report_created', 'reports', ['created_at'], unique=False)
    
    # Create report_shares association table
    op.create_table('report_shares',
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('permission', sa.String(length=20), nullable=True),
        sa.Column('shared_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], )
    )
    
    # Create report_executions table
    op.create_table('report_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('draft', 'pending', 'generating', 'completed', 'failed', 'scheduled', name='reportstatus'), nullable=True),
        sa.Column('format', sa.Enum('pdf', 'excel', 'csv', 'json', 'html', name='reportformat'), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('filters_applied', sa.JSON(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('preview_data', sa.JSON(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('query_time_ms', sa.Integer(), nullable=True),
        sa.Column('render_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True),
        sa.Column('cached', sa.Boolean(), nullable=True),
        sa.Column('cache_hit', sa.Boolean(), nullable=True),
        sa.Column('cache_key', sa.String(length=255), nullable=True),
        sa.Column('executed_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['executed_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for report_executions
    op.create_index('idx_report_execution_report', 'report_executions', ['report_id'], unique=False)
    op.create_index('idx_report_execution_status', 'report_executions', ['status'], unique=False)
    op.create_index('idx_report_execution_created', 'report_executions', ['created_at'], unique=False)
    op.create_index('idx_report_execution_cache', 'report_executions', ['cache_key'], unique=False)
    
    # Create report_schedules table
    op.create_table('report_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cron_expression', sa.String(length=100), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('format', sa.Enum('pdf', 'excel', 'csv', 'json', 'html', name='reportformat'), nullable=False),
        sa.Column('delivery_method', sa.String(length=20), nullable=True),
        sa.Column('delivery_config', sa.JSON(), nullable=True),
        sa.Column('recipient_users', sa.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('recipient_emails', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for report_schedules
    op.create_index('idx_report_schedule_active', 'report_schedules', ['is_active'], unique=False)
    op.create_index('idx_report_schedule_next_run', 'report_schedules', ['next_run_at'], unique=False)
    
    # Create report_templates table
    op.create_table('report_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('report_type', sa.Enum('revenue', 'user_activity', 'model_performance', 'transaction', 'payout', 'engagement', 'conversion', 'custom', 'executive', name='reporttype'), nullable=False),
        sa.Column('base_query', sa.Text(), nullable=True),
        sa.Column('default_filters', sa.JSON(), nullable=True),
        sa.Column('default_columns', sa.JSON(), nullable=True),
        sa.Column('default_grouping', sa.JSON(), nullable=True),
        sa.Column('default_sorting', sa.JSON(), nullable=True),
        sa.Column('default_aggregations', sa.JSON(), nullable=True),
        sa.Column('default_chart_config', sa.JSON(), nullable=True),
        sa.Column('customizable_fields', sa.JSON(), nullable=True),
        sa.Column('required_parameters', sa.JSON(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('preview_image_url', sa.String(length=500), nullable=True),
        sa.Column('sample_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for report_templates
    op.create_index('idx_report_template_category', 'report_templates', ['category'], unique=False)
    op.create_index('idx_report_template_type', 'report_templates', ['report_type'], unique=False)
    op.create_index('idx_report_template_active', 'report_templates', ['is_active'], unique=False)
    
    # Create report_widgets table
    op.create_table('report_widgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('widget_type', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('position_x', sa.Integer(), nullable=True),
        sa.Column('position_y', sa.Integer(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('data_source', sa.String(length=50), nullable=True),
        sa.Column('custom_query', sa.Text(), nullable=True),
        sa.Column('refresh_interval_seconds', sa.Integer(), nullable=True),
        sa.Column('style_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for report_widgets
    op.create_index('idx_report_widget_report', 'report_widgets', ['report_id'], unique=False)
    
    # Create report_cache table
    op.create_table('report_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cache_key', sa.String(length=255), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('data_type', sa.String(length=20), nullable=False),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('hit_count', sa.Integer(), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cache_key')
    )
    
    # Create indexes for report_cache
    op.create_index('idx_report_cache_key', 'report_cache', ['cache_key'], unique=False)
    op.create_index('idx_report_cache_expires', 'report_cache', ['expires_at'], unique=False)
    op.create_index('idx_report_cache_report', 'report_cache', ['report_id'], unique=False)
    
    # Create report_audit_logs table
    op.create_table('report_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('action_details', sa.JSON(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for report_audit_logs
    op.create_index('idx_report_audit_report', 'report_audit_logs', ['report_id'], unique=False)
    op.create_index('idx_report_audit_user', 'report_audit_logs', ['user_id'], unique=False)
    op.create_index('idx_report_audit_timestamp', 'report_audit_logs', ['timestamp'], unique=False)
    op.create_index('idx_report_audit_action', 'report_audit_logs', ['action'], unique=False)
    
    # Set default values
    op.execute("UPDATE reports SET is_public = false WHERE is_public IS NULL")
    op.execute("UPDATE reports SET is_template = false WHERE is_template IS NULL")
    op.execute("UPDATE reports SET cache_duration_minutes = 60 WHERE cache_duration_minutes IS NULL")
    op.execute("UPDATE reports SET run_count = 0 WHERE run_count IS NULL")
    op.execute("UPDATE report_shares SET permission = 'view' WHERE permission IS NULL")
    op.execute("UPDATE report_executions SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE report_executions SET retry_count = 0 WHERE retry_count IS NULL")
    op.execute("UPDATE report_executions SET cached = false WHERE cached IS NULL")
    op.execute("UPDATE report_executions SET cache_hit = false WHERE cache_hit IS NULL")
    op.execute("UPDATE report_schedules SET timezone = 'UTC' WHERE timezone IS NULL")
    op.execute("UPDATE report_schedules SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE report_schedules SET delivery_method = 'email' WHERE delivery_method IS NULL")
    op.execute("UPDATE report_schedules SET run_count = 0 WHERE run_count IS NULL")
    op.execute("UPDATE report_schedules SET consecutive_failures = 0 WHERE consecutive_failures IS NULL")
    op.execute("UPDATE report_templates SET is_system = false WHERE is_system IS NULL")
    op.execute("UPDATE report_templates SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE report_templates SET usage_count = 0 WHERE usage_count IS NULL")
    op.execute("UPDATE report_widgets SET position_x = 0 WHERE position_x IS NULL")
    op.execute("UPDATE report_widgets SET position_y = 0 WHERE position_y IS NULL")
    op.execute("UPDATE report_widgets SET width = 6 WHERE width IS NULL")
    op.execute("UPDATE report_widgets SET height = 4 WHERE height IS NULL")
    op.execute("UPDATE report_widgets SET data_source = 'report' WHERE data_source IS NULL")
    op.execute("UPDATE report_cache SET hit_count = 0 WHERE hit_count IS NULL")
    
    # Insert default report templates
    op.execute("""
        INSERT INTO report_templates (id, name, description, category, report_type, 
            default_filters, default_columns, is_system, is_active)
        VALUES
        -- Revenue templates
        (gen_random_uuid(), 'Daily Revenue Report', 'Daily revenue breakdown by model and platform', 
            'financial', 'revenue', 
            '{"date_range": "last_30_days"}', 
            '["date", "model_name", "platform", "revenue", "transaction_count"]', 
            true, true),
        
        (gen_random_uuid(), 'Monthly Revenue Summary', 'Monthly revenue summary with trends', 
            'financial', 'revenue', 
            '{"date_range": "last_12_months"}', 
            '["month", "total_revenue", "avg_transaction", "growth_rate"]', 
            true, true),
        
        -- User activity templates
        (gen_random_uuid(), 'User Engagement Report', 'User engagement metrics and activity', 
            'analytics', 'user_activity', 
            '{"active_only": true}', 
            '["user_name", "last_login", "total_spent", "message_count", "engagement_score"]', 
            true, true),
        
        (gen_random_uuid(), 'Chatter Performance', 'Chatter performance metrics', 
            'performance', 'user_activity', 
            '{"role": "chatter"}', 
            '["chatter_name", "conversations", "revenue_generated", "avg_response_time"]', 
            true, true),
        
        -- Model performance templates
        (gen_random_uuid(), 'Model Performance Dashboard', 'Comprehensive model performance metrics', 
            'performance', 'model_performance', 
            '{"period": "last_30_days"}', 
            '["model_name", "revenue", "new_fans", "retention_rate", "avg_tip"]', 
            true, true),
        
        (gen_random_uuid(), 'Top Models Report', 'Top performing models by revenue', 
            'performance', 'model_performance', 
            '{"limit": 20}', 
            '["rank", "model_name", "total_revenue", "growth_percentage", "fan_count"]', 
            true, true),
        
        -- Transaction templates
        (gen_random_uuid(), 'Transaction Detail Report', 'Detailed transaction listing', 
            'financial', 'transaction', 
            '{"status": "completed"}', 
            '["transaction_id", "date", "user", "model", "amount", "type", "status"]', 
            true, true),
        
        -- Payout templates
        (gen_random_uuid(), 'Payout Summary', 'Payout summary by model', 
            'financial', 'payout', 
            '{"status": "completed"}', 
            '["model_name", "payout_date", "amount", "method", "status"]', 
            true, true),
        
        -- Executive templates
        (gen_random_uuid(), 'Executive Dashboard', 'High-level executive summary', 
            'executive', 'executive', 
            '{"period": "last_30_days"}', 
            '["metric", "current_value", "previous_value", "change_percentage", "trend"]', 
            true, true)
    """)


def downgrade() -> None:
    """Remove reporting tables."""
    
    # Drop indexes
    op.drop_index('idx_report_audit_action', table_name='report_audit_logs')
    op.drop_index('idx_report_audit_timestamp', table_name='report_audit_logs')
    op.drop_index('idx_report_audit_user', table_name='report_audit_logs')
    op.drop_index('idx_report_audit_report', table_name='report_audit_logs')
    op.drop_index('idx_report_cache_report', table_name='report_cache')
    op.drop_index('idx_report_cache_expires', table_name='report_cache')
    op.drop_index('idx_report_cache_key', table_name='report_cache')
    op.drop_index('idx_report_widget_report', table_name='report_widgets')
    op.drop_index('idx_report_template_active', table_name='report_templates')
    op.drop_index('idx_report_template_type', table_name='report_templates')
    op.drop_index('idx_report_template_category', table_name='report_templates')
    op.drop_index('idx_report_schedule_next_run', table_name='report_schedules')
    op.drop_index('idx_report_schedule_active', table_name='report_schedules')
    op.drop_index('idx_report_execution_cache', table_name='report_executions')
    op.drop_index('idx_report_execution_created', table_name='report_executions')
    op.drop_index('idx_report_execution_status', table_name='report_executions')
    op.drop_index('idx_report_execution_report', table_name='report_executions')
    op.drop_index('idx_report_created', table_name='reports')
    op.drop_index('idx_report_template', table_name='reports')
    op.drop_index('idx_report_type', table_name='reports')
    op.drop_index('idx_report_agency', table_name='reports')
    
    # Drop tables
    op.drop_table('report_audit_logs')
    op.drop_table('report_cache')
    op.drop_table('report_widgets')
    op.drop_table('report_templates')
    op.drop_table('report_schedules')
    op.drop_table('report_executions')
    op.drop_table('report_shares')
    op.drop_table('reports')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS reportstatus')
    op.execute('DROP TYPE IF EXISTS reportformat')
    op.execute('DROP TYPE IF EXISTS reporttype')