"""Create chat system tables - simplified version

Revision ID: 035
Revises: 034
Create Date: 2025-01-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade():
    # First ensure we have UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create models table if it doesn't exist (rename from model_profiles)
    op.execute("""
        ALTER TABLE IF EXISTS model_profiles RENAME TO models;
    """)
    
    # Create conversations table (check if it exists as conversations or chat_conversations)
    conn = op.get_bind()
    
    # Check if chat_conversations exists (from migration 021)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_conversations')"
    ))
    chat_conversations_exists = result.scalar()
    
    # Check if conversations exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'conversations')"
    ))
    conversations_exists = result.scalar()
    
    if chat_conversations_exists and not conversations_exists:
        # Rename chat_conversations to conversations
        op.rename_table('chat_conversations', 'conversations')
    elif not conversations_exists:
        # Create new table
        op.create_table('conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fan_id', sa.String(255), nullable=False),
        sa.Column('fan_username', sa.String(255), nullable=False),
        sa.Column('fan_display_name', sa.String(255), nullable=True),
        sa.Column('assigned_chatter_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_at', sa.String(30), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fan_avatar_url', sa.String(500), nullable=True),
        sa.Column('fan_location', sa.String(255), nullable=True),
        sa.Column('fan_timezone', sa.String(50), nullable=True),
        sa.Column('fan_language', sa.String(10), nullable=False, server_default='en'),
        sa.Column('total_spent', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('total_tips', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('ppv_purchased', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_message_at', sa.String(30), nullable=True),
        sa.Column('last_fan_message_at', sa.String(30), nullable=True),
        sa.Column('unread_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tags', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('platform_data', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
        # Create indexes for conversations if we just created it
        op.create_index('idx_conversations_model_id', 'conversations', ['model_id'])
        op.create_index('idx_conversations_fan_id', 'conversations', ['fan_id'])
        op.create_index('idx_conversations_assigned_chatter_id', 'conversations', ['assigned_chatter_id'])
        op.create_index('idx_conversations_status', 'conversations', ['status'])
        op.create_index('idx_conversations_last_message_at', 'conversations', ['last_message_at'])
        op.create_index('idx_conversations_agency_id', 'conversations', ['agency_id'])
    
    # Create messages table (check if it exists as messages or chat_messages)
    # Check if chat_messages exists (from migration 021)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_messages')"
    ))
    chat_messages_exists = result.scalar()
    
    # Check if messages exists
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'messages')"
    ))
    messages_exists = result.scalar()
    
    if chat_messages_exists and not messages_exists:
        # Rename chat_messages to messages
        op.rename_table('chat_messages', 'messages')
    elif not messages_exists:
        # Create new table
        op.create_table('messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sender_type', sa.String(20), nullable=False),
        sa.Column('type', sa.String(20), nullable=False, server_default='text'),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('media_url', sa.String(500), nullable=True),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='sent'),
        sa.Column('delivered_at', sa.String(30), nullable=True),
        sa.Column('read_at', sa.String(30), nullable=True),
        sa.Column('amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=True, server_default='USD'),
        sa.Column('is_paid', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('platform_message_id', sa.String(255), nullable=True),
        sa.Column('platform_data', postgresql.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_flagged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('flagged_reason', sa.String(255), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
        # Create indexes for messages if we just created it
        op.create_index('idx_messages_conversation_id', 'messages', ['conversation_id'])
        op.create_index('idx_messages_sender_id', 'messages', ['sender_id'])
        op.create_index('idx_messages_created_at', 'messages', ['created_at'])
        op.create_index('idx_messages_status', 'messages', ['status'])
        op.create_index('idx_messages_platform_message_id', 'messages', ['platform_message_id'], unique=True)
        op.create_index('idx_messages_agency_id', 'messages', ['agency_id'])
    
    # Create chat_templates table (if not exists)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'chat_templates')"
    ))
    if not result.scalar():
        op.create_table('chat_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('variables', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tags', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('languages', postgresql.JSON(), nullable=False, server_default='["en"]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
        # Create indexes for chat_templates
        op.create_index('idx_chat_templates_agency_id', 'chat_templates', ['agency_id'])
        op.create_index('idx_chat_templates_category', 'chat_templates', ['category'])
        op.create_index('idx_chat_templates_is_active', 'chat_templates', ['is_active'])
    
    # Create conversation_analytics table (if not exists)
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'conversation_analytics')"
    ))
    if not result.scalar():
        op.create_table('conversation_analytics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('date', sa.String(10), nullable=False),
        sa.Column('messages_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('messages_received', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('response_time_avg', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('response_time_min', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('response_time_max', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('revenue', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('tips_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tips_amount', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('ppv_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ppv_amount', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id', 'date', name='uq_conversation_analytics_date')
    )
    
        # Create indexes for conversation_analytics
        op.create_index('idx_conversation_analytics_conversation_id', 'conversation_analytics', ['conversation_id'])
        op.create_index('idx_conversation_analytics_date', 'conversation_analytics', ['date'])


def downgrade():
    # Drop all tables
    op.drop_table('conversation_analytics')
    op.drop_table('chat_templates')
    op.drop_table('messages')
    op.drop_table('conversations')
