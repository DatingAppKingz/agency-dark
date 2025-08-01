"""Add task results table

Revision ID: 033
Revises: 032
Create Date: 2025-01-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    
    # Check and create taskstatus enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'taskstatus'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE taskstatus AS ENUM ('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'RETRY', 'REVOKED')"))
# Create task status enum
    
    # Create task_results table
    op.create_table(
        'task_results',
        sa.Column('task_id', sa.String(255), nullable=False),
        sa.Column('task_name', sa.String(255), nullable=False),
        sa.Column('status', postgresql.ENUM('PENDING', 'STARTED', 'SUCCESS', 'FAILURE', 'RETRY', 'REVOKED', name='taskstatus', create_type=False), nullable=False),
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