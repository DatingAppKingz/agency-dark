"""add security tables

Revision ID: 008
Revises: 007
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_category', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('user_role', sa.String(50), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('target_type', sa.String(100), nullable=True),
        sa.Column('target_id', sa.String(100), nullable=True),
        sa.Column('target_name', sa.String(200), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_timestamp', 'audit_logs', ['timestamp'], unique=False)
    op.create_index('idx_audit_event_type', 'audit_logs', ['event_type'], unique=False)
    op.create_index('idx_audit_user_agency', 'audit_logs', ['user_id', 'agency_id'], unique=False)

    # Create api_keys table
    op.create_table('api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('key_hash', sa.String(128), nullable=False),
        sa.Column('key_prefix', sa.String(8), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('rate_limit', sa.Integer(), nullable=True),
        sa.Column('ip_whitelist', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_ip', sa.String(45), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rotated_from', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    op.create_index('idx_api_key_agency', 'api_keys', ['agency_id'], unique=False)
    op.create_index('idx_api_key_prefix', 'api_keys', ['key_prefix'], unique=False)
    op.create_index('idx_api_key_active', 'api_keys', ['is_active'], unique=False)

    # Add encrypted fields to existing tables (example for wallet addresses)
    op.add_column('wallet_addresses', 
        sa.Column('address_encrypted', sa.String(500), nullable=True)
    )
    
    # Add security-related fields to users table
    op.add_column('users',
        sa.Column('failed_login_attempts', sa.Integer(), default=0)
    )
    op.add_column('users',
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('users',
        sa.Column('last_password_change', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('users',
        sa.Column('require_password_change', sa.Boolean(), default=False)
    )
    op.add_column('users',
        sa.Column('two_factor_enabled', sa.Boolean(), default=False)
    )
    op.add_column('users',
        sa.Column('two_factor_secret', sa.String(255), nullable=True)
    )


def downgrade():
    # Remove security fields from users table
    op.drop_column('users', 'two_factor_secret')
    op.drop_column('users', 'two_factor_enabled')
    op.drop_column('users', 'require_password_change')
    op.drop_column('users', 'last_password_change')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')
    
    # Remove encrypted fields
    op.drop_column('wallet_addresses', 'address_encrypted')
    
    # Drop indexes and tables
    op.drop_index('idx_api_key_active', table_name='api_keys')
    op.drop_index('idx_api_key_prefix', table_name='api_keys')
    op.drop_index('idx_api_key_agency', table_name='api_keys')
    op.drop_table('api_keys')
    
    op.drop_index('idx_audit_user_agency', table_name='audit_logs')
    op.drop_index('idx_audit_event_type', table_name='audit_logs')
    op.drop_index('idx_audit_timestamp', table_name='audit_logs')
    op.drop_table('audit_logs')