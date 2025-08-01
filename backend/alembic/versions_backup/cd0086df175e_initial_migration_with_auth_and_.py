"""Initial migration with auth and OnlyFans models

Revision ID: cd0086df175e
Revises: 
Create Date: 2025-07-23 16:55:13.313911

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'cd0086df175e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for AgencyDark MVP."""
    
    # Create custom types
    op.execute("CREATE TYPE userole AS ENUM ('super_admin', 'agency_owner', 'agency_admin', 'agency_member', 'model', 'chatter')")
    op.execute("CREATE TYPE subscriptionstatus AS ENUM ('active', 'trialing', 'canceled', 'past_due', 'incomplete')")
    op.execute("CREATE TYPE notificationtype AS ENUM ('info', 'warning', 'error', 'success')")
    
    # Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    
    # Create agencies table
    op.create_table('agencies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True),
        sa.Column('settings', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('subscription_status', postgresql.ENUM('active', 'trialing', 'canceled', 'past_due', 'incomplete', name='subscriptionstatus', create_type=False), nullable=True, server_default='trialing'),
        sa.Column('subscription_ends_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    
    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', postgresql.ENUM('super_admin', 'agency_owner', 'agency_admin', 'agency_member', 'model', 'chatter', name='userole', create_type=False), nullable=False, server_default='agency_member'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('email_verification_token', sa.String(length=255), nullable=True),
        sa.Column('password_reset_token', sa.String(length=255), nullable=True),
        sa.Column('password_reset_expires', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    
    # Create sessions table
    op.create_table('sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('refresh_token', sa.String(length=500), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('refreshed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('refresh_token')
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)
    
    # Create notifications table
    op.create_table('notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('type', postgresql.ENUM('info', 'warning', 'error', 'success', name='notificationtype', create_type=False), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('read', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_agency_id'), 'notifications', ['agency_id'], unique=False)
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    
    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(length=255), nullable=False),
        sa.Column('resource_type', sa.String(length=255), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True, server_default='{}'),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_agency_id'), 'audit_logs', ['agency_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_created_at'), 'audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)
    
    # Create model_profiles table
    op.create_table('model_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('onlyfans_username', sa.String(length=255), nullable=False),
        sa.Column('onlyfans_user_id', sa.String(length=255), nullable=True),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('profile_photo_url', sa.Text(), nullable=True),
        sa.Column('cover_photo_url', sa.Text(), nullable=True),
        sa.Column('inflow_api_key', sa.Text(), nullable=True),
        sa.Column('onlyfans_api_key', sa.Text(), nullable=True),
        sa.Column('subscriber_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('paying_subscriber_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_earnings', sa.Numeric(precision=12, scale=2), nullable=True, server_default='0'),
        sa.Column('commission_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('onlyfans_username'),
        sa.UniqueConstraint('onlyfans_user_id')
    )
    op.create_index(op.f('ix_model_profiles_agency_id'), 'model_profiles', ['agency_id'], unique=False)
    
    # Create model_chatters table
    op.create_table('model_chatters',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chatter_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('assigned_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['chatter_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['model_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_id', 'chatter_id', name='uq_model_chatter')
    )
    
    # Create fans table
    op.create_table('fans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('onlyfans_user_id', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('is_subscriber', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('is_paying', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('subscription_price', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('subscribed_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('total_spent', sa.Numeric(precision=12, scale=2), nullable=True, server_default='0'),
        sa.Column('message_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('tip_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('ppv_purchased_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_active_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['model_id'], ['model_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_id', 'onlyfans_user_id', name='uq_model_fan')
    )
    op.create_index(op.f('ix_fans_model_id'), 'fans', ['model_id'], unique=False)
    
    # Create fan_claims table
    op.create_table('fan_claims',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('uuid_generate_v4()')),
        sa.Column('fan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chatter_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('claimed_by_model', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('claimed_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('released_at', sa.DateTime(), nullable=True),
        sa.Column('released_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['chatter_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fan_id'], ['fans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['model_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['released_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_active_fan_claim', 'fan_claims', ['fan_id', 'is_active'], unique=True, postgresql_where=sa.text('is_active = true'))
    
    # Create update triggers for updated_at columns
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    for table in ['agencies', 'users', 'model_profiles', 'fans']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at 
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)


def downgrade() -> None:
    """Drop all tables."""
    # Drop triggers
    for table in ['agencies', 'users', 'model_profiles', 'fans']:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table}")
    
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    
    # Drop tables in reverse order
    op.drop_table('fan_claims')
    op.drop_table('fans')
    op.drop_table('model_chatters')
    op.drop_table('model_profiles')
    op.drop_table('audit_logs')
    op.drop_table('notifications')
    op.drop_table('sessions')
    op.drop_table('users')
    op.drop_table('agencies')
    
    # Drop custom types
    op.execute("DROP TYPE IF EXISTS userole")
    op.execute("DROP TYPE IF EXISTS subscriptionstatus")
    op.execute("DROP TYPE IF EXISTS notificationtype")