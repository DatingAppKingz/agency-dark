"""
Add analytics dashboard tables

Revision ID: 015
Revises: 014
Create Date: 2025-01-27 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade():
    # Create dashboard_widgets table
    op.create_table(
        'dashboard_widgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('widget_type', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        
        # Configuration
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('position', sa.JSON(), nullable=False),
        sa.Column('size', sa.JSON(), nullable=False),
        
        # Visibility
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('visibility', sa.String(), nullable=False, default='private'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create dashboard_layouts table
    op.create_table(
        'dashboard_layouts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        
        # Configuration
        sa.Column('widgets', sa.JSON(), nullable=False),
        sa.Column('grid_size', sa.JSON(), nullable=False, default={'cols': 12, 'rows': 8}),
        
        # Settings
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_shared', sa.Boolean(), nullable=False, default=False),
        sa.Column('theme', sa.String(), nullable=False, default='light'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create dashboard_layout_widgets association table
    op.create_table(
        'dashboard_layout_widgets',
        sa.Column('layout_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('widget_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.JSON(), nullable=False),
        sa.Column('size', sa.JSON(), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False, default=0),
        
        sa.PrimaryKeyConstraint('layout_id', 'widget_id'),
        sa.ForeignKeyConstraint(['layout_id'], ['dashboard_layouts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['widget_id'], ['dashboard_widgets.id'], ondelete='CASCADE')
    )
    
    # Create dashboard_filters table
    op.create_table(
        'dashboard_filters',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        
        # Filter configuration
        sa.Column('filters', sa.JSON(), nullable=False),
        sa.Column('is_global', sa.Boolean(), nullable=False, default=False),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create dashboard_snapshots table
    op.create_table(
        'dashboard_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('layout_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        
        # Snapshot data
        sa.Column('snapshot_data', sa.JSON(), nullable=False),
        sa.Column('snapshot_date', sa.DateTime(), nullable=False),
        
        # Metadata
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['layout_id'], ['dashboard_layouts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )
    
    # Add analytics table if it doesn't exist
    op.create_table(
        'analytics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('fan_id', postgresql.UUID(as_uuid=True), nullable=True),
        
        # Event data
        sa.Column('metric_type', sa.String(50), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('value', sa.Numeric(12, 2), nullable=False, default=0),
        sa.Column('data', sa.JSON(), nullable=False, default={}),
        
        # Timestamps
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['model_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fan_id'], ['fans.id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index('idx_dashboard_widgets_agency', 'dashboard_widgets', ['agency_id'])
    op.create_index('idx_dashboard_widgets_type', 'dashboard_widgets', ['widget_type'])
    
    op.create_index('idx_dashboard_layouts_user', 'dashboard_layouts', ['user_id'])
    op.create_index('idx_dashboard_layouts_agency', 'dashboard_layouts', ['agency_id'])
    
    op.create_index('idx_dashboard_filters_user', 'dashboard_filters', ['user_id'])
    op.create_index('idx_dashboard_filters_agency', 'dashboard_filters', ['agency_id'])
    
    op.create_index('idx_analytics_agency_date', 'analytics', ['agency_id', 'date'])
    op.create_index('idx_analytics_model_date', 'analytics', ['model_id', 'date'])
    op.create_index('idx_analytics_metric_type', 'analytics', ['metric_type'])
    op.create_index('idx_analytics_event_type', 'analytics', ['event_type'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_analytics_event_type', table_name='analytics')
    op.drop_index('idx_analytics_metric_type', table_name='analytics')
    op.drop_index('idx_analytics_model_date', table_name='analytics')
    op.drop_index('idx_analytics_agency_date', table_name='analytics')
    
    op.drop_index('idx_dashboard_filters_agency', table_name='dashboard_filters')
    op.drop_index('idx_dashboard_filters_user', table_name='dashboard_filters')
    
    op.drop_index('idx_dashboard_layouts_agency', table_name='dashboard_layouts')
    op.drop_index('idx_dashboard_layouts_user', table_name='dashboard_layouts')
    
    op.drop_index('idx_dashboard_widgets_type', table_name='dashboard_widgets')
    op.drop_index('idx_dashboard_widgets_agency', table_name='dashboard_widgets')
    
    # Drop tables
    op.drop_table('analytics')
    op.drop_table('dashboard_snapshots')
    op.drop_table('dashboard_filters')
    op.drop_table('dashboard_layout_widgets')
    op.drop_table('dashboard_layouts')
    op.drop_table('dashboard_widgets')
