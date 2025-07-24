"""add whitelabel tables

Revision ID: 007
Revises: 006
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007'
down_revision = 'ab6eda48e947'
branch_labels = None
depends_on = None


def upgrade():
    # Create theme_configurations table
    op.create_table('theme_configurations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('default_mode', sa.String(10), nullable=True),
        sa.Column('allow_user_preference', sa.Boolean(), nullable=True),
        sa.Column('light_theme', sa.JSON(), nullable=True),
        sa.Column('dark_theme', sa.JSON(), nullable=True),
        sa.Column('custom_css', sa.Text(), nullable=True),
        sa.Column('font_family', sa.String(100), nullable=True),
        sa.Column('font_size_base', sa.String(10), nullable=True),
        sa.Column('layout_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agency_id')
    )
    op.create_index('idx_theme_configuration_agency', 'theme_configurations', ['agency_id'], unique=False)

    # Create branding_assets table
    op.create_table('branding_assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('asset_type', sa.String(50), nullable=False),
        sa.Column('file_name', sa.String(255), nullable=False),
        sa.Column('file_url', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['model_id'], ['model_profiles.id'], ),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_branding_asset_agency', 'branding_assets', ['agency_id'], unique=False)
    op.create_index('idx_branding_asset_model', 'branding_assets', ['model_id'], unique=False)
    op.create_index('idx_branding_asset_type', 'branding_assets', ['asset_type'], unique=False)
    op.create_index('idx_branding_asset_unique_active', 'branding_assets', 
                    ['agency_id', 'model_id', 'asset_type', 'is_active'], 
                    unique=True, postgresql_where=sa.text('is_active = true'))

    # Create agency_profiles table
    op.create_table('agency_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('tagline', sa.String(200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('support_email', sa.String(255), nullable=True),
        sa.Column('support_phone', sa.String(50), nullable=True),
        sa.Column('website_url', sa.String(500), nullable=True),
        sa.Column('social_links', sa.JSON(), nullable=True),
        sa.Column('legal_name', sa.String(200), nullable=True),
        sa.Column('tax_id', sa.String(50), nullable=True),
        sa.Column('address', sa.JSON(), nullable=True),
        sa.Column('brand_guidelines', sa.Text(), nullable=True),
        sa.Column('custom_domain', sa.String(255), nullable=True),
        sa.Column('custom_domain_verified', sa.Boolean(), nullable=True),
        sa.Column('from_email_name', sa.String(100), nullable=True),
        sa.Column('from_email_address', sa.String(255), nullable=True),
        sa.Column('reply_to_email', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agency_id')
    )
    op.create_index('idx_agency_profile_agency', 'agency_profiles', ['agency_id'], unique=False)

    # Create model_branding table
    op.create_table('model_branding',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('theme_override', sa.JSON(), nullable=True),
        sa.Column('use_agency_theme', sa.Boolean(), nullable=True),
        sa.Column('content_tags', sa.JSON(), nullable=True),
        sa.Column('links', sa.JSON(), nullable=True),
        sa.Column('watermark_enabled', sa.Boolean(), nullable=True),
        sa.Column('watermark_text', sa.String(100), nullable=True),
        sa.Column('watermark_position', sa.String(20), nullable=True),
        sa.Column('watermark_opacity', sa.Integer(), nullable=True),
        sa.Column('auto_welcome_message', sa.Text(), nullable=True),
        sa.Column('tip_thank_you_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['model_profiles.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_id')
    )
    op.create_index('idx_model_branding_model', 'model_branding', ['model_id'], unique=False)

    # Create email_templates table
    op.create_table('email_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_type', sa.String(50), nullable=False),
        sa.Column('language', sa.String(10), nullable=True),
        sa.Column('subject', sa.String(200), nullable=False),
        sa.Column('html_body', sa.Text(), nullable=False),
        sa.Column('text_body', sa.Text(), nullable=True),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('test_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_email_template_agency', 'email_templates', ['agency_id'], unique=False)
    op.create_index('idx_email_template_type', 'email_templates', ['template_type'], unique=False)
    op.create_index('idx_email_template_language', 'email_templates', ['language'], unique=False)
    op.create_index('idx_email_template_unique_active', 'email_templates', 
                    ['agency_id', 'template_type', 'language', 'is_active'], 
                    unique=True, postgresql_where=sa.text('is_active = true'))

    # Create theme_presets table
    op.create_table('theme_presets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('preview_url', sa.String(500), nullable=True),
        sa.Column('light_theme', sa.JSON(), nullable=False),
        sa.Column('dark_theme', sa.JSON(), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('is_premium', sa.Boolean(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_theme_preset_name', 'theme_presets', ['name'], unique=False)
    op.create_index('idx_theme_preset_category', 'theme_presets', ['category'], unique=False)


def downgrade():
    op.drop_index('idx_theme_preset_category', table_name='theme_presets')
    op.drop_index('idx_theme_preset_name', table_name='theme_presets')
    op.drop_table('theme_presets')
    
    op.drop_index('idx_email_template_unique_active', table_name='email_templates')
    op.drop_index('idx_email_template_language', table_name='email_templates')
    op.drop_index('idx_email_template_type', table_name='email_templates')
    op.drop_index('idx_email_template_agency', table_name='email_templates')
    op.drop_table('email_templates')
    
    op.drop_index('idx_model_branding_model', table_name='model_branding')
    op.drop_table('model_branding')
    
    op.drop_index('idx_agency_profile_agency', table_name='agency_profiles')
    op.drop_table('agency_profiles')
    
    op.drop_index('idx_branding_asset_unique_active', table_name='branding_assets')
    op.drop_index('idx_branding_asset_type', table_name='branding_assets')
    op.drop_index('idx_branding_asset_model', table_name='branding_assets')
    op.drop_index('idx_branding_asset_agency', table_name='branding_assets')
    op.drop_table('branding_assets')
    
    op.drop_index('idx_theme_configuration_agency', table_name='theme_configurations')
    op.drop_table('theme_configurations')