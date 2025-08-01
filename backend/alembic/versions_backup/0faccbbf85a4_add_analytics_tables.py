"""Add analytics tables

Revision ID: 0faccbbf85a4
Revises: cd0086df175e
Create Date: 2025-07-23 19:47:03.628926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0faccbbf85a4'
down_revision: Union[str, Sequence[str], None] = 'cd0086df175e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
