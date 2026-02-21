"""merge_heads

Revision ID: e975e3aa34d1
Revises: rule_scoping_001, eth_wallet_001
Create Date: 2025-12-30 19:56:42.834581

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e975e3aa34d1'
down_revision: Union[str, Sequence[str], None] = ('rule_scoping_001', 'eth_wallet_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
