"""Add saved searches table

Revision ID: saved_searches_001
Revises: 
Create Date: 2025-01-08 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'saved_searches_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create saved_searches table
    op.create_table('saved_searches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('search_type', sa.String(length=50), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indices
    op.create_index(op.f('ix_saved_searches_user_id'), 'saved_searches', ['user_id'], unique=False)
    op.create_index(op.f('ix_saved_searches_agency_id'), 'saved_searches', ['agency_id'], unique=False)
    op.create_index(op.f('ix_saved_searches_search_type'), 'saved_searches', ['search_type'], unique=False)


def downgrade() -> None:
    # Drop indices
    op.drop_index(op.f('ix_saved_searches_search_type'), table_name='saved_searches')
    op.drop_index(op.f('ix_saved_searches_agency_id'), table_name='saved_searches')
    op.drop_index(op.f('ix_saved_searches_user_id'), table_name='saved_searches')
    
    # Drop table
    op.drop_table('saved_searches')