"""Create rate limit tables

Revision ID: create_rate_limits
Revises: create_audit_logs
Create Date: 2025-01-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers
revision = 'create_rate_limits'
down_revision = 'create_audit_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create rate limit type enum
    op.execute("""
        CREATE TYPE ratelimittype AS ENUM (
            'user', 'api_key', 'ip', 'endpoint', 'global', 'geographic', 'tier', 'custom'
        )
    """)
    
    # Create rate limit algorithm enum
    op.execute("""
        CREATE TYPE ratelimitalgorithm AS ENUM (
            'token_bucket', 'sliding_window', 'fixed_window', 'leaky_bucket', 'adaptive'
        )
    """)
    
    # Create rate limit tier enum
    op.execute("""
        CREATE TYPE ratelimittier AS ENUM (
            'free', 'basic', 'pro', 'enterprise', 'unlimited'
        )
    """)
    
    # Create rate_limit_configs table
    op.create_table(
        'rate_limit_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('limit_type', postgresql.ENUM('user', 'api_key', 'ip', 'endpoint', 'global', 
                  'geographic', 'tier', 'custom', name='ratelimittype'), nullable=False, index=True),
        sa.Column('identifier', sa.String(255), nullable=True),
        
        # Request-based limits
        sa.Column('requests_per_minute', sa.Integer(), nullable=True),
        sa.Column('requests_per_hour', sa.Integer(), nullable=True),
        sa.Column('requests_per_day', sa.Integer(), nullable=True),
        sa.Column('burst_size', sa.Integer(), nullable=True),
        
        # Cost-based limits
        sa.Column('cost_per_minute', sa.Float(), nullable=True),
        sa.Column('cost_per_hour', sa.Float(), nullable=True),
        sa.Column('cost_per_day', sa.Float(), nullable=True),
        
        # Algorithm settings
        sa.Column('algorithm', postgresql.ENUM('token_bucket', 'sliding_window', 'fixed_window', 
                  'leaky_bucket', 'adaptive', name='ratelimitalgorithm'), default='token_bucket'),
        sa.Column('refill_rate', sa.Float(), nullable=True),
        sa.Column('window_size_seconds', sa.Integer(), nullable=True),
        
        # Geographic settings
        sa.Column('allowed_countries', postgresql.JSONB(), nullable=True),
        sa.Column('blocked_countries', postgresql.JSONB(), nullable=True),
        sa.Column('geographic_multiplier', postgresql.JSONB(), nullable=True),
        
        # Time-based variations
        sa.Column('time_based_limits', postgresql.JSONB(), nullable=True),
        
        # Tier settings
        sa.Column('tier', postgresql.ENUM('free', 'basic', 'pro', 'enterprise', 'unlimited', name='ratelimittier'), nullable=True),
        sa.Column('tier_multiplier', sa.Float(), default=1.0),
        
        # Endpoint-specific settings
        sa.Column('endpoint_costs', postgresql.JSONB(), nullable=True),
        sa.Column('endpoint_limits', postgresql.JSONB(), nullable=True),
        
        # Status
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('override_global', sa.Boolean(), default=False),
        sa.Column('stackable', sa.Boolean(), default=True),
        
        # Negotiated limits
        sa.Column('is_negotiated', sa.Boolean(), default=False),
        sa.Column('negotiated_by', sa.String(255), nullable=True),
        sa.Column('negotiation_notes', sa.String(1000), nullable=True),
        
        # Metadata
        sa.Column('metadata', postgresql.JSONB(), default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        
        # Relationships
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agencies.id'))
    )
    
    # Create indexes
    op.create_index('idx_rate_limit_configs_type_identifier', 'rate_limit_configs', ['limit_type', 'identifier'])
    op.create_index('idx_rate_limit_configs_active', 'rate_limit_configs', ['is_active'])
    
    # Create rate_limit_buckets table
    op.create_table(
        'rate_limit_buckets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('bucket_key', sa.String(500), nullable=False, unique=True),
        sa.Column('config_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('rate_limit_configs.id')),
        sa.Column('tokens', sa.Float(), nullable=False, default=0),
        sa.Column('last_refill', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('request_count', sa.Integer(), default=0),
        sa.Column('total_cost', sa.Float(), default=0),
        sa.Column('window_counters', postgresql.JSONB(), default=dict),
        sa.Column('burst_used', sa.Integer(), default=0),
        sa.Column('last_burst_reset', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    
    # Create indexes
    op.create_index('idx_rate_limit_buckets_identifier', 'rate_limit_buckets', ['bucket_key'])
    op.create_index('idx_rate_limit_buckets_updated', 'rate_limit_buckets', ['last_updated'])
    
    # Create rate_limit_violations table
    op.create_table(
        'rate_limit_violations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        sa.Column('identifier', sa.String(255), nullable=False),
        sa.Column('identifier_type', postgresql.ENUM('user', 'api_key', 'ip', 'endpoint', 'global', 
                  'geographic', 'tier', 'custom', name='ratelimittype'), nullable=False),
        sa.Column('endpoint', sa.String(500), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('limit_type', sa.String(50), nullable=False),
        sa.Column('limit_value', sa.Float(), nullable=False),
        sa.Column('actual_value', sa.Float(), nullable=False),
        sa.Column('response_code', sa.Integer(), default=429),
        sa.Column('retry_after_seconds', sa.Integer(), nullable=True),
        sa.Column('country_code', sa.String(2), nullable=True),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('is_repeated', sa.Boolean(), default=False),
        sa.Column('severity_score', sa.Integer(), default=1),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id')),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('platform_api_keys.id')),
        sa.Column('config_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('rate_limit_configs.id'))
    )
    
    # Create indexes
    op.create_index('idx_rate_limit_violations_timestamp', 'rate_limit_violations', ['timestamp'])
    op.create_index('idx_rate_limit_violations_identifier', 'rate_limit_violations', ['identifier'])
    
    # Create endpoint_costs table
    op.create_table(
        'endpoint_costs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('endpoint_pattern', sa.String(500), nullable=False),
        sa.Column('method', sa.String(10), nullable=True),
        sa.Column('base_cost', sa.Float(), default=1.0, nullable=False),
        sa.Column('request_size_factor', sa.Float(), default=0.0),
        sa.Column('response_size_factor', sa.Float(), default=0.0),
        sa.Column('compute_time_factor', sa.Float(), default=0.0),
        sa.Column('database_read_cost', sa.Float(), default=0.1),
        sa.Column('database_write_cost', sa.Float(), default=1.0),
        sa.Column('cache_miss_cost', sa.Float(), default=0.5),
        sa.Column('external_api_cost', sa.Float(), default=2.0),
        sa.Column('ml_inference_cost', sa.Float(), default=5.0),
        sa.Column('ml_training_cost', sa.Float(), default=50.0),
        sa.Column('peak_hours_multiplier', sa.Float(), default=1.5),
        sa.Column('off_hours_multiplier', sa.Float(), default=0.8),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('priority', sa.Integer(), default=0),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('tags', postgresql.JSONB(), default=list),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now())
    )
    
    # Create indexes
    op.create_index('idx_endpoint_costs_pattern', 'endpoint_costs', ['endpoint_pattern'])
    
    # Create rate_limit_overrides table
    op.create_table(
        'rate_limit_overrides',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('target_type', postgresql.ENUM('user', 'api_key', 'ip', 'endpoint', 'global', 
                  'geographic', 'tier', 'custom', name='ratelimittype'), nullable=False),
        sa.Column('target_identifier', sa.String(255), nullable=False),
        sa.Column('requests_per_minute', sa.Integer(), nullable=True),
        sa.Column('requests_per_hour', sa.Integer(), nullable=True),
        sa.Column('requests_per_day', sa.Integer(), nullable=True),
        sa.Column('cost_per_minute', sa.Float(), nullable=True),
        sa.Column('cost_per_hour', sa.Float(), nullable=True),
        sa.Column('cost_per_day', sa.Float(), nullable=True),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('approved_by', sa.String(255), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('metadata', postgresql.JSONB(), default=dict),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'))
    )
    
    # Insert default rate limit configurations
    op.execute("""
        INSERT INTO rate_limit_configs (id, name, description, limit_type, requests_per_minute, 
            requests_per_hour, requests_per_day, algorithm, priority, is_active)
        VALUES 
        (gen_random_uuid(), 'Global Default', 'Default rate limits for all users', 'global', 
            60, 1000, 10000, 'token_bucket', 0, true),
        (gen_random_uuid(), 'Free Tier', 'Rate limits for free tier users', 'tier', 
            30, 500, 5000, 'token_bucket', 10, true),
        (gen_random_uuid(), 'Pro Tier', 'Rate limits for pro tier users', 'tier', 
            120, 2000, 20000, 'token_bucket', 20, true),
        (gen_random_uuid(), 'Enterprise Tier', 'Rate limits for enterprise users', 'tier', 
            600, 10000, 100000, 'token_bucket', 30, true)
    """)
    
    # Insert default endpoint costs
    op.execute("""
        INSERT INTO endpoint_costs (id, endpoint_pattern, base_cost, description, priority)
        VALUES 
        (gen_random_uuid(), '/api/v1/auth/*', 0.5, 'Authentication endpoints', 10),
        (gen_random_uuid(), '/api/v1/users/*', 1.0, 'User management', 5),
        (gen_random_uuid(), '/api/v1/analytics/*', 5.0, 'Analytics endpoints', 20),
        (gen_random_uuid(), '/api/v1/export/*', 10.0, 'Data export endpoints', 30),
        (gen_random_uuid(), '/api/v1/ml/*', 20.0, 'Machine learning endpoints', 40)
    """)


def downgrade() -> None:
    # Drop tables
    op.drop_table('rate_limit_overrides')
    op.drop_table('endpoint_costs')
    op.drop_table('rate_limit_violations')
    op.drop_table('rate_limit_buckets')
    op.drop_table('rate_limit_configs')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS ratelimittier')
    op.execute('DROP TYPE IF EXISTS ratelimitalgorithm')
    op.execute('DROP TYPE IF EXISTS ratelimittype')