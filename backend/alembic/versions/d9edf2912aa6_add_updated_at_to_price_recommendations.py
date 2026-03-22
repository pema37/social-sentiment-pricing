"""add updated_at to price_recommendations

Revision ID: d9edf2912aa6
Revises: eb1b1cb111ad
Create Date: 2026-03-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd9edf2912aa6'
down_revision: Union[str, Sequence[str], None] = 'eb1b1cb111ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'price_recommendations',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('price_recommendations', 'updated_at')
