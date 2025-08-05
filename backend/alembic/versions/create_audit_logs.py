"""Create audit log tables

Revision ID: create_audit_logs
Revises: create_platform_api_keys
Create Date: 2025-01-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = 'create_audit_logs'
down_revision = 'create_platform_api_keys'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create audit action enum
    op.execute("""
        CREATE TYPE auditaction AS ENUM (
            'login', 'logout', 'login_failed', 'password_changed', 'password_reset',
            'mfa_enabled', 'mfa_disabled',
            'user_created', 'user_updated', 'user_deleted', 'user_activated',
            'user_deactivated', 'user_role_changed', 'user_permissions_changed',
            'model_created', 'model_updated', 'model_deleted', 'model_assigned',
            'model_unassigned',
            'transaction_created', 'transaction_updated', 'transaction_deleted',
            'payout_initiated', 'payout_approved', 'payout_rejected', 'commission_calculated',
            'message_sent', 'message_deleted', 'conversation_created', 'conversation_archived',
            'bulk_message_sent',
            'api_key_created', 'api_key_rotated', 'api_key_revoked', 'api_key_used',
            'data_exported', 'data_imported', 'report_generated', 'analytics_viewed',
            'settings_changed', 'integration_connected', 'integration_disconnected',
            'webhook_configured', 'sync_initiated',
            'permission_granted', 'permission_revoked', 'suspicious_activity',
            'rate_limit_exceeded', 'ip_blocked',
            'data_retention_applied', 'user_data_requested', 'user_data_deleted',
            'audit_exported'
        )
    """)
    
    # Create audit severity enum
    op.execute("""
        CREATE TYPE auditseverity AS ENUM ('info', 'warning', 'error', 'critical')
    """)
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        
        # Who
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agencies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('impersonator_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('platform_api_keys.id', ondelete='SET NULL'), nullable=True),
        
        # What
        sa.Column('action', postgresql.ENUM('login', 'logout', 'login_failed', 'password_changed', 'password_reset',
            'mfa_enabled', 'mfa_disabled', 'user_created', 'user_updated', 'user_deleted', 'user_activated',
            'user_deactivated', 'user_role_changed', 'user_permissions_changed', 'model_created', 'model_updated',
            'model_deleted', 'model_assigned', 'model_unassigned', 'transaction_created', 'transaction_updated',
            'transaction_deleted', 'payout_initiated', 'payout_approved', 'payout_rejected', 'commission_calculated',
            'message_sent', 'message_deleted', 'conversation_created', 'conversation_archived', 'bulk_message_sent',
            'api_key_created', 'api_key_rotated', 'api_key_revoked', 'api_key_used', 'data_exported', 'data_imported',
            'report_generated', 'analytics_viewed', 'settings_changed', 'integration_connected', 'integration_disconnected',
            'webhook_configured', 'sync_initiated', 'permission_granted', 'permission_revoked', 'suspicious_activity',
            'rate_limit_exceeded', 'ip_blocked', 'data_retention_applied', 'user_data_requested', 'user_data_deleted',
            'audit_exported', name='auditaction'), nullable=False, index=True),
        sa.Column('resource_type', sa.String(100), nullable=True, index=True),
        sa.Column('resource_id', sa.String(255), nullable=True),
        sa.Column('resource_name', sa.String(255), nullable=True),
        
        # Details
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('changes', postgresql.JSONB(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        
        # Where
        sa.Column('ip_address', sa.String(45), nullable=True, index=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        
        # Context
        sa.Column('session_id', sa.String(255), nullable=True),
        sa.Column('request_id', sa.String(255), nullable=True),
        sa.Column('correlation_id', sa.String(255), nullable=True),
        
        # Security
        sa.Column('severity', postgresql.ENUM('info', 'warning', 'error', 'critical', name='auditseverity'), 
                  default='info', nullable=False),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('flagged', sa.Boolean(), default=False, nullable=False),
        
        # Compliance
        sa.Column('retention_days', sa.Integer(), nullable=True),
        sa.Column('compliance_tags', postgresql.JSONB(), nullable=True),
        sa.Column('exported', sa.Boolean(), default=False, nullable=False),
        sa.Column('export_date', sa.DateTime(timezone=True), nullable=True),
        
        # Performance
        sa.Column('duration_ms', sa.Integer(), nullable=True)
    )
    
    # Create indexes
    op.create_index('idx_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('idx_audit_logs_user_timestamp', 'audit_logs', ['user_id', 'timestamp'])
    op.create_index('idx_audit_logs_agency_timestamp', 'audit_logs', ['agency_id', 'timestamp'])
    op.create_index('idx_audit_logs_action_timestamp', 'audit_logs', ['action', 'timestamp'])
    op.create_index('idx_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_logs_ip', 'audit_logs', ['ip_address'])
    
    # Create audit_log_retention_policies table
    op.create_table(
        'audit_log_retention_policies',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('action_pattern', sa.String(255), nullable=True),
        sa.Column('resource_type_pattern', sa.String(255), nullable=True),
        sa.Column('severity', postgresql.ENUM('info', 'warning', 'error', 'critical', name='auditseverity'), nullable=True),
        sa.Column('retention_days', sa.Integer(), nullable=False),
        sa.Column('delete_after_export', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('priority', sa.Integer(), default=0, nullable=False),
        sa.Column('compliance_requirement', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'))
    )
    
    # Create audit_log_exports table
    op.create_table(
        'audit_log_exports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('exported_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('exported_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('filters', postgresql.JSONB(), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=False),
        sa.Column('storage_location', sa.String(500), nullable=True),
        sa.Column('file_hash', sa.String(255), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('purpose', sa.String(255), nullable=True),
        sa.Column('authorized_by', sa.String(255), nullable=True),
        sa.Column('compliance_tags', postgresql.JSONB(), nullable=True),
        sa.Column('encrypted', sa.Boolean(), default=True, nullable=False),
        sa.Column('encryption_key_id', sa.String(255), nullable=True)
    )
    
    # Create audit_log_alerts table
    op.create_table(
        'audit_log_alerts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('action_pattern', sa.String(255), nullable=True),
        sa.Column('threshold_count', sa.Integer(), nullable=True),
        sa.Column('threshold_minutes', sa.Integer(), nullable=True),
        sa.Column('severity_threshold', postgresql.ENUM('info', 'warning', 'error', 'critical', name='auditseverity'), nullable=True),
        sa.Column('risk_score_threshold', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_triggered', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trigger_count', sa.Integer(), default=0, nullable=False),
        sa.Column('notify_emails', postgresql.JSONB(), nullable=True),
        sa.Column('notify_webhook', sa.String(500), nullable=True),
        sa.Column('notify_in_app', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'))
    )
    
    # Insert default retention policies
    op.execute("""
        INSERT INTO audit_log_retention_policies (id, name, description, action_pattern, retention_days, priority, compliance_requirement)
        VALUES 
        (gen_random_uuid(), 'Financial Actions', 'Retain financial actions for 7 years', 'transaction_.*|payout_.*|commission_.*', 2555, 100, 'SOX'),
        (gen_random_uuid(), 'User Data Actions', 'Retain user data actions for 3 years', 'user_.*|data_exported|user_data_.*', 1095, 90, 'GDPR'),
        (gen_random_uuid(), 'Security Events', 'Retain security events for 1 year', 'login_failed|suspicious_activity|rate_limit_exceeded|ip_blocked', 365, 80, 'Security'),
        (gen_random_uuid(), 'General Actions', 'Retain general actions for 90 days', '.*', 90, 0, 'General')
    """)


def downgrade() -> None:
    # Drop tables
    op.drop_table('audit_log_alerts')
    op.drop_table('audit_log_exports')
    op.drop_table('audit_log_retention_policies')
    
    # Drop indexes
    op.drop_index('idx_audit_logs_ip', 'audit_logs')
    op.drop_index('idx_audit_logs_resource', 'audit_logs')
    op.drop_index('idx_audit_logs_action_timestamp', 'audit_logs')
    op.drop_index('idx_audit_logs_agency_timestamp', 'audit_logs')
    op.drop_index('idx_audit_logs_user_timestamp', 'audit_logs')
    op.drop_index('idx_audit_logs_timestamp', 'audit_logs')
    
    op.drop_table('audit_logs')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS auditseverity')
    op.execute('DROP TYPE IF EXISTS auditaction')