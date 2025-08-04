"""Add financial system improvements

Revision ID: 010_add_financial_improvements
Revises: 009_add_model_approval_fields
Create Date: 2024-01-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010_add_financial_improvements'
down_revision = '009_add_model_approval_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add paid_date to earnings table
    op.add_column('earnings', sa.Column('paid_date', sa.String(30), nullable=True))
    
    # Add missing indexes for financial tables
    op.create_index('idx_payouts_agency_status', 'payouts', ['agency_id', 'status'])
    op.create_index('idx_payouts_model_status', 'payouts', ['model_id', 'status'])
    op.create_index('idx_payouts_scheduled_date', 'payouts', ['scheduled_date'])
    
    # Add indexes for payment_methods
    op.create_index('idx_payment_methods_model', 'payment_methods', ['model_id'])
    op.create_index('idx_payment_methods_agency', 'payment_methods', ['agency_id'])
    op.create_index('idx_payment_methods_active', 'payment_methods', ['is_active'])
    
    # Add indexes for invoices
    op.create_index('idx_invoices_agency', 'invoices', ['agency_id'])
    op.create_index('idx_invoices_due_date', 'invoices', ['due_date'])
    op.create_index('idx_invoices_paid_status', 'invoices', ['is_paid'])
    
    # Create transaction summary materialized view for better performance
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS transaction_summary AS
        SELECT 
            model_id,
            agency_id,
            DATE_TRUNC('month', transaction_date::timestamp) as month,
            type,
            status,
            COUNT(*) as transaction_count,
            SUM(gross_amount) as total_gross,
            SUM(platform_fee) as total_fees,
            SUM(agency_commission) as total_commission,
            SUM(net_amount) as total_net
        FROM transactions
        WHERE status = 'completed'
        GROUP BY model_id, agency_id, DATE_TRUNC('month', transaction_date::timestamp), type, status
        WITH DATA;
    """)
    
    # Create index on materialized view
    op.execute("""
        CREATE UNIQUE INDEX idx_transaction_summary_unique 
        ON transaction_summary (model_id, agency_id, month, type, status);
    """)
    
    # Create monthly earnings summary view
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS monthly_earnings_summary AS
        SELECT 
            model_id,
            period_year,
            period_month,
            COUNT(*) as transaction_count,
            SUM(gross_amount) as gross_total,
            SUM(commission_amount) as commission_total,
            SUM(net_amount) as net_total,
            SUM(CASE WHEN is_paid THEN net_amount ELSE 0 END) as paid_amount,
            SUM(CASE WHEN NOT is_paid THEN net_amount ELSE 0 END) as unpaid_amount
        FROM earnings
        GROUP BY model_id, period_year, period_month
        WITH DATA;
    """)
    
    # Create index on monthly earnings view
    op.execute("""
        CREATE UNIQUE INDEX idx_monthly_earnings_unique 
        ON monthly_earnings_summary (model_id, period_year, period_month);
    """)


def downgrade():
    # Drop materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS monthly_earnings_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS transaction_summary CASCADE")
    
    # Drop indexes
    op.drop_index('idx_invoices_paid_status', 'invoices')
    op.drop_index('idx_invoices_due_date', 'invoices')
    op.drop_index('idx_invoices_agency', 'invoices')
    
    op.drop_index('idx_payment_methods_active', 'payment_methods')
    op.drop_index('idx_payment_methods_agency', 'payment_methods')
    op.drop_index('idx_payment_methods_model', 'payment_methods')
    
    op.drop_index('idx_payouts_scheduled_date', 'payouts')
    op.drop_index('idx_payouts_model_status', 'payouts')
    op.drop_index('idx_payouts_agency_status', 'payouts')
    
    # Remove paid_date column
    op.drop_column('earnings', 'paid_date')