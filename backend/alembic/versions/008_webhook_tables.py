"""
Add webhook tables

Revision ID: 008_webhook_tables
Revises: 007_performance_indexes
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '008_webhook_tables'
down_revision = '007_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # Create webhooks table
    op.create_table(
        'webhooks',
        sa.Column('id', sa.String(), nullable=False, default=lambda: str(uuid.uuid4())),
        sa.Column('agency_id', sa.String(), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('secret', sa.String(), nullable=False),
        sa.Column('events', sa.JSON(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        
        # Configuration
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('retry_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, default=30),
        sa.Column('custom_headers', sa.JSON(), nullable=False, default={}),
        
        # Statistics
        sa.Column('total_deliveries', sa.Integer(), nullable=False, default=0),
        sa.Column('successful_deliveries', sa.Integer(), nullable=False, default=0),
        sa.Column('failed_deliveries', sa.Integer(), nullable=False, default=0),
        sa.Column('last_delivery_at', sa.DateTime(), nullable=True),
        sa.Column('last_success_at', sa.DateTime(), nullable=True),
        sa.Column('last_failure_at', sa.DateTime(), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE')
    )
    
    # Create webhook_deliveries table
    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.String(), nullable=False, default=lambda: str(uuid.uuid4())),
        sa.Column('webhook_id', sa.String(), nullable=False),
        sa.Column('event_type', sa.String(), nullable=False),
        sa.Column('event_id', sa.String(), nullable=False),
        
        # Delivery details
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        
        # Request/Response
        sa.Column('request_headers', sa.JSON(), nullable=True),
        sa.Column('request_body', sa.JSON(), nullable=True),
        sa.Column('response_status_code', sa.Integer(), nullable=True),
        sa.Column('response_headers', sa.JSON(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        
        # Error details
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index('idx_webhooks_agency_id', 'webhooks', ['agency_id'])
    op.create_index('idx_webhooks_is_active', 'webhooks', ['is_active'])
    op.create_index('idx_webhooks_events', 'webhooks', ['events'], postgresql_using='gin')
    
    op.create_index('idx_webhook_deliveries_webhook_id', 'webhook_deliveries', ['webhook_id'])
    op.create_index('idx_webhook_deliveries_status', 'webhook_deliveries', ['status'])
    op.create_index('idx_webhook_deliveries_event_type', 'webhook_deliveries', ['event_type'])
    op.create_index('idx_webhook_deliveries_created_at', 'webhook_deliveries', ['created_at'])
    op.create_index(
        'idx_webhook_deliveries_retry',
        'webhook_deliveries',
        ['status', 'next_retry_at'],
        postgresql_where=sa.text("status = 'retrying'")
    )


def downgrade():
    # Drop indexes
    op.drop_index('idx_webhook_deliveries_retry', table_name='webhook_deliveries')
    op.drop_index('idx_webhook_deliveries_created_at', table_name='webhook_deliveries')
    op.drop_index('idx_webhook_deliveries_event_type', table_name='webhook_deliveries')
    op.drop_index('idx_webhook_deliveries_status', table_name='webhook_deliveries')
    op.drop_index('idx_webhook_deliveries_webhook_id', table_name='webhook_deliveries')
    
    op.drop_index('idx_webhooks_events', table_name='webhooks')
    op.drop_index('idx_webhooks_is_active', table_name='webhooks')
    op.drop_index('idx_webhooks_agency_id', table_name='webhooks')
    
    # Drop tables
    op.drop_table('webhook_deliveries')
    op.drop_table('webhooks')
