"""add intelligence environment columns to recommendation_outcomes

Revision ID: ie001_feedback_loop
Revises: 2e0555049c32
Create Date: 2026-02-16

Adds the missing columns that transform recommendation_outcomes from a
simple before/after tracker into the feedback loop foundation for the
intelligence environment architecture.

What this adds:
1. Multi-window measurement (7d/14d/30d instead of single 48h snapshot)
2. Confidence decomposition (per-component, not just overall)
3. Agent evidence chain (JSONB snapshots for Scout/Analyst/Strategist)
4. Merchant decision tracking (accepted/modified/rejected + modification pattern)
5. Cross-merchant fields (category + platform for benchmarks)
6. Analyst scoring snapshot (what was predicted vs what happened)
7. Measurement status state machine (background job coordination)

Place this file at: backend/alembic/versions/ie001_feedback_loop_add_intelligence_environment_columns.py
Then run: alembic upgrade head
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers
revision = "ie001_feedback_loop"
down_revision = "2e0555049c32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Measurement status state machine ──
    # Lets the background job know which rows need 7d/14d/30d measurement
    op.add_column(
        "recommendation_outcomes",
        sa.Column(
            "measurement_status",
            sa.String(30),
            nullable=False,
            server_default="single_measured",  # existing rows already have 48h measurement
        ),
    )

    # ── 2. Multi-window revenue measurement ──
    # Existing: revenue_before, revenue_after (single window)
    # Adding: 7d/14d/30d windows for real impact tracking
    op.add_column(
        "recommendation_outcomes",
        sa.Column("revenue_7d_after", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("revenue_14d_after", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("revenue_30d_after", sa.Numeric(14, 2), nullable=True),
    )

    # Multi-window units measurement
    op.add_column(
        "recommendation_outcomes",
        sa.Column("units_7d_after", sa.Integer(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("units_14d_after", sa.Integer(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("units_30d_after", sa.Integer(), nullable=True),
    )

    # Multi-window computed lifts (filled by background job)
    op.add_column(
        "recommendation_outcomes",
        sa.Column("revenue_lift_7d", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("revenue_lift_14d", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("revenue_lift_30d", sa.Float(), nullable=True),
    )

    # Margin tracking
    op.add_column(
        "recommendation_outcomes",
        sa.Column("margin_before", sa.Numeric(6, 3), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("margin_7d_after", sa.Numeric(6, 3), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("margin_30d_after", sa.Numeric(6, 3), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("margin_delta", sa.Float(), nullable=True),
    )

    # ── 3. Confidence decomposition ──
    # Existing: original_confidence (single number)
    # Adding: per-component scores so you can trace which component was wrong
    op.add_column(
        "recommendation_outcomes",
        sa.Column("confidence_elasticity", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("confidence_position", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("confidence_urgency", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("confidence_data_quality", sa.Float(), nullable=True),
    )

    # ── 4. Analyst scoring snapshot ──
    # What the Analyst actually computed at time of recommendation
    # Enables "predicted vs actual" comparison for Bayesian prior updates
    op.add_column(
        "recommendation_outcomes",
        sa.Column("elasticity_estimate", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("urgency_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("sentiment_score", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("competitive_position_index", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("competitor_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("data_completeness", sa.Float(), nullable=True),
    )

    # ── 5. Merchant decision tracking ──
    # Currently only tracks APPLIED recommendations
    # Adding: what the merchant actually decided and how they modified
    op.add_column(
        "recommendation_outcomes",
        sa.Column(
            "merchant_decision",
            sa.String(20),
            nullable=False,
            server_default="accepted",  # existing rows were all applied = accepted
        ),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("actual_price_set", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("merchant_modification_percent", sa.Float(), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )

    # ── 6. Agent evidence chain (JSONB) ──
    # Full provenance for failure tracing: when a recommendation fails,
    # trace which agent's reasoning was wrong
    op.add_column(
        "recommendation_outcomes",
        sa.Column("scout_evidence", JSONB, nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("analyst_evidence", JSONB, nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("strategist_evidence", JSONB, nullable=True),
    )

    # ── 7. Cross-merchant intelligence fields ──
    # Required for category benchmarks (activates at 5+ merchants)
    op.add_column(
        "recommendation_outcomes",
        sa.Column("product_category", sa.String(100), nullable=True),
    )
    op.add_column(
        "recommendation_outcomes",
        sa.Column("store_platform", sa.String(20), nullable=True),
    )

    # ── 8. Recommendation source ──
    # Tracks which pipeline produced this: full_pipeline, rule_based, manual, etc.
    op.add_column(
        "recommendation_outcomes",
        sa.Column(
            "recommendation_source",
            sa.String(30),
            nullable=False,
            server_default="rule_based",
        ),
    )

    # ── Indexes for the new query patterns ──

    # Category performance views (cross-merchant intelligence)
    op.create_index(
        "ix_outcomes_category_created",
        "recommendation_outcomes",
        ["product_category", "created_at"],
    )

    # Measurement job pickup: find rows needing next measurement window
    op.create_index(
        "ix_outcomes_measurement_status",
        "recommendation_outcomes",
        ["measurement_status", "price_applied_at"],
    )

    # Confidence calibration: correlate predicted confidence with actual lift
    op.create_index(
        "ix_outcomes_confidence_lift",
        "recommendation_outcomes",
        ["original_confidence", "revenue_lift_7d"],
    )

    # Merchant decision patterns (backward learning to Strategist)
    op.create_index(
        "ix_outcomes_merchant_decision",
        "recommendation_outcomes",
        ["user_id", "merchant_decision"],
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_outcomes_merchant_decision", table_name="recommendation_outcomes")
    op.drop_index("ix_outcomes_confidence_lift", table_name="recommendation_outcomes")
    op.drop_index("ix_outcomes_measurement_status", table_name="recommendation_outcomes")
    op.drop_index("ix_outcomes_category_created", table_name="recommendation_outcomes")

    # Drop columns in reverse order
    op.drop_column("recommendation_outcomes", "recommendation_source")
    op.drop_column("recommendation_outcomes", "store_platform")
    op.drop_column("recommendation_outcomes", "product_category")
    op.drop_column("recommendation_outcomes", "strategist_evidence")
    op.drop_column("recommendation_outcomes", "analyst_evidence")
    op.drop_column("recommendation_outcomes", "scout_evidence")
    op.drop_column("recommendation_outcomes", "decided_at")
    op.drop_column("recommendation_outcomes", "merchant_modification_percent")
    op.drop_column("recommendation_outcomes", "actual_price_set")
    op.drop_column("recommendation_outcomes", "merchant_decision")
    op.drop_column("recommendation_outcomes", "data_completeness")
    op.drop_column("recommendation_outcomes", "competitor_count")
    op.drop_column("recommendation_outcomes", "competitive_position_index")
    op.drop_column("recommendation_outcomes", "sentiment_score")
    op.drop_column("recommendation_outcomes", "urgency_score")
    op.drop_column("recommendation_outcomes", "elasticity_estimate")
    op.drop_column("recommendation_outcomes", "confidence_data_quality")
    op.drop_column("recommendation_outcomes", "confidence_urgency")
    op.drop_column("recommendation_outcomes", "confidence_position")
    op.drop_column("recommendation_outcomes", "confidence_elasticity")
    op.drop_column("recommendation_outcomes", "margin_delta")
    op.drop_column("recommendation_outcomes", "margin_30d_after")
    op.drop_column("recommendation_outcomes", "margin_7d_after")
    op.drop_column("recommendation_outcomes", "margin_before")
    op.drop_column("recommendation_outcomes", "revenue_lift_30d")
    op.drop_column("recommendation_outcomes", "revenue_lift_14d")
    op.drop_column("recommendation_outcomes", "revenue_lift_7d")
    op.drop_column("recommendation_outcomes", "units_30d_after")
    op.drop_column("recommendation_outcomes", "units_14d_after")
    op.drop_column("recommendation_outcomes", "units_7d_after")
    op.drop_column("recommendation_outcomes", "revenue_30d_after")
    op.drop_column("recommendation_outcomes", "revenue_14d_after")
    op.drop_column("recommendation_outcomes", "revenue_7d_after")
    op.drop_column("recommendation_outcomes", "measurement_status")


    