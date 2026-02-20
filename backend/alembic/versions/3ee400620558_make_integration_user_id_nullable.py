"""make integration user_id nullable

Revision ID: 3ee400620558
Revises: ie004
Create Date: 2026-02-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '3ee400620558'
down_revision: Union[str, Sequence[str], None] = 'ie004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('integrations', 'user_id',
                    existing_type=sa.UUID(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('integrations', 'user_id',
                    existing_type=sa.UUID(),
                    nullable=False)
