"""Add missing core tables - chat_messages, financial_transactions, fan_profiles, webhook_logs

Revision ID: 021_add_missing_core_tables
Revises: 020_add_user_profile_fields
Create Date: 2025-08-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '021_add_missing_core_tables'
down_revision = '020_add_user_profile_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing core tables that were referenced but not created."""
    
    # Create chat_messages table
    op.create_table('chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_type', sa.String(20), nullable=False),  # 'model', 'chatter', 'fan'
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_type', sa.String(20), nullable=False, default='text'),  # 'text', 'image', 'video', 'audio'
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, default=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, default=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    )
    
    # Create indexes for chat_messages
    op.create_index('idx_chat_messages_conversation_id', 'chat_messages', ['conversation_id'])
    op.create_index('idx_chat_messages_sender_id', 'chat_messages', ['sender_id'])
    op.create_index('idx_chat_messages_created_at', 'chat_messages', ['created_at'])
    op.create_index('idx_chat_messages_is_read', 'chat_messages', ['is_read'])
    
    # Create chat_conversations table
    op.create_table('chat_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_chatter_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='active'),  # 'active', 'archived', 'blocked'
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unread_count', sa.Integer(), nullable=False, default=0),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['model_id'], ['model_profiles.id'], ),
        sa.ForeignKeyConstraint(['fan_id'], ['fans.id'], ),
        sa.ForeignKeyConstraint(['assigned_chatter_id'], ['users.id'], ),
    )
    
    # Create indexes for chat_conversations
    op.create_index('idx_chat_conversations_agency_id', 'chat_conversations', ['agency_id'])
    op.create_index('idx_chat_conversations_model_id', 'chat_conversations', ['model_id'])
    op.create_index('idx_chat_conversations_fan_id', 'chat_conversations', ['fan_id'])
    op.create_index('idx_chat_conversations_assigned_chatter', 'chat_conversations', ['assigned_chatter_id'])
    op.create_index('idx_chat_conversations_last_message', 'chat_conversations', ['last_message_at'])
    
    # Add foreign key from chat_messages to chat_conversations
    op.create_foreign_key('fk_chat_messages_conversation', 'chat_messages', 'chat_conversations', ['conversation_id'], ['id'])
    
    # Create financial_transactions table
    op.create_table('financial_transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fan_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('transaction_type', sa.String(50), nullable=False),  # 'subscription', 'tip', 'ppv', 'message', 'refund'
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, default='USD'),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),  # 'pending', 'completed', 'failed', 'refunded'
        sa.Column('external_id', sa.String(255), nullable=True),  # ID from OnlyFans/payment processor
        sa.Column('platform', sa.String(50), nullable=False, default='onlyfans'),  # 'onlyfans', 'fansly', etc.
        sa.Column('commission_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('commission_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['model_id'], ['model_profiles.id'], ),
        sa.ForeignKeyConstraint(['fan_id'], ['fans.id'], ),
    )
    
    # Create indexes for financial_transactions
    op.create_index('idx_financial_transactions_agency_id', 'financial_transactions', ['agency_id'])
    op.create_index('idx_financial_transactions_model_id', 'financial_transactions', ['model_id'])
    op.create_index('idx_financial_transactions_fan_id', 'financial_transactions', ['fan_id'])
    op.create_index('idx_financial_transactions_type', 'financial_transactions', ['transaction_type'])
    op.create_index('idx_financial_transactions_status', 'financial_transactions', ['status'])
    op.create_index('idx_financial_transactions_created_at', 'financial_transactions', ['created_at'])
    op.create_index('idx_financial_transactions_external_id', 'financial_transactions', ['external_id'])
    
    # Create fan_profiles table (extended fan information)
    op.create_table('fan_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('fan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('custom_fields', postgresql.JSONB(), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('preferences', postgresql.JSONB(), nullable=True),
        sa.Column('communication_history', postgresql.JSONB(), nullable=True),
        sa.Column('lifetime_value', sa.Numeric(10, 2), nullable=False, default=0),
        sa.Column('last_interaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('churn_risk_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['fan_id'], ['fans.id'], ),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.UniqueConstraint('fan_id', 'agency_id', name='uq_fan_profiles_fan_agency')
    )
    
    # Create indexes for fan_profiles
    op.create_index('idx_fan_profiles_fan_id', 'fan_profiles', ['fan_id'])
    op.create_index('idx_fan_profiles_agency_id', 'fan_profiles', ['agency_id'])
    op.create_index('idx_fan_profiles_lifetime_value', 'fan_profiles', ['lifetime_value'])
    op.create_index('idx_fan_profiles_tags', 'fan_profiles', ['tags'], postgresql_using='gin')
    
    # Create webhook_logs table
    op.create_table('webhook_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),  # Nullable for system-wide webhooks
        sa.Column('provider', sa.String(50), nullable=False),  # 'onlyfans', 'stripe', 'inflow', etc.
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('headers', postgresql.JSONB(), nullable=True),
        sa.Column('signature', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='received'),  # 'received', 'processing', 'processed', 'failed'
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
    )
    
    # Create indexes for webhook_logs
    op.create_index('idx_webhook_logs_agency_id', 'webhook_logs', ['agency_id'])
    op.create_index('idx_webhook_logs_provider', 'webhook_logs', ['provider'])
    op.create_index('idx_webhook_logs_event_type', 'webhook_logs', ['event_type'])
    op.create_index('idx_webhook_logs_status', 'webhook_logs', ['status'])
    op.create_index('idx_webhook_logs_created_at', 'webhook_logs', ['created_at'])


def downgrade() -> None:
    """Drop the tables created in upgrade."""
    # Drop tables in reverse order of creation
    op.drop_table('webhook_logs')
    op.drop_table('fan_profiles')
    op.drop_table('financial_transactions')
    op.drop_table('chat_messages')
    op.drop_table('chat_conversations')