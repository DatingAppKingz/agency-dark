"""Add API key audit logs table

Revision ID: 032
Revises: 031
Create Date: 2025-08-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create api_key_audit_logs table for tracking API key usage and changes."""
    
    # Check and create audit_action enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'audit_action'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE audit_action AS ENUM ('api_key.create', 'api_key.update', 'api_key.delete', 'api_key.rotate', 'api_key.enable', 'api_key.disable', 'access.granted', 'access.denied', 'rate_limit.exceeded', 'sync.started', 'sync.completed', 'sync.failed', 'security.invalid_key', 'security.ip_blocked', 'security.suspicious')"))
# Skip enum creation - it's already created by SQLAlchemy
    
    # Create audit logs table (if not exists)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'api_key_audit_logs')"
    ))
    if not result.scalar():
        op.create_table('api_key_audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', postgresql.ENUM('api_key.create', 'api_key.update', 'api_key.delete', 
                                           'api_key.rotate', 'api_key.enable', 'api_key.disable',
                                           'access.granted', 'access.denied', 'rate_limit.exceeded',
                                           'sync.started', 'sync.completed', 'sync.failed',
                                           'security.invalid_key', 'security.ip_blocked', 'security.suspicious',
                                           name='audit_action', create_type=False), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(100), nullable=True),
        sa.Column('request_path', sa.String(500), nullable=True),
        sa.Column('request_method', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
        # Create indexes
        op.create_index('idx_api_key_audit_logs_api_key', 'api_key_audit_logs', ['api_key_id'])
        op.create_index('idx_api_key_audit_logs_agency', 'api_key_audit_logs', ['agency_id'])
        op.create_index('idx_api_key_audit_logs_action', 'api_key_audit_logs', ['action'])
        op.create_index('idx_api_key_audit_logs_created', 'api_key_audit_logs', ['created_at'])
        op.create_index('idx_api_key_audit_logs_request_id', 'api_key_audit_logs', ['request_id'])


def downgrade() -> None:
    """Drop api_key_audit_logs table and related objects."""
    # Drop indexes
    op.drop_index('idx_api_key_audit_logs_request_id', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_created', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_action', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_agency', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_api_key', table_name='api_key_audit_logs')
    
    # Drop table
    op.drop_table('api_key_audit_logs')
    
    # Keep enum type - it's managed by SQLAlchemy
