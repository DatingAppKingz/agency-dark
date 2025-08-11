"""Add OAuth tables

Revision ID: 043_add_oauth_tables
Revises: 041_create_model_assignments
Create Date: 2024-11-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = '043_add_oauth_tables'
down_revision = '041_create_model_assignments'
branch_labels = None
depends_on = None


def upgrade():
    # Create oauth_clients table
    op.create_table('oauth_clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', sa.String(48), nullable=False),
        sa.Column('client_secret', sa.String(120), nullable=True),
        sa.Column('client_name', sa.String(100), nullable=True),
        sa.Column('redirect_uris', postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column('grant_types', postgresql.ARRAY(sa.Text), nullable=False, server_default='{"authorization_code"}'),
        sa.Column('response_types', postgresql.ARRAY(sa.Text), nullable=False, server_default='{"code"}'),
        sa.Column('scope', sa.Text(), nullable=True, server_default=''),
        sa.Column('allowed_agencies', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id')
    )
    op.create_index('idx_oauth_clients_agency_id', 'oauth_clients', ['agency_id'])
    op.create_index('idx_oauth_clients_client_id', 'oauth_clients', ['client_id'])

    # Create oauth_tokens table
    op.create_table('oauth_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('client_id', sa.String(48), nullable=True),
        sa.Column('token_type', sa.String(40), nullable=True),
        sa.Column('access_token', sa.String(255), nullable=False),
        sa.Column('refresh_token', sa.String(255), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True, server_default=''),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['oauth_clients.client_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('access_token'),
        sa.UniqueConstraint('refresh_token')
    )
    op.create_index('idx_oauth_tokens_user_id', 'oauth_tokens', ['user_id'])
    op.create_index('idx_oauth_tokens_expires_at', 'oauth_tokens', ['expires_at'])
    op.create_index('idx_oauth_tokens_access_token', 'oauth_tokens', ['access_token'])

    # Create oauth_authorization_codes table
    op.create_table('oauth_authorization_codes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('client_id', sa.String(48), nullable=True),
        sa.Column('code', sa.String(120), nullable=False),
        sa.Column('redirect_uri', sa.Text(), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True, server_default=''),
        sa.Column('code_challenge', sa.String(128), nullable=True),
        sa.Column('code_challenge_method', sa.String(10), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['oauth_clients.client_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index('idx_oauth_authorization_codes_code', 'oauth_authorization_codes', ['code'])

    # Create external_oauth_tokens table (for Instagram, OnlyFans, etc.)
    op.create_table('external_oauth_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),  # Encrypted
        sa.Column('refresh_token', sa.Text(), nullable=True),  # Encrypted
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('raw_data', sa.Text(), nullable=True),  # Encrypted JSON
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_external_oauth_tokens_provider', 'external_oauth_tokens', ['provider', 'user_id'])
    op.create_index('idx_external_oauth_tokens_agency_id', 'external_oauth_tokens', ['agency_id'])

    # Create oauth_consent_records table for tracking user consent
    op.create_table('oauth_consent_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=uuid.uuid4),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', sa.String(48), nullable=False),
        sa.Column('scope', sa.Text(), nullable=False),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['client_id'], ['oauth_clients.client_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_oauth_consent_records_user_client', 'oauth_consent_records', ['user_id', 'client_id'])

    # Update users table with OAuth fields
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('age_verified', sa.Boolean(), nullable=False, server_default='false'))
        batch_op.add_column(sa.Column('age_verified_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('oauth_provider', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('oauth_id', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('oauth_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Create indexes on new user columns
    op.create_index('idx_users_oauth_provider', 'users', ['oauth_provider', 'oauth_id'])
    op.create_index('idx_users_age_verified', 'users', ['age_verified'])


def downgrade():
    # Drop indexes on users table
    op.drop_index('idx_users_age_verified', table_name='users')
    op.drop_index('idx_users_oauth_provider', table_name='users')
    
    # Remove columns from users table
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('oauth_metadata')
        batch_op.drop_column('oauth_id')
        batch_op.drop_column('oauth_provider')
        batch_op.drop_column('age_verified_at')
        batch_op.drop_column('age_verified')
    
    # Drop tables
    op.drop_table('oauth_consent_records')
    op.drop_table('external_oauth_tokens')
    op.drop_table('oauth_authorization_codes')
    op.drop_table('oauth_tokens')
    op.drop_table('oauth_clients')