"""Create feature permission tables

Revision ID: create_feature_permissions
Revises: create_rate_limits
Create Date: 2025-01-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = 'create_feature_permissions'
down_revision = 'create_rate_limits'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create feature type enum
    op.execute("""
        CREATE TYPE featuretype AS ENUM (
            'reports', 'exports', 'analytics', 'messaging', 'financial',
            'models', 'chat', 'sync', 'webhooks', 'api', 'admin',
            'settings', 'audit', 'ml', 'integrations'
        )
    """)
    
    # Create report type enum
    op.execute("""
        CREATE TYPE reporttype AS ENUM (
            'earnings', 'performance', 'user_activity', 'model_metrics',
            'chat_analytics', 'revenue_breakdown', 'commission_report',
            'tax_report', 'compliance_report', 'custom'
        )
    """)
    
    # Create export format enum
    op.execute("""
        CREATE TYPE exportformat AS ENUM (
            'csv', 'excel', 'pdf', 'json', 'xml', 'html', 'parquet'
        )
    """)
    
    # Create analytics scope enum
    op.execute("""
        CREATE TYPE analyticsscope AS ENUM (
            'own', 'team', 'agency', 'global'
        )
    """)
    
    # Create message permission enum
    op.execute("""
        CREATE TYPE messagepermission AS ENUM (
            'send_individual', 'send_bulk', 'view_history', 'delete_messages',
            'edit_templates', 'approve_scheduled', 'manage_automation',
            'access_all_chats', 'export_chats'
        )
    """)
    
    # Create data sensitivity enum
    op.execute("""
        CREATE TYPE datasensitivity AS ENUM (
            'public', 'internal', 'confidential', 'restricted', 'top_secret'
        )
    """)
    
    # Create feature_permissions table
    op.create_table(
        'feature_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Basic information
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('feature_type', postgresql.ENUM('reports', 'exports', 'analytics', 'messaging',
                  'financial', 'models', 'chat', 'sync', 'webhooks', 'api', 'admin', 'settings',
                  'audit', 'ml', 'integrations', name='featuretype'), nullable=False, index=True),
        
        # Permission scope
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id'), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agencies.id'), nullable=True),
        
        # Feature-specific permissions
        sa.Column('allowed_actions', postgresql.JSONB(), default=list),
        sa.Column('denied_actions', postgresql.JSONB(), default=list),
        
        # Report permissions
        sa.Column('allowed_report_types', postgresql.JSONB(), default=list),
        sa.Column('max_report_range_days', sa.Integer(), nullable=True),
        sa.Column('can_access_financial_data', sa.Boolean(), default=False),
        sa.Column('can_access_pii_data', sa.Boolean(), default=False),
        sa.Column('data_sensitivity_level', postgresql.ENUM('public', 'internal', 'confidential',
                  'restricted', 'top_secret', name='datasensitivity'), default='internal'),
        
        # Export permissions
        sa.Column('allowed_export_formats', postgresql.JSONB(), default=list),
        sa.Column('max_export_rows', sa.Integer(), nullable=True),
        sa.Column('max_export_size_mb', sa.Integer(), nullable=True),
        sa.Column('export_rate_limit_per_hour', sa.Integer(), default=10),
        sa.Column('can_export_all_data', sa.Boolean(), default=False),
        sa.Column('requires_export_approval', sa.Boolean(), default=False),
        
        # Analytics permissions
        sa.Column('analytics_scope', postgresql.ENUM('own', 'team', 'agency', 'global',
                  name='analyticsscope'), default='own'),
        sa.Column('allowed_metrics', postgresql.JSONB(), default=list),
        sa.Column('can_view_revenue_data', sa.Boolean(), default=False),
        sa.Column('can_view_cost_data', sa.Boolean(), default=False),
        sa.Column('can_create_custom_metrics', sa.Boolean(), default=False),
        
        # Messaging permissions
        sa.Column('message_permissions', postgresql.JSONB(), default=list),
        sa.Column('max_bulk_recipients', sa.Integer(), nullable=True),
        sa.Column('max_messages_per_hour', sa.Integer(), nullable=True),
        sa.Column('can_use_automation', sa.Boolean(), default=False),
        sa.Column('can_access_all_conversations', sa.Boolean(), default=False),
        
        # Time restrictions
        sa.Column('access_start_time', sa.String(5), nullable=True),
        sa.Column('access_end_time', sa.String(5), nullable=True),
        sa.Column('access_days_of_week', postgresql.JSONB(), default=list),
        sa.Column('access_timezone', sa.String(50), default='UTC'),
        
        # Conditional access
        sa.Column('requires_mfa', sa.Boolean(), default=False),
        sa.Column('requires_vpn', sa.Boolean(), default=False),
        sa.Column('allowed_ip_ranges', postgresql.JSONB(), nullable=True),
        sa.Column('allowed_countries', postgresql.JSONB(), nullable=True),
        
        # Approval workflow
        sa.Column('requires_approval', sa.Boolean(), default=False),
        sa.Column('approval_chain', postgresql.JSONB(), default=list),
        sa.Column('auto_expire_hours', sa.Integer(), nullable=True),
        
        # Usage tracking
        sa.Column('usage_quota_daily', sa.Integer(), nullable=True),
        sa.Column('usage_quota_monthly', sa.Integer(), nullable=True),
        sa.Column('cost_per_use', sa.Float(), nullable=True),
        
        # Metadata
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_system', sa.Boolean(), default=False),
        sa.Column('metadata', postgresql.JSONB(), default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        
        # Constraints
        sa.CheckConstraint(
            "(role_id IS NOT NULL) OR (user_id IS NOT NULL)",
            name="check_permission_target"
        )
    )
    
    # Create indexes
    op.create_index('idx_feature_permissions_active', 'feature_permissions', ['is_active'])
    op.create_index('idx_feature_permissions_feature_type', 'feature_permissions', ['feature_type'])
    op.create_index('idx_feature_permissions_role_user', 'feature_permissions', ['role_id', 'user_id'])
    
    # Create feature_usage_logs table
    op.create_table(
        'feature_usage_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        
        # What was accessed
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('feature_permissions.id'), nullable=False),
        sa.Column('feature_type', postgresql.ENUM('reports', 'exports', 'analytics', 'messaging',
                  'financial', 'models', 'chat', 'sync', 'webhooks', 'api', 'admin', 'settings',
                  'audit', 'ml', 'integrations', name='featuretype'), nullable=False, index=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('resource_type', sa.String(100), nullable=True),
        
        # Who accessed it
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('roles.id'), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        
        # Access details
        sa.Column('was_allowed', sa.Boolean(), nullable=False),
        sa.Column('denial_reason', sa.String(255), nullable=True),
        
        # Usage details
        sa.Column('data_accessed', postgresql.JSONB(), nullable=True),
        sa.Column('rows_affected', sa.Integer(), nullable=True),
        sa.Column('export_format', sa.String(20), nullable=True),
        sa.Column('export_size_mb', sa.Float(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        
        # Cost tracking
        sa.Column('usage_cost', sa.Float(), nullable=True),
        sa.Column('quota_used', sa.Integer(), default=1),
        
        # Metadata
        sa.Column('request_id', sa.String(255), nullable=True),
        sa.Column('session_id', sa.String(255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), default=dict)
    )
    
    # Create indexes
    op.create_index('idx_feature_usage_logs_user_timestamp', 'feature_usage_logs', 
                    ['user_id', 'timestamp'])
    op.create_index('idx_feature_usage_logs_permission_timestamp', 'feature_usage_logs', 
                    ['permission_id', 'timestamp'])
    
    # Create report_templates table
    op.create_table(
        'report_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Template information
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', postgresql.ENUM('earnings', 'performance', 'user_activity',
                  'model_metrics', 'chat_analytics', 'revenue_breakdown', 'commission_report',
                  'tax_report', 'compliance_report', 'custom', name='reporttype'), 
                  nullable=False, index=True),
        
        # Template configuration
        sa.Column('query_template', sa.Text(), nullable=False),
        sa.Column('parameters', postgresql.JSONB(), default=dict),
        sa.Column('default_filters', postgresql.JSONB(), default=dict),
        sa.Column('available_columns', postgresql.JSONB(), default=list),
        sa.Column('default_columns', postgresql.JSONB(), default=list),
        
        # Visualization settings
        sa.Column('chart_types', postgresql.JSONB(), default=list),
        sa.Column('default_chart_type', sa.String(50), nullable=True),
        sa.Column('visualization_config', postgresql.JSONB(), default=dict),
        
        # Access control
        sa.Column('required_permission_level', postgresql.ENUM('public', 'internal', 'confidential',
                  'restricted', 'top_secret', name='datasensitivity'), default='internal'),
        sa.Column('required_roles', postgresql.JSONB(), default=list),
        sa.Column('excluded_roles', postgresql.JSONB(), default=list),
        sa.Column('requires_approval', sa.Boolean(), default=False),
        
        # Data restrictions
        sa.Column('max_date_range_days', sa.Integer(), nullable=True),
        sa.Column('data_retention_days', sa.Integer(), nullable=True),
        sa.Column('cache_duration_minutes', sa.Integer(), default=60),
        
        # Export settings
        sa.Column('allow_export', sa.Boolean(), default=True),
        sa.Column('export_formats', postgresql.JSONB(), default=['csv', 'excel', 'pdf']),
        sa.Column('include_pii', sa.Boolean(), default=False),
        sa.Column('include_financial', sa.Boolean(), default=False),
        
        # Scheduling
        sa.Column('allow_scheduling', sa.Boolean(), default=True),
        sa.Column('min_schedule_interval_hours', sa.Integer(), default=24),
        
        # Cost
        sa.Column('execution_cost', sa.Float(), default=1.0),
        
        # Metadata
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_system', sa.Boolean(), default=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agencies.id'), nullable=True),
        sa.Column('tags', postgresql.JSONB(), default=list),
        sa.Column('metadata', postgresql.JSONB(), default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())
    )
    
    # Create report_schedules table
    op.create_table(
        'report_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Schedule information
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('report_templates.id'), nullable=False),
        
        # Schedule configuration
        sa.Column('cron_expression', sa.String(100), nullable=True),
        sa.Column('interval_hours', sa.Integer(), nullable=True),
        sa.Column('timezone', sa.String(50), default='UTC'),
        
        # Report parameters
        sa.Column('parameters', postgresql.JSONB(), default=dict),
        sa.Column('filters', postgresql.JSONB(), default=dict),
        
        # Distribution
        sa.Column('recipients', postgresql.JSONB(), default=list),
        sa.Column('export_format', postgresql.ENUM('csv', 'excel', 'pdf', 'json', 'xml',
                  'html', 'parquet', name='exportformat'), default='pdf'),
        sa.Column('delivery_method', sa.String(50), default='email'),
        sa.Column('delivery_config', postgresql.JSONB(), default=dict),
        
        # Access control
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('approved_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approval_date', sa.DateTime(timezone=True), nullable=True),
        
        # Status
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_count', sa.Integer(), default=0),
        
        # Metadata
        sa.Column('metadata', postgresql.JSONB(), default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Create report_executions table
    op.create_table(
        'report_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        
        # Execution information
        sa.Column('template_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('report_templates.id'), nullable=False),
        sa.Column('schedule_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('report_schedules.id'), nullable=True),
        sa.Column('executed_by_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('users.id'), nullable=False),
        
        # Execution details
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Parameters used
        sa.Column('parameters', postgresql.JSONB(), default=dict),
        sa.Column('filters', postgresql.JSONB(), default=dict),
        
        # Results
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('file_size_mb', sa.Float(), nullable=True),
        sa.Column('export_format', sa.String(20), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        
        # Performance
        sa.Column('query_time_ms', sa.Integer(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('memory_used_mb', sa.Float(), nullable=True),
        
        # Cost
        sa.Column('execution_cost', sa.Float(), nullable=True),
        
        # Metadata
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), default=dict)
    )
    
    # Insert default feature permissions for roles
    op.execute("""
        INSERT INTO feature_permissions (
            id, name, description, feature_type, role_id,
            allowed_actions, can_access_financial_data, can_access_pii_data,
            analytics_scope, can_view_revenue_data, is_system, created_at, updated_at
        )
        SELECT 
            gen_random_uuid(),
            'Admin - ' || r.name || ' Permissions',
            'Full access permissions for ' || r.name || ' role',
            'admin',
            r.id,
            '["*"]'::jsonb,
            true,
            true,
            'global',
            true,
            true,
            now(),
            now()
        FROM roles r
        WHERE r.name = 'admin'
    """)
    
    # Insert manager permissions
    op.execute("""
        INSERT INTO feature_permissions (
            id, name, description, feature_type, role_id,
            allowed_report_types, max_report_range_days,
            can_access_financial_data, analytics_scope,
            can_view_revenue_data, is_system, created_at, updated_at
        )
        SELECT 
            gen_random_uuid(),
            'Manager - Reports & Analytics',
            'Report and analytics permissions for managers',
            'reports',
            r.id,
            '["earnings", "performance", "user_activity", "model_metrics", "revenue_breakdown"]'::jsonb,
            365,
            true,
            'agency',
            true,
            true,
            now(),
            now()
        FROM roles r
        WHERE r.name = 'manager'
    """)
    
    # Insert default report templates
    op.execute("""
        INSERT INTO report_templates (
            id, name, description, report_type, query_template,
            available_columns, default_columns, is_system,
            created_at, updated_at
        )
        VALUES 
        (gen_random_uuid(), 'Daily Earnings Report', 'Daily earnings breakdown by model',
         'earnings', 'SELECT date, model_id, SUM(amount) as earnings FROM transactions GROUP BY date, model_id',
         '["date", "model_id", "earnings", "transactions", "avg_transaction"]'::jsonb,
         '["date", "model_id", "earnings"]'::jsonb,
         true, now(), now()),
         
        (gen_random_uuid(), 'Model Performance Report', 'Model performance metrics',
         'performance', 'SELECT model_id, messages_sent, response_rate, conversion_rate FROM model_metrics',
         '["model_id", "messages_sent", "response_rate", "conversion_rate", "active_fans"]'::jsonb,
         '["model_id", "messages_sent", "conversion_rate"]'::jsonb,
         true, now(), now()),
         
        (gen_random_uuid(), 'User Activity Report', 'User activity and engagement metrics',
         'user_activity', 'SELECT user_id, login_count, active_hours, messages_sent FROM user_activity',
         '["user_id", "login_count", "active_hours", "messages_sent", "last_active"]'::jsonb,
         '["user_id", "login_count", "messages_sent"]'::jsonb,
         true, now(), now())
    """)


def downgrade() -> None:
    # Drop tables
    op.drop_table('report_executions')
    op.drop_table('report_schedules')
    op.drop_table('report_templates')
    op.drop_table('feature_usage_logs')
    op.drop_table('feature_permissions')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS datasensitivity')
    op.execute('DROP TYPE IF EXISTS messagepermission')
    op.execute('DROP TYPE IF EXISTS analyticsscope')
    op.execute('DROP TYPE IF EXISTS exportformat')
    op.execute('DROP TYPE IF EXISTS reporttype')
    op.execute('DROP TYPE IF EXISTS featuretype')