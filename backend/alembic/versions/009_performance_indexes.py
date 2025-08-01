"""Add performance indexes

Revision ID: 009
Revises: 008
Create Date: 2025-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    """Add performance indexes for existing tables only."""
    
    # NOTE: Many indexes were already created in migration 004
    # This migration adds only the missing indexes that weren't created before
    
    # Users table - additional indexes not in 004
    # Note: idx_users_agency_role, idx_users_active_verified, idx_users_last_login already created in 004
    
    # Agencies table - additional indexes not in 004
    # Note: agencies table doesn't have is_active column
    
    # Model_profiles table - additional indexes not in 004
    # Note: idx_model_profiles_agency_active, idx_model_profiles_last_sync, idx_model_profiles_earnings already created in 004
    
    # Fans table - additional indexes not in 004
    # Note: idx_fans_active_subscribers, idx_fans_last_active, idx_fans_total_spent already created in 004
    
    # Sessions table - additional indexes
    # Note: idx_sessions_expires_active already created in 004
    
    # Notifications table - additional indexes
    # Note: idx_notifications_user_read already created in 004
    
    # Audit logs table - additional indexes
    # Note: idx_audit_logs_resource already created in 004
    
    # NOTE: Since migration 004 already created most of the important indexes
    # and many referenced tables don't exist yet, this migration is effectively
    # a no-op to maintain the migration sequence


def downgrade():
    """Drop performance indexes."""
    
    # Since we didn't add any new indexes in upgrade,
    # there's nothing to drop in downgrade
    pass