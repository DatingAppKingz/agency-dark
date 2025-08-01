"""Add translation tables

Revision ID: add_translation_tables
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_translation_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create translations table
    op.create_table('translations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=500), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('context', sa.String(length=100), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('verified_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['verified_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', 'language', 'context', name='uq_translation_key_lang_context')
    )
    
    # Create indices
    op.create_index('ix_translations_key', 'translations', ['key'])
    op.create_index('ix_translations_language', 'translations', ['language'])
    op.create_index('ix_translations_context', 'translations', ['context'])
    op.create_index('ix_translations_key_language', 'translations', ['key', 'language'])
    
    # Create model_translations table
    op.create_table('model_translations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('model_id', sa.String(length=100), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('is_machine_translated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_name', 'model_id', 'field_name', 'language', name='uq_model_translation')
    )
    
    # Create indices
    op.create_index('ix_model_translations_model', 'model_translations', ['model_name', 'model_id'])
    op.create_index('ix_model_translations_language', 'model_translations', ['language'])
    
    # Create translation_requests table
    op.create_table('translation_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('key', sa.String(length=500), nullable=False),
        sa.Column('source_language', sa.String(length=10), nullable=False),
        sa.Column('target_language', sa.String(length=10), nullable=False),
        sa.Column('source_text', sa.Text(), nullable=False),
        sa.Column('translated_text', sa.Text(), nullable=True),
        sa.Column('context', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='normal'),
        sa.Column('requested_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('translator_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agency_id', sa.Integer(), nullable=False),
        sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['translator_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indices
    op.create_index('ix_translation_requests_status', 'translation_requests', ['status'])
    op.create_index('ix_translation_requests_priority', 'translation_requests', ['priority'])
    op.create_index('ix_translation_requests_agency', 'translation_requests', ['agency_id'])
    
    # Create language_preferences table
    op.create_table('language_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('primary_language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('fallback_languages', postgresql.ARRAY(sa.String(length=10)), nullable=True),
        sa.Column('auto_translate', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('show_original', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('date_format', sa.String(length=50), nullable=True),
        sa.Column('time_format', sa.String(length=50), nullable=True),
        sa.Column('number_format', sa.String(length=50), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='UTC'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_language_preference_user')
    )
    
    # Add language column to users table if not exists
    op.add_column('users', sa.Column('language', sa.String(length=10), nullable=False, server_default='en'))


def downgrade() -> None:
    # Drop language column from users
    op.drop_column('users', 'language')
    
    # Drop tables
    op.drop_table('language_preferences')
    op.drop_table('translation_requests')
    op.drop_table('model_translations')
    op.drop_table('translations')