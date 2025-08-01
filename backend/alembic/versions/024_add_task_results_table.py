"""Add task results table

Revision ID: 024_add_task_results
Revises: 023_add_media_management
Create Date: 2025-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '024_add_task_results'
down_revision = '023_add_media_management'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create task status enum
    op.execute("CREATE TYPE taskstatus AS ENUM ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'RETRY', 'REVOKED')")
    
    # Create task_results table
    op.create_table(
        'task_results',
        sa.Column('task_id', sa.String(255), nullable=False),
        sa.Column('task_name', sa.String(255), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'RETRY', 'REVOKED', name='taskstatus'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('params', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('traceback', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('task_id')
    )
    
    # Create indexes
    op.create_index('ix_task_results_task_name', 'task_results', ['task_name'])
    op.create_index('ix_task_results_status', 'task_results', ['status'])
    op.create_index('ix_task_results_user_id', 'task_results', ['user_id'])
    op.create_index('ix_task_results_agency_id', 'task_results', ['agency_id'])
    op.create_index('ix_task_results_created_at', 'task_results', ['created_at'])
    
    # Add relationships to existing tables
    # Note: These are handled by SQLAlchemy relationships, no database changes needed


def downgrade() -> None:
    # Drop table
    op.drop_table('task_results')
    
    # Drop enum
    op.execute('DROP TYPE taskstatus')