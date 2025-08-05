"""create model assignments table

Revision ID: 041_create_model_assignments
Revises: 040_add_performance_indexes
Create Date: 2024-08-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '041_create_model_assignments'
down_revision = '040_add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create model_assignments table
    op.create_table('model_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chatter_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agency_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('priority', sa.String(), nullable=True, default='normal'),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['chatter_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['model_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chatter_id', 'model_id', name='unique_chatter_model_assignment')
    )
    
    # Create indexes for better query performance
    op.create_index('idx_model_assignments_chatter', 'model_assignments', ['chatter_id'])
    op.create_index('idx_model_assignments_model', 'model_assignments', ['model_id'])
    op.create_index('idx_model_assignments_agency', 'model_assignments', ['agency_id'])
    op.create_index('idx_model_assignments_active', 'model_assignments', ['is_active'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_model_assignments_active', table_name='model_assignments')
    op.drop_index('idx_model_assignments_agency', table_name='model_assignments')
    op.drop_index('idx_model_assignments_model', table_name='model_assignments')
    op.drop_index('idx_model_assignments_chatter', table_name='model_assignments')
    
    # Drop table
    op.drop_table('model_assignments')