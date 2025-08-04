"""Enhance chat system with encryption and analytics

Revision ID: 012_enhance_chat_system
Revises: 011_add_email_system
Create Date: 2024-01-29 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012_enhance_chat_system'
down_revision = '011_add_email_system'
branch_labels = None
depends_on = None


def upgrade():
    # Add encryption fields to messages table
    op.add_column('messages', sa.Column('encrypted_content', sa.Text(), nullable=True))
    op.add_column('messages', sa.Column('encryption_key_id', sa.String(length=255), nullable=True))
    op.add_column('messages', sa.Column('media_encryption_key', sa.Text(), nullable=True))
    
    # Add agency_id to messages for multi-tenant support
    op.add_column('messages', sa.Column('agency_id', sa.Integer(), nullable=True))
    
    # Create foreign key for agency_id
    op.create_foreign_key(
        'fk_messages_agency_id',
        'messages', 'agencies',
        ['agency_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Add agency_id to conversations if not exists
    try:
        op.add_column('conversations', sa.Column('agency_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_conversations_agency_id',
            'conversations', 'agencies',
            ['agency_id'], ['id'],
            ondelete='CASCADE'
        )
    except:
        pass  # Column might already exist
    
    # Create chat_analytics table for storing aggregated analytics
    op.create_table('chat_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('model_id', sa.Integer(), nullable=True),
        sa.Column('agency_id', sa.Integer(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('messages_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('messages_received', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tips_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tips_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('ppv_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ppv_purchased', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ppv_revenue', sa.Numeric(12, 2), nullable=False, server_default='0.00'),
        sa.Column('avg_response_time', sa.Integer(), nullable=True),  # in seconds
        sa.Column('unique_fans', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('new_conversations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for chat_analytics
    op.create_index('idx_chat_analytics_date', 'chat_analytics', ['date'])
    op.create_index('idx_chat_analytics_conversation', 'chat_analytics', ['conversation_id', 'date'])
    op.create_index('idx_chat_analytics_model', 'chat_analytics', ['model_id', 'date'])
    op.create_index('idx_chat_analytics_agency', 'chat_analytics', ['agency_id', 'date'])
    
    # Create unique constraint for daily analytics
    op.create_unique_constraint(
        'uq_chat_analytics_daily',
        'chat_analytics',
        ['conversation_id', 'date']
    )
    
    # Create conversation_tags table for categorizing conversations
    op.create_table('conversation_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('tag', sa.String(length=50), nullable=False),
        sa.Column('added_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(['added_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for tags
    op.create_index('idx_conversation_tags_conversation', 'conversation_tags', ['conversation_id'])
    op.create_index('idx_conversation_tags_tag', 'conversation_tags', ['tag'])
    
    # Create moderation_log table
    op.create_table('moderation_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('moderator_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['moderator_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for moderation_log
    op.create_index('idx_moderation_log_user', 'moderation_log', ['user_id'])
    op.create_index('idx_moderation_log_action', 'moderation_log', ['action'])
    op.create_index('idx_moderation_log_created', 'moderation_log', ['created_at'])
    
    # Add indexes to improve chat query performance
    op.create_index('idx_messages_encrypted', 'messages', ['encryption_key_id'])
    op.create_index('idx_messages_agency', 'messages', ['agency_id'])
    op.create_index('idx_conversations_agency', 'conversations', ['agency_id'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_conversations_agency', 'conversations')
    op.drop_index('idx_messages_agency', 'messages')
    op.drop_index('idx_messages_encrypted', 'messages')
    
    # Drop moderation_log
    op.drop_index('idx_moderation_log_created', 'moderation_log')
    op.drop_index('idx_moderation_log_action', 'moderation_log')
    op.drop_index('idx_moderation_log_user', 'moderation_log')
    op.drop_table('moderation_log')
    
    # Drop conversation_tags
    op.drop_index('idx_conversation_tags_tag', 'conversation_tags')
    op.drop_index('idx_conversation_tags_conversation', 'conversation_tags')
    op.drop_table('conversation_tags')
    
    # Drop chat_analytics
    op.drop_constraint('uq_chat_analytics_daily', 'chat_analytics', type_='unique')
    op.drop_index('idx_chat_analytics_agency', 'chat_analytics')
    op.drop_index('idx_chat_analytics_model', 'chat_analytics')
    op.drop_index('idx_chat_analytics_conversation', 'chat_analytics')
    op.drop_index('idx_chat_analytics_date', 'chat_analytics')
    op.drop_table('chat_analytics')
    
    # Drop foreign keys
    op.drop_constraint('fk_messages_agency_id', 'messages', type_='foreignkey')
    
    # Drop columns from messages
    op.drop_column('messages', 'agency_id')
    op.drop_column('messages', 'media_encryption_key')
    op.drop_column('messages', 'encryption_key_id')
    op.drop_column('messages', 'encrypted_content')