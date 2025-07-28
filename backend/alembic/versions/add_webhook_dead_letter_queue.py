"""add webhook dead letter queue

Revision ID: add_webhook_dead_letter_queue
Revises: 
Create Date: 2025-01-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sys
import os

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# revision identifiers, used by Alembic.
revision = 'add_webhook_dead_letter_queue'
down_revision = '011_add_monitoring_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create webhook_dead_letters table
    op.create_table('webhook_dead_letters',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('webhook_id', sa.String(), nullable=False),
        sa.Column('delivery_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('final_status_code', sa.Integer(), nullable=True),
        sa.Column('total_attempts', sa.Integer(), nullable=False),
        sa.Column('first_attempt_at', sa.DateTime(), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=False),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_reprocessed', sa.Boolean(), nullable=True),
        sa.Column('reprocessed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['delivery_id'], ['webhook_deliveries.id'], ),
        sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_webhook_dead_letters_webhook_id'), 'webhook_dead_letters', ['webhook_id'], unique=False)
    op.create_index(op.f('ix_webhook_dead_letters_event_type'), 'webhook_dead_letters', ['event_type'], unique=False)
    op.create_index(op.f('ix_webhook_dead_letters_created_at'), 'webhook_dead_letters', ['created_at'], unique=False)
    op.create_index(op.f('ix_webhook_dead_letters_expires_at'), 'webhook_dead_letters', ['expires_at'], unique=False)
    op.create_index(op.f('ix_webhook_dead_letters_is_reprocessed'), 'webhook_dead_letters', ['is_reprocessed'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_webhook_dead_letters_is_reprocessed'), table_name='webhook_dead_letters')
    op.drop_index(op.f('ix_webhook_dead_letters_expires_at'), table_name='webhook_dead_letters')
    op.drop_index(op.f('ix_webhook_dead_letters_created_at'), table_name='webhook_dead_letters')
    op.drop_index(op.f('ix_webhook_dead_letters_event_type'), table_name='webhook_dead_letters')
    op.drop_index(op.f('ix_webhook_dead_letters_webhook_id'), table_name='webhook_dead_letters')
    
    # Drop table
    op.drop_table('webhook_dead_letters')