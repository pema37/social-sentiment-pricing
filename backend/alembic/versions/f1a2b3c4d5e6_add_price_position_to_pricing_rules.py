"""add price_position to pricing_rules

Revision ID: f1a2b3c4d5e6
Revises: fix_keywords_jsonb
Create Date: 2025-12-31
"""

import sqlalchemy as sa

from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "fix_keywords_jsonb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pricing_rules", sa.Column("price_position", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("pricing_rules", "price_position")
