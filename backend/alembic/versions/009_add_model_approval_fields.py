"""Add model approval workflow fields

Revision ID: 009_model_approval
Revises: 008_add_missing_columns
Create Date: 2025-08-04 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009_model_approval'
down_revision = '008_add_fraud_detection_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add approval workflow fields to models table."""
    # Add new columns
    op.add_column('models', sa.Column('reviewed_by', sa.Integer(), nullable=True))
    op.add_column('models', sa.Column('reviewed_at', sa.String(30), nullable=True))
    op.add_column('models', sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.add_column('models', sa.Column('admin_notes', sa.Text(), nullable=True))
    op.add_column('models', sa.Column('id_document_url', sa.String(500), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_models_reviewed_by_users',
        'models', 'users',
        ['reviewed_by'], ['id'],
        ondelete='SET NULL'
    )
    
    # Update existing status enum to include new values
    # First, create a new enum type
    op.execute("CREATE TYPE modelstatus_new AS ENUM ('pending', 'under_review', 'active', 'paused', 'inactive', 'banned', 'rejected', 'deleted')")
    
    # Change column to use new enum, converting values
    op.execute("""
        ALTER TABLE models 
        ALTER COLUMN status TYPE modelstatus_new 
        USING status::text::modelstatus_new
    """)
    
    # Drop old enum type
    op.execute("DROP TYPE IF EXISTS modelstatus")
    
    # Rename new enum to old name
    op.execute("ALTER TYPE modelstatus_new RENAME TO modelstatus")


def downgrade():
    """Remove approval workflow fields from models table."""
    # Drop foreign key constraint
    op.drop_constraint('fk_models_reviewed_by_users', 'models', type_='foreignkey')
    
    # Drop columns
    op.drop_column('models', 'reviewed_by')
    op.drop_column('models', 'reviewed_at')
    op.drop_column('models', 'rejection_reason')
    op.drop_column('models', 'admin_notes')
    op.drop_column('models', 'id_document_url')
    
    # Revert enum type
    # Create old enum type
    op.execute("CREATE TYPE modelstatus_old AS ENUM ('pending', 'active', 'paused', 'inactive', 'banned')")
    
    # Update any new statuses to closest old status
    op.execute("UPDATE models SET status = 'inactive' WHERE status IN ('rejected', 'deleted')")
    op.execute("UPDATE models SET status = 'pending' WHERE status = 'under_review'")
    
    # Change column to use old enum
    op.execute("""
        ALTER TABLE models 
        ALTER COLUMN status TYPE modelstatus_old 
        USING status::text::modelstatus_old
    """)
    
    # Drop new enum type
    op.execute("DROP TYPE modelstatus")
    
    # Rename old enum to original name
    op.execute("ALTER TYPE modelstatus_old RENAME TO modelstatus")