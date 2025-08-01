"""Add media management tables

Revision ID: 025
Revises: 024
Create Date: 2025-01-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    
    # Check and create mediastatus enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'mediastatus'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE mediastatus AS ENUM ('pending', 'processing', 'ready', 'failed', 'deleted')"))

    # Check and create mediatype enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'mediatype'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE mediatype AS ENUM ('image', 'video', 'audio', 'document', 'other')"))

    # Check and create mediavisibility enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'mediavisibility'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE mediavisibility AS ENUM ('private', 'agency', 'model', 'public')"))
# Create enums
    
    # Create media_folders table
    op.create_table(
        'media_folders',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ),
        sa.ForeignKeyConstraint(['parent_id'], ['media_folders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_media_folders_agency_id', 'media_folders', ['agency_id'])
    op.create_index('ix_media_folders_model_id', 'media_folders', ['model_id'])
    
    # Create media table
    op.create_table(
        'media',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('media_type', postgresql.ENUM('image', 'video', 'audio', 'document', 'other', name='mediatype', create_type=False), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'processing', 'ready', 'failed', 'deleted', name='mediastatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('cdn_url', sa.String(500), nullable=True),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('optimized_versions', sa.JSON(), nullable=True),
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True, server_default='{}'),
        sa.Column('visibility', postgresql.ENUM('private', 'agency', 'model', 'public', name='mediavisibility', create_type=False), nullable=False, server_default='private'),
        sa.Column('password_protected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_nsfw', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('moderation_status', sa.String(50), nullable=True),
        sa.Column('moderation_labels', sa.JSON(), nullable=True),
        sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('alt_text', sa.String(500), nullable=True),
        sa.Column('copyright_info', sa.String(500), nullable=True),
        sa.Column('exif_data', sa.JSON(), nullable=True),
        sa.Column('custom_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['folder_id'], ['media_folders.id'], ),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for media table
    op.create_index('ix_media_file_hash', 'media', ['file_hash'])
    op.create_index('ix_media_media_type', 'media', ['media_type'])
    op.create_index('ix_media_status', 'media', ['status'])
    op.create_index('ix_media_agency_type_created', 'media', ['agency_id', 'media_type', 'created_at'])
    op.create_index('ix_media_model_type_created', 'media', ['model_id', 'media_type', 'created_at'])
    op.create_index('ix_media_folder_created', 'media', ['folder_id', 'created_at'])
    op.create_index('ix_media_status_created', 'media', ['status', 'created_at'])
    
    # Create media_shares table
    op.create_table(
        'media_shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('media_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('share_token', sa.String(100), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('max_views', sa.Integer(), nullable=True),
        sa.Column('current_views', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('password_protected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('allow_download', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('allow_embed', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['media_id'], ['media.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_media_shares_share_token', 'media_shares', ['share_token'], unique=True)
    
    # Add media storage quota to agencies table
    op.add_column('agencies', sa.Column('storage_quota_gb', sa.Integer(), nullable=False, server_default='100'))
    op.add_column('agencies', sa.Column('storage_used_bytes', sa.BigInteger(), nullable=False, server_default='0'))


def downgrade() -> None:
    # Remove columns from agencies
    op.drop_column('agencies', 'storage_used_bytes')
    op.drop_column('agencies', 'storage_quota_gb')
    
    # Drop tables
    op.drop_table('media_shares')
    op.drop_table('media')
    op.drop_table('media_folders')
    
    # Drop enums
    op.execute('DROP TYPE mediavisibility')
    op.execute('DROP TYPE mediastatus')
    op.execute('DROP TYPE mediatype')