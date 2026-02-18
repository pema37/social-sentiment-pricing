"""merge_ie001_with_existing

Revision ID: 0c9987a05f5d
Revises: fa2643be5ee3, ie001_feedback_loop
Create Date: 2026-02-17 14:45:44.100585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0c9987a05f5d'
down_revision: Union[str, Sequence[str], None] = ('fa2643be5ee3', 'ie001_feedback_loop')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
