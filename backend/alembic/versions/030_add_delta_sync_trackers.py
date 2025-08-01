"""Add delta sync trackers table

Revision ID: 030
Revises: 029
Create Date: 2025-08-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create delta_sync_trackers table for tracking sync state."""
    op.create_table('delta_sync_trackers',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('service_name', sa.String(length=100), nullable=False),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_successful_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_full_sync_at', sa.DateTime(), nullable=True),
        sa.Column('last_cursor', sa.String(length=500), nullable=True),
        sa.Column('checksum_cache', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('deleted_ids', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('service_name')
    )
    
    # Create indexes for better performance
    op.create_index(
        'idx_delta_sync_trackers_service_name',
        'delta_sync_trackers',
        ['service_name']
    )
    
    op.create_index(
        'idx_delta_sync_trackers_last_sync',
        'delta_sync_trackers',
        ['last_sync_at']
    )
    
    # Add updated_at trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    op.execute("""
        CREATE TRIGGER update_delta_sync_trackers_updated_at 
        BEFORE UPDATE ON delta_sync_trackers 
        FOR EACH ROW 
        EXECUTE FUNCTION update_updated_at_column();
    """)


def downgrade() -> None:
    """Drop delta_sync_trackers table and related objects."""
    # Drop trigger first
    op.execute("DROP TRIGGER IF EXISTS update_delta_sync_trackers_updated_at ON delta_sync_trackers;")
    
    # Drop indexes
    op.drop_index('idx_delta_sync_trackers_last_sync', table_name='delta_sync_trackers')
    op.drop_index('idx_delta_sync_trackers_service_name', table_name='delta_sync_trackers')
    
    # Drop table
    op.drop_table('delta_sync_trackers')