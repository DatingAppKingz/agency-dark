"""Add sync fields to api_keys table

Revision ID: 031
Revises: 030
Create Date: 2025-08-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add sync-related fields to api_keys table."""
    # Add sync configuration fields
    op.add_column('api_keys', sa.Column('sync_enabled', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('api_keys', sa.Column('sync_interval_minutes', sa.Integer(), server_default='30', nullable=False))
    op.add_column('api_keys', sa.Column('last_sync_at', sa.DateTime(), nullable=True))
    op.add_column('api_keys', sa.Column('last_sync_status', sa.String(50), nullable=True))
    op.add_column('api_keys', sa.Column('last_sync_error', sa.Text(), nullable=True))
    op.add_column('api_keys', sa.Column('sync_failure_count', sa.Integer(), server_default='0', nullable=False))
    
    # Add index for finding keys that need syncing
    op.create_index(
        'idx_api_keys_sync_enabled_last_sync',
        'api_keys',
        ['sync_enabled', 'last_sync_at'],
        postgresql_where=sa.text("sync_enabled = true")
    )


def downgrade() -> None:
    """Remove sync-related fields from api_keys table."""
    # Drop index
    op.drop_index('idx_api_keys_sync_enabled_last_sync', table_name='api_keys')
    
    # Drop columns
    op.drop_column('api_keys', 'sync_failure_count')
    op.drop_column('api_keys', 'last_sync_error')
    op.drop_column('api_keys', 'last_sync_status')
    op.drop_column('api_keys', 'last_sync_at')
    op.drop_column('api_keys', 'sync_interval_minutes')
    op.drop_column('api_keys', 'sync_enabled')