"""Create webhook tables for receiving external events

Revision ID: 029_create_webhook_tables
Revises: 028_create_api_keys_table
Create Date: 2024-01-31 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '029_create_webhook_tables'
down_revision = '028_create_api_keys_table'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create webhook tables and related structures."""
    
    # Create webhook event enum
    op.execute("""
        CREATE TYPE webhookevent AS ENUM (
            'model.created', 'model.updated', 'model.deleted', 'model.verified',
            'transaction.created', 'transaction.completed', 'transaction.failed',
            'message.received', 'message.sent',
            'content.published', 'content.purchased',
            'payout.scheduled', 'payout.completed', 'payout.failed'
        )
    """)
    
    # Create webhook status enum
    op.execute("CREATE TYPE webhookstatus AS ENUM ('active', 'inactive', 'failed')")
    
    # Create webhooks table
    op.create_table('webhooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('secret', sa.String(255), nullable=False),
        sa.Column('events', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('headers', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'failed', name='webhookstatus', create_type=False), nullable=False, server_default='active'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('total_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('successful_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_called_at', sa.String(30), nullable=True),
        sa.Column('last_error', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_webhooks_agency_status', 'webhooks', ['agency_id', 'status'])
    op.create_index('idx_webhooks_is_active', 'webhooks', ['is_active'])
    
    # Create webhook_deliveries table
    op.create_table('webhook_deliveries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('webhook_id', sa.Integer(), nullable=False),
        sa.Column('event', sa.String(50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.String(2000), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('is_successful', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('error_message', sa.String(500), nullable=True),
        sa.Column('next_retry_at', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['webhook_id'], ['webhooks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for deliveries
    op.create_index('idx_webhook_deliveries_webhook_created', 'webhook_deliveries', ['webhook_id', 'created_at'])
    op.create_index('idx_webhook_deliveries_event', 'webhook_deliveries', ['event'])
    op.create_index('idx_webhook_deliveries_retry', 'webhook_deliveries', ['is_successful', 'next_retry_at'])
    
    # Create webhook_logs table (this replaces webhook_logs if it doesn't exist)
    op.execute("""
        CREATE TABLE IF NOT EXISTS webhook_logs (
            id SERIAL PRIMARY KEY,
            provider VARCHAR(50) NOT NULL,
            event_type VARCHAR(100) NOT NULL,
            payload JSON NOT NULL,
            status VARCHAR(50) NOT NULL,
            error_message TEXT,
            response_code INTEGER,
            response_body TEXT,
            processing_time_ms INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
    """)
    
    # Create index for webhook_logs
    op.create_index('idx_webhook_logs_provider_created', 'webhook_logs', ['provider', 'created_at'])
    op.create_index('idx_webhook_logs_event_type', 'webhook_logs', ['event_type'])
    op.create_index('idx_webhook_logs_status', 'webhook_logs', ['status'])


def downgrade() -> None:
    """Drop webhook tables and enums."""
    
    # Drop tables
    op.drop_table('webhook_logs')
    op.drop_table('webhook_deliveries')
    op.drop_table('webhooks')
    
    # Drop enums
    op.execute("DROP TYPE webhookstatus")
    op.execute("DROP TYPE webhookevent")