"""add_pricing_engine_tables

Revision ID: d99408af71fc
Revises: fe5f2a6d2e42
Create Date: 2025-12-01 16:41:12.885060

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d99408af71fc"
down_revision: str | Sequence[str] | None = "fe5f2a6d2e42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create new pricing tables
    op.create_table(
        "price_recommendations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("triggered_rule_id", sa.UUID(), nullable=True),
        sa.Column("current_price", sa.Numeric(scale=2), nullable=False),
        sa.Column("recommended_price", sa.Numeric(scale=2), nullable=False),
        sa.Column("change_percent", sa.Numeric(scale=2), nullable=False),
        sa.Column("confidence_score", sa.Numeric(scale=2), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("factors", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING", "AUTO_APPROVED", "APPROVED", "REJECTED", "APPLIED", "EXPIRED", name="recommendationstatus"
            ),
            nullable=False,
        ),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("rejection_reason", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("applied_to_platform", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_price_recommendations_product_id"), "price_recommendations", ["product_id"], unique=False)
    op.create_index(op.f("ix_price_recommendations_user_id"), "price_recommendations", ["user_id"], unique=False)

    op.create_table(
        "pricing_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column(
            "rule_type",
            sa.Enum(
                "SENTIMENT_THRESHOLD",
                "COMPETITOR_RELATIVE",
                "TIME_BASED",
                "VOLUME_SURGE",
                "VIRAL_DETECTION",
                name="ruletype",
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("sentiment_threshold", sa.Numeric(scale=2), nullable=True),
        sa.Column("sentiment_direction", sqlmodel.sql.sqltypes.AutoString(length=10), nullable=True),
        sa.Column("competitor_id", sa.UUID(), nullable=True),
        sa.Column("competitor_margin_percent", sa.Numeric(scale=2), nullable=True),
        sa.Column("time_days", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("time_start", sqlmodel.sql.sqltypes.AutoString(length=5), nullable=True),
        sa.Column("time_end", sqlmodel.sql.sqltypes.AutoString(length=5), nullable=True),
        sa.Column("volume_threshold", sa.Integer(), nullable=True),
        sa.Column("volume_window_hours", sa.Integer(), nullable=True),
        sa.Column("viral_threshold_reach", sa.Integer(), nullable=True),
        sa.Column("viral_threshold_engagement", sa.Integer(), nullable=True),
        sa.Column("viral_sentiment_min", sa.Numeric(scale=2), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "INCREASE_PERCENT",
                "DECREASE_PERCENT",
                "SET_ABSOLUTE",
                "MATCH_COMPETITOR",
                "UNDERCUT_COMPETITOR",
                name="ruleaction",
            ),
            nullable=False,
        ),
        sa.Column("action_value", sa.Numeric(scale=2), nullable=False),
        sa.Column("min_price", sa.Numeric(scale=2), nullable=True),
        sa.Column("max_price", sa.Numeric(scale=2), nullable=True),
        sa.Column("max_change_percent", sa.Numeric(scale=2), nullable=False),
        sa.Column("cooldown_hours", sa.Integer(), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pricing_rules_product_id"), "pricing_rules", ["product_id"], unique=False)
    op.create_index(op.f("ix_pricing_rules_user_id"), "pricing_rules", ["user_id"], unique=False)

    op.create_table(
        "pricing_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("auto_approve_enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_approve_max_increase", sa.Numeric(scale=2), nullable=False),
        sa.Column("auto_approve_max_decrease", sa.Numeric(scale=2), nullable=False),
        sa.Column("auto_approve_min_confidence", sa.Numeric(scale=2), nullable=False),
        sa.Column("max_auto_changes_per_day", sa.Integer(), nullable=False),
        sa.Column("global_cooldown_hours", sa.Integer(), nullable=False),
        sa.Column("blackout_hours_start", sa.Integer(), nullable=True),
        sa.Column("blackout_hours_end", sa.Integer(), nullable=True),
        sa.Column("require_approval_above_price", sa.Numeric(scale=2), nullable=True),
        sa.Column("recommendation_valid_hours", sa.Integer(), nullable=False),
        sa.Column("notify_on_auto_apply", sa.Boolean(), nullable=False),
        sa.Column("notify_on_pending", sa.Boolean(), nullable=False),
        sa.Column("notification_email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("notification_slack_webhook", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pricing_settings_user_id"), "pricing_settings", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_pricing_settings_user_id"), table_name="pricing_settings")
    op.drop_table("pricing_settings")
    op.drop_index(op.f("ix_pricing_rules_user_id"), table_name="pricing_rules")
    op.drop_index(op.f("ix_pricing_rules_product_id"), table_name="pricing_rules")
    op.drop_table("pricing_rules")
    op.drop_index(op.f("ix_price_recommendations_user_id"), table_name="price_recommendations")
    op.drop_index(op.f("ix_price_recommendations_product_id"), table_name="price_recommendations")
    op.drop_table("price_recommendations")
