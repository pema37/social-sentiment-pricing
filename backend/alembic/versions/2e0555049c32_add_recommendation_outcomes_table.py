"""add recommendation_outcomes table

Revision ID: 2e0555049c32
Revises: 5ddb105edefa
Create Date: 2025-12-02 08:26:32.932934

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e0555049c32"
down_revision: str | Sequence[str] | None = "5ddb105edefa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "recommendation_outcomes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("recommendation_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=True),
        sa.Column("rule_type", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("price_before", sa.Numeric(scale=2), nullable=False),
        sa.Column("price_after", sa.Numeric(scale=2), nullable=False),
        sa.Column("price_change_percent", sa.Numeric(scale=2), nullable=False),
        sa.Column("sales_count_before", sa.Integer(), nullable=False),
        sa.Column("units_sold_before", sa.Integer(), nullable=False),
        sa.Column("revenue_before", sa.Numeric(scale=2), nullable=False),
        sa.Column("avg_daily_sales_before", sa.Numeric(scale=2), nullable=False),
        sa.Column("sales_count_after", sa.Integer(), nullable=False),
        sa.Column("units_sold_after", sa.Integer(), nullable=False),
        sa.Column("revenue_after", sa.Numeric(scale=2), nullable=False),
        sa.Column("avg_daily_sales_after", sa.Numeric(scale=2), nullable=False),
        sa.Column("revenue_change", sa.Numeric(scale=2), nullable=False),
        sa.Column("revenue_change_percent", sa.Numeric(scale=2), nullable=True),
        sa.Column("units_change", sa.Integer(), nullable=False),
        sa.Column("units_change_percent", sa.Numeric(scale=2), nullable=True),
        sa.Column("outcome_score", sa.Numeric(scale=2), nullable=False),
        sa.Column(
            "outcome_label",
            sa.Enum("POSITIVE", "NEGATIVE", "NEUTRAL", "INCONCLUSIVE", name="outcomelabel"),
            nullable=False,
        ),
        sa.Column("original_confidence", sa.Numeric(scale=2), nullable=False),
        sa.Column("price_applied_at", sa.DateTime(), nullable=False),
        sa.Column("measurement_window_hours", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_recommendation_outcomes_price_applied_at"),
        "recommendation_outcomes",
        ["price_applied_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recommendation_outcomes_product_id"), "recommendation_outcomes", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_recommendation_outcomes_recommendation_id"),
        "recommendation_outcomes",
        ["recommendation_id"],
        unique=True,
    )
    op.create_index(op.f("ix_recommendation_outcomes_rule_id"), "recommendation_outcomes", ["rule_id"], unique=False)
    op.create_index(op.f("ix_recommendation_outcomes_user_id"), "recommendation_outcomes", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_recommendation_outcomes_user_id"), table_name="recommendation_outcomes")
    op.drop_index(op.f("ix_recommendation_outcomes_rule_id"), table_name="recommendation_outcomes")
    op.drop_index(op.f("ix_recommendation_outcomes_recommendation_id"), table_name="recommendation_outcomes")
    op.drop_index(op.f("ix_recommendation_outcomes_product_id"), table_name="recommendation_outcomes")
    op.drop_index(op.f("ix_recommendation_outcomes_price_applied_at"), table_name="recommendation_outcomes")
    op.drop_table("recommendation_outcomes")
    op.execute("DROP TYPE IF EXISTS outcomelabel")
