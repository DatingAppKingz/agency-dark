"""Add comprehensive multi-tenant indexes for all tables missing agency_id indexes

Revision ID: 022
Revises: 021
Create Date: 2025-08-01

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add agency_id indexes to all tenant-scoped tables that are missing them."""
    
    # Check and add indexes for core tables that might be missing them
    
    # Users table - add composite index if not exists
    op.create_index('idx_users_agency_active', 'users', ['agency_id', 'is_active'], 
                   postgresql_where=sa.text("is_active = true"))
    
    # Model profiles already has agency_id indexes from migration 004
    
    # Analytics and reporting indexes
    op.create_index('idx_notifications_agency_unread', 'notifications', 
                   ['agency_id', 'read'], 
                   postgresql_where=sa.text("read = false"))
    
    op.create_index('idx_audit_logs_agency_date', 'audit_logs', 
                   ['agency_id', 'created_at'])
    
    # Note: The following tables created in migration 021 should have their indexes there:
    # - financial_transactions
    # - chat_conversations
    # - chat_messages
    # - webhook_logs
    # - fan_profiles


def downgrade() -> None:
    """Remove all indexes created in upgrade."""
    
    # Drop indexes
    op.drop_index('idx_audit_logs_agency_date', 'audit_logs')
    op.drop_index('idx_notifications_agency_unread', 'notifications')
    op.drop_index('idx_users_agency_active', 'users')