"""Add scheduled tasks tables

Revision ID: 039_add_scheduled_tasks
Revises: 038_add_external_api_tables
Create Date: 2024-01-15 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '039_add_scheduled_tasks'
down_revision = '038_add_external_api_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create scheduled_tasks table
    op.create_table('scheduled_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('cron_expression', sa.String(length=100), nullable=False),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_run', sa.DateTime(), nullable=True),
        sa.Column('last_run_status', sa.String(length=20), nullable=True),
        sa.Column('last_run_result', sa.JSON(), nullable=True),
        sa.Column('next_run', sa.DateTime(), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, default=0),
        sa.Column('failure_count', sa.Integer(), nullable=False, default=0),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for scheduled_tasks
    op.create_index('idx_scheduled_task_agency', 'scheduled_tasks', ['agency_id'])
    op.create_index('idx_scheduled_task_type', 'scheduled_tasks', ['task_type'])
    op.create_index('idx_scheduled_task_active', 'scheduled_tasks', ['is_active'])
    op.create_index('idx_scheduled_task_next_run', 'scheduled_tasks', ['next_run'])
    
    # Create scheduled_task_executions table
    op.create_table('scheduled_task_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('records_processed', sa.Integer(), nullable=True),
        sa.Column('records_failed', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['scheduled_tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for scheduled_task_executions
    op.create_index('idx_execution_task', 'scheduled_task_executions', ['task_id'])
    op.create_index('idx_execution_started', 'scheduled_task_executions', ['started_at'])
    op.create_index('idx_execution_status', 'scheduled_task_executions', ['status'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('scheduled_task_executions')
    op.drop_table('scheduled_tasks')