"""Add advanced reporting tables

Revision ID: 014
Revises: 013
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add reporting tables."""
    
    # Check and create reportformat enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'reportformat'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE reportformat AS ENUM ('pdf', 'excel', 'csv', 'json', 'html')"))

    # Check and create reportstatus enum
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'reportstatus'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE reportstatus AS ENUM ('draft', 'pending', 'generating', 'completed', 'failed', 'scheduled')"))

    # Check and create reporttype enum
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'reporttype'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE reporttype AS ENUM ('revenue', 'user_activity', 'model_performance', 'transaction', 'payout', 'engagement', 'conversion', 'custom', 'executive')"))
    
    # Create reports table
    op.create_table('reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', postgresql.ENUM('revenue', 'user_activity', 'model_performance', 'transaction', 'payout', 'engagement', 'conversion', 'custom', 'executive', name='reporttype', create_type=False), nullable=False),
        sa.Column('query_config', sa.JSON(), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('columns', sa.JSON(), nullable=True),
        sa.Column('grouping', sa.JSON(), nullable=True),
        sa.Column('sorting', sa.JSON(), nullable=True),
        sa.Column('aggregations', sa.JSON(), nullable=True),
        sa.Column('chart_config', sa.JSON(), nullable=True),
        sa.Column('layout_config', sa.JSON(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('is_template', sa.Boolean(), nullable=True),
        sa.Column('template_category', sa.String(length=50), nullable=True),
        sa.Column('cache_duration_minutes', sa.Integer(), nullable=True),
        sa.Column('estimated_runtime_seconds', sa.Integer(), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create report_schedules table
    op.create_table('report_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schedule_name', sa.String(length=100), nullable=False),
        sa.Column('cron_expression', sa.String(length=100), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=True),
        sa.Column('format', postgresql.ENUM('pdf', 'excel', 'csv', 'json', 'html', name='reportformat', create_type=False), nullable=True),
        sa.Column('recipients', sa.JSON(), nullable=True),
        sa.Column('delivery_method', sa.String(length=50), nullable=True),
        sa.Column('delivery_config', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create report_executions table
    op.create_table('report_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('report_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('schedule_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', postgresql.ENUM('draft', 'pending', 'generating', 'completed', 'failed', 'scheduled', name='reportstatus', create_type=False), nullable=True),
        sa.Column('format', postgresql.ENUM('pdf', 'excel', 'csv', 'json', 'html', name='reportformat', create_type=False), nullable=True),
        sa.Column('parameters', sa.JSON(), nullable=True),
        sa.Column('filters_applied', sa.JSON(), nullable=True),
        sa.Column('query_executed', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('runtime_seconds', sa.Float(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('requested_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ),
        sa.ForeignKeyConstraint(['requested_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['schedule_id'], ['report_schedules.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_reports_type', 'reports', ['report_type'], unique=False)
    op.create_index('idx_reports_agency', 'reports', ['agency_id'], unique=False)
    op.create_index('idx_reports_created_by', 'reports', ['created_by_id'], unique=False)
    op.create_index('idx_reports_public', 'reports', ['is_public'], unique=False)
    op.create_index('idx_reports_template', 'reports', ['is_template'], unique=False)
    
    op.create_index('idx_report_schedules_report', 'report_schedules', ['report_id'], unique=False)
    op.create_index('idx_report_schedules_active', 'report_schedules', ['is_active'], unique=False)
    op.create_index('idx_report_schedules_next_run', 'report_schedules', ['next_run_at'], unique=False)
    
    op.create_index('idx_report_executions_report', 'report_executions', ['report_id'], unique=False)
    op.create_index('idx_report_executions_status', 'report_executions', ['status'], unique=False)
    op.create_index('idx_report_executions_created', 'report_executions', ['created_at'], unique=False)
    
    # Set default values
    op.execute("UPDATE reports SET is_public = false WHERE is_public IS NULL")
    op.execute("UPDATE reports SET is_template = false WHERE is_template IS NULL")
    op.execute("UPDATE reports SET run_count = 0 WHERE run_count IS NULL")
    op.execute("UPDATE report_schedules SET timezone = 'UTC' WHERE timezone IS NULL")
    op.execute("UPDATE report_schedules SET format = 'pdf' WHERE format IS NULL")
    op.execute("UPDATE report_schedules SET delivery_method = 'email' WHERE delivery_method IS NULL")
    op.execute("UPDATE report_schedules SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE report_schedules SET run_count = 0 WHERE run_count IS NULL")
    op.execute("UPDATE report_schedules SET failure_count = 0 WHERE failure_count IS NULL")
    op.execute("UPDATE report_executions SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE report_executions SET format = 'pdf' WHERE format IS NULL")


def downgrade() -> None:
    """Remove reporting tables."""
    
    # Drop indexes
    op.drop_index('idx_report_executions_created', table_name='report_executions')
    op.drop_index('idx_report_executions_status', table_name='report_executions')
    op.drop_index('idx_report_executions_report', table_name='report_executions')
    
    op.drop_index('idx_report_schedules_next_run', table_name='report_schedules')
    op.drop_index('idx_report_schedules_active', table_name='report_schedules')
    op.drop_index('idx_report_schedules_report', table_name='report_schedules')
    
    op.drop_index('idx_reports_template', table_name='reports')
    op.drop_index('idx_reports_public', table_name='reports')
    op.drop_index('idx_reports_created_by', table_name='reports')
    op.drop_index('idx_reports_agency', table_name='reports')
    op.drop_index('idx_reports_type', table_name='reports')
    
    # Drop tables
    op.drop_table('report_executions')
    op.drop_table('report_schedules')
    op.drop_table('reports')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS reportstatus")
    op.execute("DROP TYPE IF EXISTS reportformat")
    op.execute("DROP TYPE IF EXISTS reporttype")