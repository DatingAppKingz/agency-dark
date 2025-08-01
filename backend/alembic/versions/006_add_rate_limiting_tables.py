"""Add rate limiting tables

Revision ID: 006
Revises: 005
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add rate limiting tables."""
    
    # Create rate_limit_configs table
    op.create_table('rate_limit_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tier', postgresql.ENUM('free', 'basic', 'professional', 'enterprise', 'custom', name='ratelimittier'), nullable=False),
        sa.Column('endpoint_pattern', sa.String(length=255), nullable=False),
        sa.Column('limit_type', postgresql.ENUM('api_calls', 'data_export', 'file_upload', 'webhook_calls', 'websocket_messages', name='ratelimittype'), nullable=False),
        sa.Column('requests_per_minute', sa.Integer(), nullable=True),
        sa.Column('requests_per_hour', sa.Integer(), nullable=True),
        sa.Column('requests_per_day', sa.Integer(), nullable=True),
        sa.Column('burst_size', sa.Integer(), nullable=True),
        sa.Column('burst_window_seconds', sa.Integer(), nullable=True),
        sa.Column('max_concurrent_requests', sa.Integer(), nullable=True),
        sa.Column('max_request_size_mb', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('bypass_for_internal', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for rate_limit_configs
    op.create_index('idx_rate_limit_config_tier', 'rate_limit_configs', ['tier'], unique=False)
    op.create_index('idx_rate_limit_config_endpoint', 'rate_limit_configs', ['endpoint_pattern'], unique=False)
    op.create_index('idx_rate_limit_config_active', 'rate_limit_configs', ['is_active'], unique=False)
    
    # Create user_rate_limits table
    op.create_table('user_rate_limits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tier_override', postgresql.ENUM('free', 'basic', 'professional', 'enterprise', 'custom', name='ratelimittier'), nullable=True),
        sa.Column('custom_limits', sa.JSON(), nullable=True),
        sa.Column('limit_multiplier', sa.Float(), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('approved_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['approved_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for user_rate_limits
    op.create_index('idx_user_rate_limit_user', 'user_rate_limits', ['user_id'], unique=False)
    op.create_index('idx_user_rate_limit_validity', 'user_rate_limits', ['valid_from', 'valid_until'], unique=False)
    
    # Create ip_rate_limits table
    op.create_table('ip_rate_limits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('ip_range', sa.String(length=50), nullable=True),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('requests_per_minute', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for ip_rate_limits
    op.create_index('idx_ip_rate_limit_address', 'ip_rate_limits', ['ip_address'], unique=False)
    op.create_index('idx_ip_rate_limit_action', 'ip_rate_limits', ['action'], unique=False)
    op.create_index('idx_ip_rate_limit_expires', 'ip_rate_limits', ['expires_at'], unique=False)
    
    # Create rate_limit_violations table
    op.create_table('rate_limit_violations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('endpoint', sa.String(length=500), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('limit_type', sa.String(length=50), nullable=False),
        sa.Column('limit_value', sa.Integer(), nullable=False),
        sa.Column('actual_value', sa.Integer(), nullable=False),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('blocked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('request_headers', sa.JSON(), nullable=True),
        sa.Column('violated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for rate_limit_violations
    op.create_index('idx_rate_limit_violation_user', 'rate_limit_violations', ['user_id'], unique=False)
    op.create_index('idx_rate_limit_violation_ip', 'rate_limit_violations', ['ip_address'], unique=False)
    op.create_index('idx_rate_limit_violation_time', 'rate_limit_violations', ['violated_at'], unique=False)
    op.create_index('idx_rate_limit_violation_endpoint', 'rate_limit_violations', ['endpoint'], unique=False)
    
    # Create rate_limit_whitelist table
    op.create_table('rate_limit_whitelist',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('ip_range', sa.String(length=50), nullable=True),
        sa.Column('endpoint_pattern', sa.String(length=255), nullable=True),
        sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('approved_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.ForeignKeyConstraint(['approved_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for rate_limit_whitelist
    op.create_index('idx_rate_limit_whitelist_user', 'rate_limit_whitelist', ['user_id'], unique=False)
    op.create_index('idx_rate_limit_whitelist_api_key', 'rate_limit_whitelist', ['api_key_id'], unique=False)
    op.create_index('idx_rate_limit_whitelist_ip', 'rate_limit_whitelist', ['ip_address'], unique=False)
    op.create_index('idx_rate_limit_whitelist_validity', 'rate_limit_whitelist', ['valid_from', 'valid_until'], unique=False)
    
    # Set default values
    op.execute("UPDATE rate_limit_configs SET burst_size = 10 WHERE burst_size IS NULL")
    op.execute("UPDATE rate_limit_configs SET burst_window_seconds = 10 WHERE burst_window_seconds IS NULL")
    op.execute("UPDATE rate_limit_configs SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE rate_limit_configs SET bypass_for_internal = false WHERE bypass_for_internal IS NULL")
    op.execute("UPDATE user_rate_limits SET custom_limits = '{}' WHERE custom_limits IS NULL")
    op.execute("UPDATE user_rate_limits SET limit_multiplier = 1.0 WHERE limit_multiplier IS NULL")
    op.execute("UPDATE rate_limit_violations SET response_code = 429 WHERE response_code IS NULL")
    
    # Insert default rate limit configurations
    op.execute("""
        INSERT INTO rate_limit_configs (id, tier, endpoint_pattern, limit_type, 
            requests_per_minute, requests_per_hour, requests_per_day, 
            burst_size, is_active)
        VALUES
        -- Free tier limits
        (gen_random_uuid(), 'free', '/api/v1/*', 'api_calls', 20, 500, 5000, 5, true),
        (gen_random_uuid(), 'free', '/api/v1/analytics/*', 'api_calls', 10, 200, 1000, 3, true),
        (gen_random_uuid(), 'free', '/api/v1/export/*', 'data_export', 1, 10, 50, 1, true),
        
        -- Basic tier limits
        (gen_random_uuid(), 'basic', '/api/v1/*', 'api_calls', 60, 2000, 20000, 10, true),
        (gen_random_uuid(), 'basic', '/api/v1/analytics/*', 'api_calls', 30, 1000, 5000, 5, true),
        (gen_random_uuid(), 'basic', '/api/v1/export/*', 'data_export', 5, 50, 200, 2, true),
        
        -- Professional tier limits
        (gen_random_uuid(), 'professional', '/api/v1/*', 'api_calls', 200, 8000, 80000, 20, true),
        (gen_random_uuid(), 'professional', '/api/v1/analytics/*', 'api_calls', 100, 4000, 20000, 10, true),
        (gen_random_uuid(), 'professional', '/api/v1/export/*', 'data_export', 20, 200, 1000, 5, true),
        
        -- Enterprise tier limits
        (gen_random_uuid(), 'enterprise', '/api/v1/*', 'api_calls', 1000, 40000, 400000, 50, true),
        (gen_random_uuid(), 'enterprise', '/api/v1/analytics/*', 'api_calls', 500, 20000, 100000, 25, true),
        (gen_random_uuid(), 'enterprise', '/api/v1/export/*', 'data_export', 100, 1000, 5000, 20, true)
    """)


def downgrade() -> None:
    """Remove rate limiting tables."""
    
    # Drop indexes
    op.drop_index('idx_rate_limit_whitelist_validity', table_name='rate_limit_whitelist')
    op.drop_index('idx_rate_limit_whitelist_ip', table_name='rate_limit_whitelist')
    op.drop_index('idx_rate_limit_whitelist_api_key', table_name='rate_limit_whitelist')
    op.drop_index('idx_rate_limit_whitelist_user', table_name='rate_limit_whitelist')
    op.drop_index('idx_rate_limit_violation_endpoint', table_name='rate_limit_violations')
    op.drop_index('idx_rate_limit_violation_time', table_name='rate_limit_violations')
    op.drop_index('idx_rate_limit_violation_ip', table_name='rate_limit_violations')
    op.drop_index('idx_rate_limit_violation_user', table_name='rate_limit_violations')
    op.drop_index('idx_ip_rate_limit_expires', table_name='ip_rate_limits')
    op.drop_index('idx_ip_rate_limit_action', table_name='ip_rate_limits')
    op.drop_index('idx_ip_rate_limit_address', table_name='ip_rate_limits')
    op.drop_index('idx_user_rate_limit_validity', table_name='user_rate_limits')
    op.drop_index('idx_user_rate_limit_user', table_name='user_rate_limits')
    op.drop_index('idx_rate_limit_config_active', table_name='rate_limit_configs')
    op.drop_index('idx_rate_limit_config_endpoint', table_name='rate_limit_configs')
    op.drop_index('idx_rate_limit_config_tier', table_name='rate_limit_configs')
    
    # Drop tables
    op.drop_table('rate_limit_whitelist')
    op.drop_table('rate_limit_violations')
    op.drop_table('ip_rate_limits')
    op.drop_table('user_rate_limits')
    op.drop_table('rate_limit_configs')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS ratelimittype')
    op.execute('DROP TYPE IF EXISTS ratelimittier')