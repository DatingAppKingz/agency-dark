"""Add financial tables

Revision ID: ab6eda48e947
Revises: 0faccbbf85a4
Create Date: 2025-07-23 20:00:55.173846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab6eda48e947'
down_revision: Union[str, Sequence[str], None] = '0faccbbf85a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
