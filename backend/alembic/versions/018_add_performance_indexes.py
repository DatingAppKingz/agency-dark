"""add performance indexes

Revision ID: 018
Revises: 017
Create Date: 2025-01-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Skip - references non-existent analytics tables."""
    pass

def downgrade() -> None:
    """Skip - references non-existent analytics tables."""
    pass