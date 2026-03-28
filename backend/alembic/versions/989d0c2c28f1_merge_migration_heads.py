"""merge_migration_heads

Revision ID: 989d0c2c28f1
Revises: batch24_001, d9edf2912aa6
Create Date: 2026-03-27 07:45:14.128401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '989d0c2c28f1'
down_revision: Union[str, Sequence[str], None] = ('batch24_001', 'd9edf2912aa6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
