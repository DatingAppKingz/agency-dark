"""Add API key audit logs table

Revision ID: 032_add_api_key_audit_logs
Revises: 031_add_sync_fields_to_api_keys
Create Date: 2025-08-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '032_add_api_key_audit_logs'
down_revision = '031_add_sync_fields_to_api_keys'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create api_key_audit_logs table for tracking API key usage and changes."""
    # Skip enum creation - it's already created by SQLAlchemy
    
    # Create audit logs table
    op.create_table('api_key_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', postgresql.ENUM('api_key.create', 'api_key.update', 'api_key.delete', 
                                           'api_key.rotate', 'api_key.enable', 'api_key.disable',
                                           'access.granted', 'access.denied', 'rate_limit.exceeded',
                                           'sync.started', 'sync.completed', 'sync.failed',
                                           'security.invalid_key', 'security.ip_blocked', 'security.suspicious',
                                           name='audit_action'), nullable=False),
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
    
    # Create indexes for efficient querying
    op.create_index('idx_api_key_audit_logs_api_key_id', 'api_key_audit_logs', ['api_key_id'])
    op.create_index('idx_api_key_audit_logs_user_id', 'api_key_audit_logs', ['user_id'])
    op.create_index('idx_api_key_audit_logs_agency_id', 'api_key_audit_logs', ['agency_id'])
    op.create_index('idx_api_key_audit_logs_action', 'api_key_audit_logs', ['action'])
    op.create_index('idx_api_key_audit_logs_created_at', 'api_key_audit_logs', ['created_at'])
    op.create_index('idx_api_key_audit_logs_ip_address', 'api_key_audit_logs', ['ip_address'])
    
    # Composite index for common queries
    op.create_index(
        'idx_api_key_audit_logs_api_key_created',
        'api_key_audit_logs',
        ['api_key_id', 'created_at']
    )


def downgrade() -> None:
    """Drop api_key_audit_logs table and related objects."""
    # Drop indexes
    op.drop_index('idx_api_key_audit_logs_api_key_created', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_ip_address', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_created_at', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_action', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_agency_id', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_user_id', table_name='api_key_audit_logs')
    op.drop_index('idx_api_key_audit_logs_api_key_id', table_name='api_key_audit_logs')
    
    # Drop table
    op.drop_table('api_key_audit_logs')
    
    # Keep enum type - it's managed by SQLAlchemy