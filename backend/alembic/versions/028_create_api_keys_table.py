"""Create API keys table for encrypted external service credentials

Revision ID: 028_create_api_keys_table
Revises: 027_add_commission_tracking
Create Date: 2024-01-31 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '028_create_api_keys_table'
down_revision = '027_add_commission_tracking'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create API keys table and related structures."""
    
    # Create API key provider enum
    op.execute("CREATE TYPE apikeyprovider AS ENUM ('onlyfans', 'stripe', 'inflow', 'custom')")
    
    # Create API key status enum
    op.execute("CREATE TYPE apikeystatus AS ENUM ('active', 'inactive', 'expired', 'revoked')")
    
    # Create api_keys table
    op.create_table('api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', postgresql.ENUM('onlyfans', 'stripe', 'inflow', 'custom', name='apikeyprovider', create_type=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('key_prefix', sa.String(16), nullable=False),
        sa.Column('encrypted_value', sa.Text(), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'expired', 'revoked', name='apikeystatus', create_type=False), nullable=False, server_default='active'),
        sa.Column('last_validated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_rotated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('allowed_ips', sa.JSON(), nullable=True),
        sa.Column('permissions', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_api_keys_agency_provider', 'api_keys', ['agency_id', 'provider'])
    op.create_index('idx_api_keys_status', 'api_keys', ['status'])
    op.create_index('idx_api_keys_expires_at', 'api_keys', ['expires_at'], postgresql_where=sa.text("expires_at IS NOT NULL"))
    
    # Create api_key_usage table for tracking
    op.create_table('api_key_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_key_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.String(500), nullable=False),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('request_size', sa.Integer(), nullable=True),
        sa.Column('response_size', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for usage analytics
    op.create_index('idx_api_key_usage_key_created', 'api_key_usage', ['api_key_id', 'created_at'])
    op.create_index('idx_api_key_usage_endpoint', 'api_key_usage', ['endpoint'])
    
    # Create api_key_audit_logs table
    op.create_table('api_key_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_key_id', sa.Integer(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),  # created, updated, rotated, validated, deactivated, accessed
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for audit log queries
    op.create_index('idx_api_key_audit_key_created', 'api_key_audit_logs', ['api_key_id', 'created_at'])
    op.create_index('idx_api_key_audit_action', 'api_key_audit_logs', ['action'])


def downgrade() -> None:
    """Drop API keys tables and enums."""
    
    # Drop tables
    op.drop_table('api_key_audit_logs')
    op.drop_table('api_key_usage')
    op.drop_table('api_keys')
    
    # Drop enums
    op.execute("DROP TYPE apikeystatus")
    op.execute("DROP TYPE apikeyprovider")