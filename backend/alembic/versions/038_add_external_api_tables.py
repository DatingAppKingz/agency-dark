"""Add external API credential tables

Revision ID: 038_add_external_api_tables
Revises: 037_add_payment_method_fields
Create Date: 2024-01-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '038_add_external_api_tables'
down_revision = '037_add_payment_method_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create APIProvider enum
    op.execute("CREATE TYPE apiprovider AS ENUM ('onlyfans', 'stripe', 'inflow')")
    
    # Create external_api_credentials table
    op.create_table('external_api_credentials',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.Enum('onlyfans', 'stripe', 'inflow', name='apiprovider'), nullable=False),
        sa.Column('credentials', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_valid', sa.Boolean(), nullable=True),
        sa.Column('last_validated', sa.DateTime(), nullable=True),
        sa.Column('validation_error', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_user_provider')
    )
    
    # Create indexes for external_api_credentials
    op.create_index('idx_external_api_user_provider', 'external_api_credentials', ['user_id', 'provider'])
    op.create_index('idx_external_api_agency_provider', 'external_api_credentials', ['agency_id', 'provider'])
    
    # Create webhook_endpoints table
    op.create_table('webhook_endpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.Enum('onlyfans', 'stripe', 'inflow', name='apiprovider'), nullable=False),
        sa.Column('endpoint_url', sa.String(length=500), nullable=False),
        sa.Column('secret', sa.String(length=500), nullable=True),
        sa.Column('events', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('last_received', sa.DateTime(), nullable=True),
        sa.Column('failure_count', sa.Integer(), nullable=False, default=0),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agency_id', 'provider', 'endpoint_url', name='uq_agency_provider_url')
    )
    
    # Create indexes for webhook_endpoints
    op.create_index('idx_webhook_agency_provider', 'webhook_endpoints', ['agency_id', 'provider'])
    
    # Create api_call_logs table
    op.create_table('api_call_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('credential_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', sa.Enum('onlyfans', 'stripe', 'inflow', name='apiprovider'), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('endpoint', sa.String(length=500), nullable=False),
        sa.Column('request_headers', sa.JSON(), nullable=True),
        sa.Column('request_body', sa.JSON(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_headers', sa.JSON(), nullable=True),
        sa.Column('response_body', sa.JSON(), nullable=True),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('is_error', sa.Boolean(), nullable=False, default=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['credential_id'], ['external_api_credentials.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for api_call_logs
    op.create_index('idx_api_log_provider_created', 'api_call_logs', ['provider', 'created_at'])
    op.create_index('idx_api_log_credential', 'api_call_logs', ['credential_id'])
    op.create_index('idx_api_log_error', 'api_call_logs', ['is_error', 'created_at'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('api_call_logs')
    op.drop_table('webhook_endpoints')
    op.drop_table('external_api_credentials')
    
    # Drop enum type
    op.execute('DROP TYPE apiprovider')