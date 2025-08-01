"""Add bulk operations tables

Revision ID: 012
Revises: 011
Create Date: 2025-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add bulk operations tables."""
    
    
    # Check and create bulkoperationstatus enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'bulkoperationstatus'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE bulkoperationstatus AS ENUM ('pending', 'validating', 'scheduled', 'processing', 'completed', 'failed', 'cancelled', 'rolled_back')"))

    # Check and create bulkoperationtype enum
    connection = op.get_bind()
    result = connection.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'bulkoperationtype'"))
    if not result.fetchone():
        connection.execute(sa.text("CREATE TYPE bulkoperationtype AS ENUM ('user_update', 'user_delete', 'user_activate', 'user_deactivate', 'model_update', 'model_assign', 'transaction_export', 'transaction_reconcile', 'payout_schedule', 'payout_cancel', 'message_send', 'message_delete', 'analytics_export', 'data_import', 'data_export')"))
    
    # Create bulk_operations table
    op.create_table('bulk_operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('operation_type', postgresql.ENUM('user_update', 'user_delete', 'user_activate', 'user_deactivate', 'model_update', 'model_assign', 'transaction_export', 'transaction_reconcile', 'payout_schedule', 'payout_cancel', 'message_send', 'message_delete', 'analytics_export', 'data_import', 'data_export', name='bulkoperationtype', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'validating', 'scheduled', 'processing', 'completed', 'failed', 'cancelled', 'rolled_back', name='bulkoperationstatus', create_type=False), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_ids', sa.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('total_count', sa.Integer(), nullable=False),
        sa.Column('processed_count', sa.Integer(), nullable=True),
        sa.Column('success_count', sa.Integer(), nullable=True),
        sa.Column('failed_count', sa.Integer(), nullable=True),
        sa.Column('operation_params', sa.JSON(), nullable=True),
        sa.Column('validation_rules', sa.JSON(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('progress_percentage', sa.Integer(), nullable=True),
        sa.Column('current_batch', sa.Integer(), nullable=True),
        sa.Column('total_batches', sa.Integer(), nullable=True),
        sa.Column('batch_size', sa.Integer(), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('can_rollback', sa.Boolean(), nullable=True),
        sa.Column('rollback_data', sa.JSON(), nullable=True),
        sa.Column('max_entities', sa.Integer(), nullable=True),
        sa.Column('max_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for bulk_operations
    op.create_index('idx_bulk_operation_status', 'bulk_operations', ['status'], unique=False)
    op.create_index('idx_bulk_operation_type', 'bulk_operations', ['operation_type'], unique=False)
    op.create_index('idx_bulk_operation_agency', 'bulk_operations', ['agency_id'], unique=False)
    op.create_index('idx_bulk_operation_scheduled', 'bulk_operations', ['scheduled_at'], unique=False)
    op.create_index('idx_bulk_operation_created', 'bulk_operations', ['created_at'], unique=False)
    
    # Create bulk_operation_items table
    op.create_table('bulk_operation_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('operation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('original_data', sa.JSON(), nullable=True),
        sa.Column('new_data', sa.JSON(), nullable=True),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('validation_passed', sa.Boolean(), nullable=True),
        sa.Column('validation_errors', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['operation_id'], ['bulk_operations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for bulk_operation_items
    op.create_index('idx_bulk_item_operation', 'bulk_operation_items', ['operation_id'], unique=False)
    op.create_index('idx_bulk_item_entity', 'bulk_operation_items', ['entity_id'], unique=False)
    op.create_index('idx_bulk_item_status', 'bulk_operation_items', ['status'], unique=False)
    
    # Create bulk_operation_logs table
    op.create_table('bulk_operation_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('operation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('log_level', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('batch_number', sa.Integer(), nullable=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['operation_id'], ['bulk_operations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for bulk_operation_logs
    op.create_index('idx_bulk_log_operation', 'bulk_operation_logs', ['operation_id'], unique=False)
    op.create_index('idx_bulk_log_timestamp', 'bulk_operation_logs', ['timestamp'], unique=False)
    op.create_index('idx_bulk_log_level', 'bulk_operation_logs', ['log_level'], unique=False)
    
    # Create bulk_operation_templates table
    op.create_table('bulk_operation_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('operation_type', postgresql.ENUM('user_update', 'user_delete', 'user_activate', 'user_deactivate', 'model_update', 'model_assign', 'transaction_export', 'transaction_reconcile', 'payout_schedule', 'payout_cancel', 'message_send', 'message_delete', 'analytics_export', 'data_import', 'data_export', name='bulkoperationtype', create_type=False), nullable=False),
        sa.Column('default_params', sa.JSON(), nullable=False),
        sa.Column('validation_rules', sa.JSON(), nullable=True),
        sa.Column('selection_criteria', sa.JSON(), nullable=True),
        sa.Column('required_role', sa.String(length=50), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for bulk_operation_templates
    op.create_index('idx_bulk_template_name', 'bulk_operation_templates', ['name'], unique=False)
    op.create_index('idx_bulk_template_type', 'bulk_operation_templates', ['operation_type'], unique=False)
    op.create_index('idx_bulk_template_agency', 'bulk_operation_templates', ['agency_id'], unique=False)
    
    # Create bulk_operation_schedules table
    op.create_table('bulk_operation_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('cron_expression', sa.String(length=100), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=True),
        sa.Column('entity_selection', sa.JSON(), nullable=True),
        sa.Column('max_entities_per_run', sa.Integer(), nullable=True),
        sa.Column('notify_on_completion', sa.Boolean(), nullable=True),
        sa.Column('notify_on_failure', sa.Boolean(), nullable=True),
        sa.Column('notification_emails', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['bulk_operation_templates.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for bulk_operation_schedules
    op.create_index('idx_bulk_schedule_active', 'bulk_operation_schedules', ['is_active'], unique=False)
    op.create_index('idx_bulk_schedule_next_run', 'bulk_operation_schedules', ['next_run_at'], unique=False)
    op.create_index('idx_bulk_schedule_agency', 'bulk_operation_schedules', ['agency_id'], unique=False)
    
    # Create bulk_operation_limits table
    op.create_table('bulk_operation_limits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('operation_type', postgresql.ENUM('user_update', 'user_delete', 'user_activate', 'user_deactivate', 'model_update', 'model_assign', 'transaction_export', 'transaction_reconcile', 'payout_schedule', 'payout_cancel', 'message_send', 'message_delete', 'analytics_export', 'data_import', 'data_export', name='bulkoperationtype', create_type=False), nullable=True),
        sa.Column('max_entities_per_operation', sa.Integer(), nullable=True),
        sa.Column('max_operations_per_day', sa.Integer(), nullable=True),
        sa.Column('max_operations_per_hour', sa.Integer(), nullable=True),
        sa.Column('max_concurrent_operations', sa.Integer(), nullable=True),
        sa.Column('operations_today', sa.Integer(), nullable=True),
        sa.Column('operations_this_hour', sa.Integer(), nullable=True),
        sa.Column('last_reset_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_reset_hour', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_unlimited', sa.Boolean(), nullable=True),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for bulk_operation_limits
    op.create_index('idx_bulk_limit_agency', 'bulk_operation_limits', ['agency_id'], unique=False)
    op.create_index('idx_bulk_limit_user', 'bulk_operation_limits', ['user_id'], unique=False)
    op.create_index('idx_bulk_limit_type', 'bulk_operation_limits', ['operation_type'], unique=False)
    
    # Set default values
    op.execute("UPDATE bulk_operations SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE bulk_operations SET processed_count = 0 WHERE processed_count IS NULL")
    op.execute("UPDATE bulk_operations SET success_count = 0 WHERE success_count IS NULL")
    op.execute("UPDATE bulk_operations SET failed_count = 0 WHERE failed_count IS NULL")
    op.execute("UPDATE bulk_operations SET progress_percentage = 0 WHERE progress_percentage IS NULL")
    op.execute("UPDATE bulk_operations SET current_batch = 0 WHERE current_batch IS NULL")
    op.execute("UPDATE bulk_operations SET total_batches = 1 WHERE total_batches IS NULL")
    op.execute("UPDATE bulk_operations SET batch_size = 100 WHERE batch_size IS NULL")
    op.execute("UPDATE bulk_operations SET can_rollback = true WHERE can_rollback IS NULL")
    op.execute("UPDATE bulk_operations SET priority = 0 WHERE priority IS NULL")
    op.execute("UPDATE bulk_operation_items SET status = 'pending' WHERE status IS NULL")
    op.execute("UPDATE bulk_operation_templates SET is_system = false WHERE is_system IS NULL")
    op.execute("UPDATE bulk_operation_templates SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE bulk_operation_templates SET usage_count = 0 WHERE usage_count IS NULL")
    op.execute("UPDATE bulk_operation_schedules SET timezone = 'UTC' WHERE timezone IS NULL")
    op.execute("UPDATE bulk_operation_schedules SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE bulk_operation_schedules SET run_count = 0 WHERE run_count IS NULL")
    op.execute("UPDATE bulk_operation_schedules SET notify_on_completion = true WHERE notify_on_completion IS NULL")
    op.execute("UPDATE bulk_operation_schedules SET notify_on_failure = true WHERE notify_on_failure IS NULL")
    op.execute("UPDATE bulk_operation_limits SET max_entities_per_operation = 1000 WHERE max_entities_per_operation IS NULL")
    op.execute("UPDATE bulk_operation_limits SET max_operations_per_day = 100 WHERE max_operations_per_day IS NULL")
    op.execute("UPDATE bulk_operation_limits SET max_operations_per_hour = 20 WHERE max_operations_per_hour IS NULL")
    op.execute("UPDATE bulk_operation_limits SET max_concurrent_operations = 3 WHERE max_concurrent_operations IS NULL")
    op.execute("UPDATE bulk_operation_limits SET operations_today = 0 WHERE operations_today IS NULL")
    op.execute("UPDATE bulk_operation_limits SET operations_this_hour = 0 WHERE operations_this_hour IS NULL")
    op.execute("UPDATE bulk_operation_limits SET is_unlimited = false WHERE is_unlimited IS NULL")
    
    # Insert default templates
    op.execute("""
        INSERT INTO bulk_operation_templates (id, name, description, operation_type, 
            default_params, is_system, is_active)
        VALUES
        -- User management templates
        (gen_random_uuid(), 'Bulk Activate Users', 'Activate multiple users at once', 
            'user_activate', '{}', true, true),
        (gen_random_uuid(), 'Bulk Deactivate Users', 'Deactivate multiple users at once', 
            'user_deactivate', '{}', true, true),
        (gen_random_uuid(), 'Bulk Update User Roles', 'Update roles for multiple users', 
            'user_update', '{"role": "agency_member"}', true, true),
        
        -- Model management templates
        (gen_random_uuid(), 'Bulk Update Model Commission', 'Update commission rates for models', 
            'model_update', '{"commission_rate": 0.2}', true, true),
        (gen_random_uuid(), 'Bulk Assign Models', 'Assign models to chatters', 
            'model_assign', '{"assigned_users": []}', true, true),
        
        -- Transaction templates
        (gen_random_uuid(), 'Export Transactions', 'Export transactions to CSV', 
            'transaction_export', '{"format": "csv", "include_headers": true}', true, true),
        (gen_random_uuid(), 'Reconcile Transactions', 'Mark transactions as reconciled', 
            'transaction_reconcile', '{}', true, true),
        
        -- Payout templates
        (gen_random_uuid(), 'Schedule Payouts', 'Schedule pending payouts', 
            'payout_schedule', '{"scheduled_date": null}', true, true),
        (gen_random_uuid(), 'Cancel Payouts', 'Cancel pending or scheduled payouts', 
            'payout_cancel', '{"reason": "Bulk cancellation"}', true, true),
        
        -- Communication templates
        (gen_random_uuid(), 'Send Bulk Message', 'Send message to multiple recipients', 
            'message_send', '{"message": "", "channel": "email"}', true, true),
        
        -- Analytics templates
        (gen_random_uuid(), 'Export Analytics Data', 'Export analytics for multiple entities', 
            'analytics_export', '{"type": "full", "format": "csv"}', true, true)
    """)


def downgrade() -> None:
    """Remove bulk operations tables."""
    
    # Drop indexes
    op.drop_index('idx_bulk_limit_type', table_name='bulk_operation_limits')
    op.drop_index('idx_bulk_limit_user', table_name='bulk_operation_limits')
    op.drop_index('idx_bulk_limit_agency', table_name='bulk_operation_limits')
    op.drop_index('idx_bulk_schedule_agency', table_name='bulk_operation_schedules')
    op.drop_index('idx_bulk_schedule_next_run', table_name='bulk_operation_schedules')
    op.drop_index('idx_bulk_schedule_active', table_name='bulk_operation_schedules')
    op.drop_index('idx_bulk_template_agency', table_name='bulk_operation_templates')
    op.drop_index('idx_bulk_template_type', table_name='bulk_operation_templates')
    op.drop_index('idx_bulk_template_name', table_name='bulk_operation_templates')
    op.drop_index('idx_bulk_log_level', table_name='bulk_operation_logs')
    op.drop_index('idx_bulk_log_timestamp', table_name='bulk_operation_logs')
    op.drop_index('idx_bulk_log_operation', table_name='bulk_operation_logs')
    op.drop_index('idx_bulk_item_status', table_name='bulk_operation_items')
    op.drop_index('idx_bulk_item_entity', table_name='bulk_operation_items')
    op.drop_index('idx_bulk_item_operation', table_name='bulk_operation_items')
    op.drop_index('idx_bulk_operation_created', table_name='bulk_operations')
    op.drop_index('idx_bulk_operation_scheduled', table_name='bulk_operations')
    op.drop_index('idx_bulk_operation_agency', table_name='bulk_operations')
    op.drop_index('idx_bulk_operation_type', table_name='bulk_operations')
    op.drop_index('idx_bulk_operation_status', table_name='bulk_operations')
    
    # Drop tables
    op.drop_table('bulk_operation_limits')
    op.drop_table('bulk_operation_schedules')
    op.drop_table('bulk_operation_templates')
    op.drop_table('bulk_operation_logs')
    op.drop_table('bulk_operation_items')
    op.drop_table('bulk_operations')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS bulkoperationstatus')
    op.execute('DROP TYPE IF EXISTS bulkoperationtype')