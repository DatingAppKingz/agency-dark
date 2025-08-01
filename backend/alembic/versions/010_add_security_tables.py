"""add security tables

Revision ID: 010
Revises: 009
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    """Add security-related fields to existing tables."""
    
    # NOTE: audit_logs table already exists from migration 001
    # NOTE: api_keys table already exists from migration 005
    # NOTE: wallet_addresses table doesn't exist yet in the migration sequence
    
    # Add security-related fields to users table
    op.add_column('users',
        sa.Column('failed_login_attempts', sa.Integer(), server_default='0')
    )
    op.add_column('users',
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('users',
        sa.Column('last_password_change', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('users',
        sa.Column('require_password_change', sa.Boolean(), server_default='false')
    )
    op.add_column('users',
        sa.Column('two_factor_enabled', sa.Boolean(), server_default='false')
    )
    op.add_column('users',
        sa.Column('two_factor_secret', sa.String(255), nullable=True)
    )
    
    # Add additional indexes for audit_logs that weren't created in migration 001
    op.create_index('idx_audit_timestamp', 'audit_logs', ['created_at'], unique=False)
    op.create_index('idx_audit_event_type', 'audit_logs', ['action'], unique=False)
    op.create_index('idx_audit_user_agency', 'audit_logs', ['user_id', 'agency_id'], unique=False)
    
    # NOTE: api_keys table already has indexes created in migration 005
    # - idx_api_key_user, idx_api_key_agency, idx_api_key_status, idx_api_key_expires


def downgrade():
    """Remove security-related fields."""
    
    # Remove additional indexes
    op.drop_index('idx_audit_user_agency', table_name='audit_logs')
    op.drop_index('idx_audit_event_type', table_name='audit_logs')
    op.drop_index('idx_audit_timestamp', table_name='audit_logs')
    
    # Remove security fields from users table
    op.drop_column('users', 'two_factor_secret')
    op.drop_column('users', 'two_factor_enabled')
    op.drop_column('users', 'require_password_change')
    op.drop_column('users', 'last_password_change')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'failed_login_attempts')