"""add eth_wallet_address to users

Revision ID: eth_wallet_001
Revises: mnee_payments_001
Create Date: 2025-12-25

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eth_wallet_001"
down_revision: str | None = "mnee_payments_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("eth_wallet_address", sa.String(42), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "eth_wallet_address")
