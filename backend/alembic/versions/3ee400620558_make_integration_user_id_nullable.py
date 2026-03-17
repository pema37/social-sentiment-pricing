"""make integration user_id nullable

Revision ID: 3ee400620558
Revises: ie004
Create Date: 2026-02-20
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "3ee400620558"
down_revision: str | Sequence[str] | None = "ie004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("integrations", "user_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("integrations", "user_id", existing_type=sa.UUID(), nullable=False)
