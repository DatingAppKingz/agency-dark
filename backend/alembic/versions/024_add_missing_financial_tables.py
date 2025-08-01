"""Add missing financial tables - invoices and related tables

Revision ID: 024_add_missing_financial_tables
Revises: 023_rename_model_profiles_to_models
Create Date: 2025-08-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '024_add_missing_financial_tables'
down_revision = '023_rename_model_profiles_to_models'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add missing financial tables."""
    
    # Create invoices table
    op.create_table('invoices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agency_id', sa.Integer(), nullable=False),
        sa.Column('invoice_number', sa.String(50), nullable=False),
        sa.Column('invoice_date', sa.String(30), nullable=False),
        sa.Column('due_date', sa.String(30), nullable=False),
        sa.Column('period_start', sa.String(30), nullable=False),
        sa.Column('period_end', sa.String(30), nullable=False),
        sa.Column('subtotal', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('tax_rate', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('tax_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('paid_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('paid_at', sa.String(30), nullable=True),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('payment_reference', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('line_items', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invoice_number')
    )
    
    # Create indexes for invoices
    op.create_index('idx_invoices_agency_id', 'invoices', ['agency_id'])
    op.create_index('idx_invoices_invoice_date', 'invoices', ['invoice_date'])
    op.create_index('idx_invoices_due_date', 'invoices', ['due_date'])
    op.create_index('idx_invoices_status', 'invoices', ['status'])
    op.create_index('idx_invoices_invoice_number', 'invoices', ['invoice_number'])
    
    # Create commission_rules table if it doesn't exist
    op.create_table('commission_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agency_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(50), nullable=False, server_default='tiered'),  # 'tiered', 'flat', 'custom'
        sa.Column('base_rate', sa.Numeric(5, 2), nullable=False, server_default='20'),
        sa.Column('tiers', postgresql.JSONB(), nullable=True),
        sa.Column('conditions', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for commission_rules
    op.create_index('idx_commission_rules_agency_id', 'commission_rules', ['agency_id'])
    op.create_index('idx_commission_rules_is_active', 'commission_rules', ['is_active'])
    op.create_index('idx_commission_rules_priority', 'commission_rules', ['priority'])
    
    # Create earnings table (for model earnings tracking)
    op.create_table('earnings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('agency_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.String(30), nullable=False),
        sa.Column('period_end', sa.String(30), nullable=False),
        sa.Column('gross_revenue', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('platform_fees', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('net_revenue', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('commission_rate', sa.Numeric(5, 2), nullable=False),
        sa.Column('commission_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('model_earnings', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('transaction_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('subscriber_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),  # 'pending', 'calculated', 'approved', 'paid'
        sa.Column('approved_at', sa.String(30), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for earnings
    op.create_index('idx_earnings_model_id', 'earnings', ['model_id'])
    op.create_index('idx_earnings_agency_id', 'earnings', ['agency_id'])
    op.create_index('idx_earnings_period', 'earnings', ['period_start', 'period_end'])
    op.create_index('idx_earnings_status', 'earnings', ['status'])
    op.create_index('idx_earnings_model_period', 'earnings', ['model_id', 'period_start', 'period_end'], unique=True)
    
    # Create payment_methods table
    op.create_table('payment_methods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('agency_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.String(50), nullable=False),  # 'bank_account', 'paypal', 'stripe', 'crypto'
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('account_holder_name', sa.String(255), nullable=True),
        sa.Column('account_details', postgresql.JSONB(), nullable=False),  # Encrypted in production
        sa.Column('verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('verified_at', sa.String(30), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for payment_methods
    op.create_index('idx_payment_methods_user_id', 'payment_methods', ['user_id'])
    op.create_index('idx_payment_methods_agency_id', 'payment_methods', ['agency_id'])
    op.create_index('idx_payment_methods_type', 'payment_methods', ['type'])
    op.create_index('idx_payment_methods_is_default', 'payment_methods', ['is_default'])


def downgrade() -> None:
    """Drop the tables created in upgrade."""
    # Drop tables in reverse order
    op.drop_table('payment_methods')
    op.drop_table('earnings')
    op.drop_table('commission_rules')
    op.drop_table('invoices')