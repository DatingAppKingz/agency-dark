"""Add sync conflict logs table

Revision ID: 026_add_sync_conflict_logs
Revises: 025_fix_chat_tables_structure
Create Date: 2025-01-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '026_add_sync_conflict_logs'
down_revision = '025_fix_chat_tables_structure'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create conflict type enum
    conflict_type = postgresql.ENUM(
        'concurrent_update', 'schema_mismatch', 'data_validation',
        'business_rule', 'delete_modified', 'duplicate_key',
        name='conflict_type'
    )
    conflict_type.create(op.get_bind())
    
    # Create resolution action enum
    resolution_action = postgresql.ENUM(
        'keep_local', 'keep_remote', 'merge',
        'manual', 'skip', 'retry',
        name='resolution_action'
    )
    resolution_action.create(op.get_bind())
    
    # Create sync_conflict_logs table
    op.create_table('sync_conflict_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sync_job_id', sa.String(), nullable=True),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conflict_type', sa.Enum('concurrent_update', 'schema_mismatch', 'data_validation', 'business_rule', 'delete_modified', 'duplicate_key', name='conflict_type'), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('local_id', sa.String(), nullable=False),
        sa.Column('remote_id', sa.String(), nullable=False),
        sa.Column('field_conflicts', sa.JSON(), nullable=True),
        sa.Column('local_data_snapshot', sa.JSON(), nullable=True),
        sa.Column('remote_data_snapshot', sa.JSON(), nullable=True),
        sa.Column('resolution_action', sa.Enum('keep_local', 'keep_remote', 'merge', 'manual', 'skip', 'retry', name='resolution_action'), nullable=False),
        sa.Column('resolved_data', sa.JSON(), nullable=True),
        sa.Column('merge_conflicts', sa.JSON(), nullable=True),
        sa.Column('manual_review_required', sa.Boolean(), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('auto_resolved', sa.Boolean(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_sync_conflict_logs_sync_job_id', 'sync_conflict_logs', ['sync_job_id'], unique=False)
    op.create_index('ix_sync_conflict_logs_agency_id', 'sync_conflict_logs', ['agency_id'], unique=False)
    op.create_index('ix_sync_conflict_logs_api_key_id', 'sync_conflict_logs', ['api_key_id'], unique=False)
    op.create_index('ix_sync_conflict_logs_entity_type', 'sync_conflict_logs', ['entity_type'], unique=False)
    op.create_index('ix_sync_conflict_logs_conflict_type', 'sync_conflict_logs', ['conflict_type'], unique=False)
    op.create_index('ix_sync_conflict_logs_manual_review_required', 'sync_conflict_logs', ['manual_review_required'], unique=False)
    op.create_index('ix_sync_conflict_logs_created_at', 'sync_conflict_logs', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop table
    op.drop_table('sync_conflict_logs')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS conflict_type')
    op.execute('DROP TYPE IF EXISTS resolution_action')