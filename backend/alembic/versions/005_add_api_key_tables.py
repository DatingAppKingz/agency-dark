"""Add API key management tables

Revision ID: 005
Revises: 004
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add API key management tables."""
    
    # Create api_keys table
    op.create_table('api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('key_prefix', sa.String(length=50), nullable=False),
        sa.Column('key_hash', sa.String(length=255), nullable=False),
        sa.Column('encrypted_data', sa.Text(), nullable=False),
        sa.Column('encryption_version', sa.String(length=10), nullable=True),
        sa.Column('scopes', sa.JSON(), nullable=True),
        sa.Column('ip_whitelist', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_rotated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rotation_count', sa.Integer(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('last_ip', sa.String(length=45), nullable=True),
        sa.Column('last_user_agent', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    
    # Create indexes for api_keys
    op.create_index('idx_api_key_user', 'api_keys', ['user_id'], unique=False)
    op.create_index('idx_api_key_agency', 'api_keys', ['agency_id'], unique=False)
    op.create_index('idx_api_key_status', 'api_keys', ['status'], unique=False)
    op.create_index('idx_api_key_expires', 'api_keys', ['expires_at'], unique=False)
    
    # Create api_key_audit_logs table
    op.create_table('api_key_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('performed_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_path', sa.String(length=500), nullable=True),
        sa.Column('request_method', sa.String(length=10), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['performed_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for api_key_audit_logs
    op.create_index('idx_api_key_audit_key', 'api_key_audit_logs', ['api_key_id'], unique=False)
    op.create_index('idx_api_key_audit_action', 'api_key_audit_logs', ['action'], unique=False)
    op.create_index('idx_api_key_audit_created', 'api_key_audit_logs', ['created_at'], unique=False)
    
    # Create api_key_rotation_history table
    op.create_table('api_key_rotation_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('old_key_prefix', sa.String(length=50), nullable=False),
        sa.Column('new_key_prefix', sa.String(length=50), nullable=False),
        sa.Column('rotated_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rotation_reason', sa.String(length=500), nullable=True),
        sa.Column('old_encrypted_data', sa.Text(), nullable=True),
        sa.Column('rotated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('old_key_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rotated_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for api_key_rotation_history
    op.create_index('idx_api_key_rotation_key', 'api_key_rotation_history', ['api_key_id'], unique=False)
    op.create_index('idx_api_key_rotation_date', 'api_key_rotation_history', ['rotated_at'], unique=False)
    
    # Set default values for columns
    op.execute("UPDATE api_keys SET encryption_version = '1.0' WHERE encryption_version IS NULL")
    op.execute("UPDATE api_keys SET scopes = '[]'::jsonb WHERE scopes IS NULL")
    op.execute("UPDATE api_keys SET ip_whitelist = '[]'::jsonb WHERE ip_whitelist IS NULL")
    op.execute("UPDATE api_keys SET status = 'active' WHERE status IS NULL")
    op.execute("UPDATE api_keys SET rotation_count = 0 WHERE rotation_count IS NULL")
    op.execute("UPDATE api_keys SET usage_count = 0 WHERE usage_count IS NULL")
    op.execute("UPDATE api_keys SET metadata = '{}'::jsonb WHERE metadata IS NULL")


def downgrade() -> None:
    """Remove API key management tables."""
    
    # Drop indexes
    op.drop_index('idx_api_key_rotation_date', table_name='api_key_rotation_history')
    op.drop_index('idx_api_key_rotation_key', table_name='api_key_rotation_history')
    op.drop_index('idx_api_key_audit_created', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_action', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_key', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_expires', table_name='api_keys')
    op.drop_index('idx_api_key_status', table_name='api_keys')
    op.drop_index('idx_api_key_agency', table_name='api_keys')
    op.drop_index('idx_api_key_user', table_name='api_keys')
    
    # Drop tables
    op.drop_table('api_key_rotation_history')
    op.drop_table('api_key_audit_logs')
    op.drop_table('api_keys')