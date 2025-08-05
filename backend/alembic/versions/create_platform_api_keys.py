"""Create platform API keys tables

Revision ID: create_platform_api_keys
Revises: latest
Create Date: 2025-01-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = 'create_platform_api_keys'
down_revision = None  # Set this to your latest revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create platform_api_keys table
    op.create_table(
        'platform_api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agencies.id', ondelete='CASCADE'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('key_prefix', sa.String(8), nullable=False, index=True),
        sa.Column('key_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('scopes', sa.JSON(), nullable=False, default=list),
        sa.Column('role_restrictions', sa.JSON(), nullable=True),
        sa.Column('allowed_ips', sa.JSON(), nullable=True),
        sa.Column('allowed_origins', sa.JSON(), nullable=True),
        sa.Column('allowed_user_agents', sa.JSON(), nullable=True),
        sa.Column('rate_limit_per_minute', sa.Integer(), default=60),
        sa.Column('rate_limit_per_hour', sa.Integer(), default=1000),
        sa.Column('rate_limit_per_day', sa.Integer(), default=10000),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_ip', sa.String(45), nullable=True),
        sa.Column('usage_count', sa.Integer(), default=0, nullable=False),
        sa.Column('monthly_usage', sa.JSON(), default=dict),
        sa.Column('error_count', sa.Integer(), default=0, nullable=False),
        sa.Column('metadata', sa.JSON(), default=dict),
        sa.Column('webhook_url', sa.String(500), nullable=True),
        sa.Column('webhook_secret', sa.String(255), nullable=True),
        sa.Column('allowed_models', sa.JSON(), nullable=True),
        sa.Column('allowed_conversations', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('revoke_reason', sa.Text(), nullable=True),
        sa.Column('rotated_from_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('platform_api_keys.id'), nullable=True),
        sa.Column('rotation_scheduled_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Create indexes
    op.create_index('idx_platform_api_keys_prefix', 'platform_api_keys', ['key_prefix'])
    op.create_index('idx_platform_api_keys_user_agency', 'platform_api_keys', ['user_id', 'agency_id'])
    op.create_index('idx_platform_api_keys_expires', 'platform_api_keys', ['expires_at'])
    
    # Create platform_api_key_usage_logs table
    op.create_table(
        'platform_api_key_usage_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('platform_api_keys.id', ondelete='CASCADE'), nullable=False),
        sa.Column('endpoint', sa.String(255), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('origin', sa.String(255), nullable=True),
        sa.Column('request_size', sa.Integer(), nullable=True),
        sa.Column('response_size', sa.Integer(), nullable=True),
        sa.Column('scope_used', sa.String(100), nullable=True),
        sa.Column('resource_accessed', sa.String(255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('rate_limit_remaining', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )
    
    # Create indexes for usage logs
    op.create_index('idx_platform_key_usage_key_time', 'platform_api_key_usage_logs', ['api_key_id', 'timestamp'])
    op.create_index('idx_platform_key_usage_time', 'platform_api_key_usage_logs', ['timestamp'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_platform_key_usage_time', 'platform_api_key_usage_logs')
    op.drop_index('idx_platform_key_usage_key_time', 'platform_api_key_usage_logs')
    op.drop_index('idx_platform_api_keys_expires', 'platform_api_keys')
    op.drop_index('idx_platform_api_keys_user_agency', 'platform_api_keys')
    op.drop_index('idx_platform_api_keys_prefix', 'platform_api_keys')
    
    # Drop tables
    op.drop_table('platform_api_key_usage_logs')
    op.drop_table('platform_api_keys')