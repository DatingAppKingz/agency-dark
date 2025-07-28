"""add user profile fields

Revision ID: add_user_profile_fields
Revises: add_webhook_dead_letter_queue
Create Date: 2025-01-28

"""
from alembic import op
import sqlalchemy as sa
import sys
import os

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# revision identifiers, used by Alembic.
revision = 'add_user_profile_fields'
down_revision = 'add_webhook_dead_letter_queue'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users table
    op.add_column('users', sa.Column('username', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('stage_name', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('avatar_url', sa.String(500), nullable=True))
    
    # Create index on username for faster lookups
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_users_username'), table_name='users')
    
    # Drop columns
    op.drop_column('users', 'avatar_url')
    op.drop_column('users', 'stage_name')
    op.drop_column('users', 'username')