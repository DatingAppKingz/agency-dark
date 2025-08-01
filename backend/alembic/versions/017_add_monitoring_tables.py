"""add monitoring tables

Revision ID: 017_add_monitoring_tables
Revises: 010_add_ml_analytics_tables
Create Date: 2024-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '017_add_monitoring_tables'
down_revision = '016_add_ml_analytics_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create metrics table
    op.create_table(
        'metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_type', sa.String(), nullable=False),
        sa.Column('metric_name', sa.String(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('entity_type', sa.String(), nullable=True),
        sa.Column('entity_id', sa.String(), nullable=True),
        sa.Column('hostname', sa.String(), nullable=True),
        sa.Column('service_name', sa.String(), nullable=True),
        sa.Column('environment', sa.String(), nullable=True, server_default='production'),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for metrics
    op.create_index('idx_metric_type_timestamp', 'metrics', ['metric_type', 'timestamp'])
    op.create_index('idx_metric_name_timestamp', 'metrics', ['metric_name', 'timestamp'])
    op.create_index('idx_service_timestamp', 'metrics', ['service_name', 'timestamp'])
    op.create_index('idx_metrics_hostname', 'metrics', ['hostname'])
    
    # Create service_health table
    op.create_table(
        'service_health',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='unknown'),
        sa.Column('check_name', sa.String(), nullable=False),
        sa.Column('response_time_ms', sa.Float(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('dependencies', sa.JSON(), nullable=True),
        sa.Column('checked_at', sa.DateTime(), nullable=False),
        sa.Column('last_healthy_at', sa.DateTime(), nullable=True),
        sa.Column('previous_status', sa.String(), nullable=True),
        sa.Column('status_changed_at', sa.DateTime(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=True, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_name', 'check_name', name='uq_service_check')
    )
    
    op.create_index('idx_service_status', 'service_health', ['service_name', 'status'])
    
    # Create alert_rules table
    op.create_table(
        'alert_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metric_type', sa.String(), nullable=False),
        sa.Column('condition', sa.String(), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('query', sa.Text(), nullable=True),
        sa.Column('aggregation', sa.String(), nullable=True),
        sa.Column('time_window_minutes', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('severity', sa.String(), nullable=False, server_default='warning'),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('notification_channels', sa.JSON(), nullable=True),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=True, server_default='30'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create alerts table
    op.create_table(
        'alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='active'),
        sa.Column('metric_value', sa.Float(), nullable=True),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('metric_details', sa.JSON(), nullable=True),
        sa.Column('triggered_at', sa.DateTime(), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_alert_status', 'alerts', ['status'])
    op.create_index('idx_alert_triggered', 'alerts', ['triggered_at'])
    
    # Create alert_notifications table
    op.create_table(
        'alert_notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('channel', sa.String(), nullable=False),
        sa.Column('recipient', sa.String(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create performance_profiles table
    op.create_table(
        'performance_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('endpoint', sa.String(), nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('total_duration_ms', sa.Float(), nullable=False),
        sa.Column('db_duration_ms', sa.Float(), nullable=True),
        sa.Column('cache_duration_ms', sa.Float(), nullable=True),
        sa.Column('external_api_duration_ms', sa.Float(), nullable=True),
        sa.Column('processing_duration_ms', sa.Float(), nullable=True),
        sa.Column('memory_usage_mb', sa.Float(), nullable=True),
        sa.Column('cpu_usage_percent', sa.Float(), nullable=True),
        sa.Column('query_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('slow_queries', sa.JSON(), nullable=True),
        sa.Column('cache_hits', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('cache_misses', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id')
    )
    
    op.create_index('idx_performance_endpoint_timestamp', 'performance_profiles', ['endpoint', 'timestamp'])
    op.create_index('idx_performance_request_id', 'performance_profiles', ['request_id'])
    
    # Create monitoring_dashboards table
    op.create_table(
        'monitoring_dashboards',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('layout', sa.JSON(), nullable=False),
        sa.Column('widgets', sa.JSON(), nullable=False),
        sa.Column('refresh_interval_seconds', sa.Integer(), nullable=True, server_default='30'),
        sa.Column('is_public', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('shared_with', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create default alert rules
    op.execute("""
        INSERT INTO alert_rules (id, name, description, metric_type, condition, threshold, severity, is_active)
        VALUES 
        (gen_random_uuid(), 'High CPU Usage', 'Alert when CPU usage exceeds 80%', 'system_cpu', 'greater_than', 80, 'warning', true),
        (gen_random_uuid(), 'Critical CPU Usage', 'Alert when CPU usage exceeds 95%', 'system_cpu', 'greater_than', 95, 'critical', true),
        (gen_random_uuid(), 'High Memory Usage', 'Alert when memory usage exceeds 85%', 'system_memory', 'greater_than', 85, 'warning', true),
        (gen_random_uuid(), 'Low Disk Space', 'Alert when disk usage exceeds 90%', 'system_disk', 'greater_than', 90, 'critical', true),
        (gen_random_uuid(), 'High API Error Rate', 'Alert when API error rate exceeds 5%', 'api_error_rate', 'greater_than', 5, 'warning', true),
        (gen_random_uuid(), 'Database Connection Pool Full', 'Alert when active DB connections exceed 80', 'database_connections', 'greater_than', 80, 'warning', true),
        (gen_random_uuid(), 'Low Cache Hit Rate', 'Alert when cache hit rate falls below 70%', 'cache_hit_rate', 'less_than', 70, 'warning', true)
    """)


def downgrade():
    op.drop_table('monitoring_dashboards')
    op.drop_table('performance_profiles')
    op.drop_table('alert_notifications')
    op.drop_table('alerts')
    op.drop_table('alert_rules')
    op.drop_table('service_health')
    op.drop_table('metrics')