"""Add commission tracking fields

Revision ID: 027
Revises: 026
Create Date: 2024-01-31 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add commission tracking fields to models and transactions."""
    
    # Add monthly revenue tracking to models
    op.add_column('models', sa.Column('current_month_revenue', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'))
    op.add_column('models', sa.Column('last_month_revenue', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'))
    op.add_column('models', sa.Column('current_commission_tier', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('models', sa.Column('commission_rate_override', sa.Numeric(precision=5, scale=4), nullable=True))
    
    # Add detailed commission tracking to transactions (if table exists)
    # Check if transactions table exists
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'transactions')"
    ))
    if result.scalar():
        op.add_column('transactions', sa.Column('commission_tier_at_time', sa.Integer(), nullable=True))
        op.add_column('transactions', sa.Column('agency_commission_rate', sa.Numeric(precision=5, scale=4), nullable=True))
        op.add_column('transactions', sa.Column('platform_commission_rate', sa.Numeric(precision=5, scale=4), nullable=True))
    
    # Create commission_history table for tracking tier changes
    op.create_table('commission_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('month', sa.Date(), nullable=False),
        sa.Column('total_revenue', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('commission_tier', sa.Integer(), nullable=False),
        sa.Column('commission_rate', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('total_commission', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique index for model/month combination
    op.create_index('idx_commission_history_model_month', 'commission_history', ['model_id', 'month'], unique=True)
    
    # Create commission_rules table for custom commission structures (if not exists)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'commission_rules')"
    ))
    if not result.scalar():
        op.create_table('commission_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(50), nullable=False),  # 'tiered', 'flat', 'custom'
        sa.Column('tiers', sa.JSON(), nullable=True),  # JSON array of tier definitions
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
        # Create index for active rules lookup
        op.create_index('idx_commission_rules_active', 'commission_rules', ['agency_id', 'is_active'])
    
    # Create commission_overrides table for model-specific overrides
    op.create_table('commission_overrides',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('override_type', sa.String(50), nullable=False),  # 'rate', 'tier', 'rule'
        sa.Column('override_value', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['model_id'], ['models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_id'], ['commission_rules.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for active overrides lookup
    op.create_index('idx_commission_overrides_active', 'commission_overrides', ['model_id', 'start_date', 'end_date'])


def downgrade() -> None:
    """Remove commission tracking fields and tables."""
    
    # Drop tables
    op.drop_table('commission_overrides')
    op.drop_table('commission_rules')
    op.drop_table('commission_history')
    
    # Remove columns from transactions (if table exists)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'transactions')"
    ))
    if result.scalar():
        op.drop_column('transactions', 'platform_commission_rate')
        op.drop_column('transactions', 'agency_commission_rate')
        op.drop_column('transactions', 'commission_tier_at_time')
    
    # Remove columns from models
    op.drop_column('models', 'commission_rate_override')
    op.drop_column('models', 'current_commission_tier')
    op.drop_column('models', 'last_month_revenue')
    op.drop_column('models', 'current_month_revenue')