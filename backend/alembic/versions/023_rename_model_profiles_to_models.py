"""Rename model_profiles table to models to match codebase

Revision ID: 023
Revises: 022
Create Date: 2025-08-01

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename model_profiles table and related constraints/indexes to match code expectations."""
    
    # Rename the table
    op.rename_table('model_profiles', 'models')
    
    # Rename indexes (with existence checks)
    connection = op.get_bind()
    
    # Check and rename each index
    indexes_to_rename = [
        ('ix_model_profiles_agency_id', 'ix_models_agency_id'),
        ('idx_model_profiles_agency_active', 'idx_models_agency_active'),
        ('idx_model_profiles_agency_covering', 'idx_models_agency_covering'),
        ('idx_model_profiles_agency_id', 'idx_models_agency_id_2'),
        ('idx_model_profiles_agency_platform', 'idx_models_agency_platform')
    ]
    
    for old_name, new_name in indexes_to_rename:
        result = connection.execute(
            sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
            {"name": old_name}
        )
        if result.fetchone():
            op.execute(f'ALTER INDEX {old_name} RENAME TO {new_name}')
        else:
            print(f"Index {old_name} does not exist, skipping rename")
    
    # Rename constraints
    op.execute('ALTER TABLE models RENAME CONSTRAINT model_profiles_pkey TO models_pkey')
    op.execute('ALTER TABLE models RENAME CONSTRAINT model_profiles_agency_id_fkey TO models_agency_id_fkey')
    op.execute('ALTER TABLE models RENAME CONSTRAINT model_profiles_user_id_fkey TO models_user_id_fkey')
    op.execute('ALTER TABLE models RENAME CONSTRAINT model_profiles_onlyfans_username_key TO models_onlyfans_username_key')
    op.execute('ALTER TABLE models RENAME CONSTRAINT model_profiles_onlyfans_user_id_key TO models_onlyfans_user_id_key')
    
    # Update foreign key references in other tables
    # model_chatters table
    op.execute('ALTER TABLE model_chatters DROP CONSTRAINT model_chatters_model_id_fkey')
    op.create_foreign_key('model_chatters_model_id_fkey', 'model_chatters', 'models', ['model_id'], ['id'])
    
    # chat_conversations table
    op.execute('ALTER TABLE chat_conversations DROP CONSTRAINT chat_conversations_model_id_fkey')
    op.create_foreign_key('chat_conversations_model_id_fkey', 'chat_conversations', 'models', ['model_id'], ['id'])
    
    # financial_transactions table
    op.execute('ALTER TABLE financial_transactions DROP CONSTRAINT financial_transactions_model_id_fkey')
    op.create_foreign_key('financial_transactions_model_id_fkey', 'financial_transactions', 'models', ['model_id'], ['id'])
    
    # Add missing columns to match the Model class
    op.add_column('models', sa.Column('stage_name', sa.String(255), nullable=True))
    op.add_column('models', sa.Column('real_name', sa.String(255), nullable=True))
    op.add_column('models', sa.Column('platform', sa.String(50), nullable=True, server_default='onlyfans'))
    op.add_column('models', sa.Column('platform_username', sa.String(255), nullable=True))
    op.add_column('models', sa.Column('platform_user_id', sa.String(255), nullable=True))
    op.add_column('models', sa.Column('platform_url', sa.String(500), nullable=True))
    op.add_column('models', sa.Column('status', sa.String(50), nullable=True, server_default='pending'))
    op.add_column('models', sa.Column('verification_status', sa.String(50), nullable=True, server_default='unverified'))
    op.add_column('models', sa.Column('verified_at', sa.String(30), nullable=True))
    op.add_column('models', sa.Column('photo_galleries', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('models', sa.Column('followers_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('models', sa.Column('posts_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('models', sa.Column('likes_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('models', sa.Column('pending_payout', sa.Numeric(12, 2), nullable=True, server_default='0'))
    op.add_column('models', sa.Column('lifetime_earnings', sa.Numeric(12, 2), nullable=True, server_default='0'))
    op.add_column('models', sa.Column('api_access_token', sa.Text(), nullable=True))
    op.add_column('models', sa.Column('api_refresh_token', sa.Text(), nullable=True))
    op.add_column('models', sa.Column('api_token_expires_at', sa.String(30), nullable=True))
    op.add_column('models', sa.Column('webhook_secret', sa.String(255), nullable=True))
    op.add_column('models', sa.Column('auto_sync_enabled', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('models', sa.Column('sync_frequency_hours', sa.Integer(), nullable=True, server_default='6'))
    op.add_column('models', sa.Column('categories', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('models', sa.Column('tags', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('models', sa.Column('content_types', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('models', sa.Column('languages', sa.JSON(), nullable=True, server_default='["en"]'))
    op.add_column('models', sa.Column('timezone', sa.String(50), nullable=True, server_default='UTC'))
    op.add_column('models', sa.Column('working_hours', sa.JSON(), nullable=True, server_default='{}'))
    op.add_column('models', sa.Column('chat_enabled', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('models', sa.Column('auto_reply_enabled', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('models', sa.Column('welcome_message', sa.Text(), nullable=True))
    op.add_column('models', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('models', sa.Column('phone', sa.String(50), nullable=True))
    op.add_column('models', sa.Column('date_of_birth', sa.DateTime(), nullable=True))
    
    # Migrate data from old columns to new ones
    op.execute("""
        UPDATE models 
        SET stage_name = display_name,
            platform_username = onlyfans_username,
            platform_user_id = onlyfans_user_id
        WHERE display_name IS NOT NULL
    """)
    
    # Make stage_name and platform_username required after data migration
    op.alter_column('models', 'stage_name', nullable=False)
    op.alter_column('models', 'platform_username', nullable=False)
    
    # Drop old columns that are no longer needed
    op.drop_column('models', 'onlyfans_username')
    op.drop_column('models', 'onlyfans_user_id')
    op.drop_column('models', 'display_name')
    op.drop_column('models', 'inflow_api_key')
    op.drop_column('models', 'onlyfans_api_key')
    op.drop_column('models', 'subscriber_count')
    op.drop_column('models', 'paying_subscriber_count')
    
    # Add indexes for new columns
    op.create_index('idx_models_stage_name', 'models', ['stage_name'])
    op.create_index('idx_models_platform', 'models', ['platform'])
    op.create_index('idx_models_status', 'models', ['status'])
    op.create_index('idx_models_platform_username', 'models', ['platform', 'platform_username'], unique=True)


def downgrade() -> None:
    """Revert the changes."""
    # Drop new indexes
    op.drop_index('idx_models_platform_username', 'models')
    op.drop_index('idx_models_status', 'models')
    op.drop_index('idx_models_platform', 'models')
    op.drop_index('idx_models_stage_name', 'models')
    
    # Add back old columns
    op.add_column('models', sa.Column('paying_subscriber_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('models', sa.Column('subscriber_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('models', sa.Column('onlyfans_api_key', sa.Text(), nullable=True))
    op.add_column('models', sa.Column('inflow_api_key', sa.Text(), nullable=True))
    op.add_column('models', sa.Column('display_name', sa.String(255), nullable=True))
    op.add_column('models', sa.Column('onlyfans_user_id', sa.String(255), nullable=True))
    op.add_column('models', sa.Column('onlyfans_username', sa.String(255), nullable=False))
    
    # Migrate data back
    op.execute("""
        UPDATE models 
        SET display_name = stage_name,
            onlyfans_username = platform_username,
            onlyfans_user_id = platform_user_id
    """)
    
    # Drop new columns
    op.drop_column('models', 'date_of_birth')
    op.drop_column('models', 'phone')
    op.drop_column('models', 'email')
    op.drop_column('models', 'welcome_message')
    op.drop_column('models', 'auto_reply_enabled')
    op.drop_column('models', 'chat_enabled')
    op.drop_column('models', 'working_hours')
    op.drop_column('models', 'timezone')
    op.drop_column('models', 'languages')
    op.drop_column('models', 'content_types')
    op.drop_column('models', 'tags')
    op.drop_column('models', 'categories')
    op.drop_column('models', 'sync_frequency_hours')
    op.drop_column('models', 'auto_sync_enabled')
    op.drop_column('models', 'webhook_secret')
    op.drop_column('models', 'api_token_expires_at')
    op.drop_column('models', 'api_refresh_token')
    op.drop_column('models', 'api_access_token')
    op.drop_column('models', 'lifetime_earnings')
    op.drop_column('models', 'pending_payout')
    op.drop_column('models', 'likes_count')
    op.drop_column('models', 'posts_count')
    op.drop_column('models', 'followers_count')
    op.drop_column('models', 'photo_galleries')
    op.drop_column('models', 'verified_at')
    op.drop_column('models', 'verification_status')
    op.drop_column('models', 'status')
    op.drop_column('models', 'platform_url')
    op.drop_column('models', 'platform_user_id')
    op.drop_column('models', 'platform_username')
    op.drop_column('models', 'platform')
    op.drop_column('models', 'real_name')
    op.drop_column('models', 'stage_name')
    
    # Update foreign key references back
    op.execute('ALTER TABLE financial_transactions DROP CONSTRAINT financial_transactions_model_id_fkey')
    op.create_foreign_key('financial_transactions_model_id_fkey', 'financial_transactions', 'model_profiles', ['model_id'], ['id'])
    
    op.execute('ALTER TABLE chat_conversations DROP CONSTRAINT chat_conversations_model_id_fkey')
    op.create_foreign_key('chat_conversations_model_id_fkey', 'chat_conversations', 'model_profiles', ['model_id'], ['id'])
    
    op.execute('ALTER TABLE model_chatters DROP CONSTRAINT model_chatters_model_id_fkey')
    op.create_foreign_key('model_chatters_model_id_fkey', 'model_chatters', 'model_profiles', ['model_id'], ['id'])
    
    # Rename constraints back
    op.execute('ALTER TABLE models RENAME CONSTRAINT models_onlyfans_user_id_key TO model_profiles_onlyfans_user_id_key')
    op.execute('ALTER TABLE models RENAME CONSTRAINT models_onlyfans_username_key TO model_profiles_onlyfans_username_key')
    op.execute('ALTER TABLE models RENAME CONSTRAINT models_user_id_fkey TO model_profiles_user_id_fkey')
    op.execute('ALTER TABLE models RENAME CONSTRAINT models_agency_id_fkey TO model_profiles_agency_id_fkey')
    op.execute('ALTER TABLE models RENAME CONSTRAINT models_pkey TO model_profiles_pkey')
    
    # Rename indexes back
    op.execute('ALTER INDEX idx_models_agency_platform RENAME TO idx_model_profiles_agency_platform')
    op.execute('ALTER INDEX idx_models_agency_id_2 RENAME TO idx_model_profiles_agency_id')
    op.execute('ALTER INDEX idx_models_agency_covering RENAME TO idx_model_profiles_agency_covering')
    op.execute('ALTER INDEX idx_models_agency_active RENAME TO idx_model_profiles_agency_active')
    op.execute('ALTER INDEX ix_models_agency_id RENAME TO ix_model_profiles_agency_id')
    
    # Rename the table back
    op.rename_table('models', 'model_profiles')