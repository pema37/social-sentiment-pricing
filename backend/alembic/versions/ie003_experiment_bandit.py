"""ie003: Add experiment columns and bandit state table

Adds Thompson Sampling experiment tracking to pricing_outcomes
and creates bandit_state table for crash recovery.

Revision ID: ie003_experiment_bandit
Revises: ie002_materialized_benchmark_views
Create Date: 2026-02-18

IMPORTANT: This migration is backward-compatible.
- All new columns are NULLABLE (old code still works with new schema)
- bandit_state is a new table (no existing code affected)
- Deploy code that writes to new columns AFTER this migration runs
- Add NOT NULL constraints in a follow-up migration (ie004) once backfill is done

Zero-downtime deployment order:
  1. Run this migration
  2. Deploy new code that writes experiment metadata
  3. Run ie004 (add NOT NULL where appropriate) after backfill
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers
revision = "ie003_experiment_bandit"
down_revision = "ie002_materialized_benchmark_views"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add experiment columns to pricing_outcomes
    #    (ie001 already added confidence_decomposition and agent_evidence)
    # ------------------------------------------------------------------
    op.add_column(
        "pricing_outcomes",
        sa.Column(
            "strategy_arm",
            sa.String(length=100),
            nullable=True,
            comment="Thompson Sampling strategy arm name (e.g., 'conservative', 'elasticity_optimal')",
        ),
    )
    op.add_column(
        "pricing_outcomes",
        sa.Column(
            "is_exploration",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
            comment="True if this was a 5% exploration holdout assignment",
        ),
    )
    op.add_column(
        "pricing_outcomes",
        sa.Column(
            "bandit_processed",
            sa.Boolean(),
            nullable=True,
            server_default=sa.text("false"),
            comment="True once the bandit has ingested this outcome",
        ),
    )
    op.add_column(
        "pricing_outcomes",
        sa.Column(
            "experiment_assignment_id",
            sa.String(length=36),
            nullable=True,
            comment="UUID linking to the experiment assignment record",
        ),
    )
    op.add_column(
        "pricing_outcomes",
        sa.Column(
            "scoring_version",
            sa.String(length=50),
            nullable=True,
            comment="Pipeline version that generated this recommendation (e.g., ie-v1.0)",
        ),
    )

    # Index for bandit processing: find unprocessed outcomes quickly
    op.create_index(
        "ix_pricing_outcomes_bandit_unprocessed",
        "pricing_outcomes",
        ["bandit_processed"],
        postgresql_where=sa.text("bandit_processed = false"),
    )

    # Index for experiment analysis: filter by strategy arm
    op.create_index(
        "ix_pricing_outcomes_strategy_arm",
        "pricing_outcomes",
        ["strategy_arm"],
        postgresql_where=sa.text("strategy_arm IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # 2. Create bandit_state table for Thompson Sampling crash recovery
    # ------------------------------------------------------------------
    op.create_table(
        "bandit_state",
        sa.Column(
            "id",
            sa.String(length=36),
            primary_key=True,
            comment="UUID primary key",
        ),
        sa.Column(
            "category_id",
            sa.String(length=255),
            nullable=False,
            index=True,
            comment="Product category this bandit manages",
        ),
        sa.Column(
            "arm_states",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Per-arm Beta distribution parameters: {arm_name: {alpha, beta, pulls, wins}}",
        ),
        sa.Column(
            "total_pulls",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Total assignments across all arms",
        ),
        sa.Column(
            "converged_arm",
            sa.String(length=100),
            nullable=True,
            comment="Arm name if convergence detected, NULL otherwise",
        ),
        sa.Column(
            "convergence_confidence",
            sa.Float(),
            nullable=True,
            comment="Statistical confidence of convergence (0-1)",
        ),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Last time bandit state was persisted",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "metadata",
            JSONB,
            nullable=True,
            comment="Additional metadata: exploration_rate, prior_config, etc.",
        ),
        comment="Thompson Sampling bandit state for crash recovery. One row per category.",
    )

    # Unique constraint: one bandit per category
    op.create_unique_constraint(
        "uq_bandit_state_category_id",
        "bandit_state",
        ["category_id"],
    )

    # ------------------------------------------------------------------
    # 3. Create experiment_assignments table for audit trail
    # ------------------------------------------------------------------
    op.create_table(
        "experiment_assignments",
        sa.Column(
            "id",
            sa.String(length=36),
            primary_key=True,
            comment="UUID primary key (referenced by pricing_outcomes.experiment_assignment_id)",
        ),
        sa.Column(
            "recommendation_id",
            sa.String(length=36),
            nullable=False,
            index=True,
            comment="Which recommendation this assignment belongs to",
        ),
        sa.Column(
            "category_id",
            sa.String(length=255),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "merchant_id",
            sa.String(length=36),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "strategy_arm",
            sa.String(length=100),
            nullable=False,
            comment="Name of the strategy arm selected",
        ),
        sa.Column(
            "arm_index",
            sa.Integer(),
            nullable=False,
            comment="Numeric index of the arm in the bandit",
        ),
        sa.Column(
            "is_exploration",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether this was an exploration vs exploitation pull",
        ),
        sa.Column(
            "strategy_config",
            JSONB,
            nullable=True,
            comment="Full strategy config applied: magnitude_multiplier, guardrail_overrides, weight_overrides",
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        comment="Audit trail for Thompson Sampling experiment assignments.",
    )

    # ------------------------------------------------------------------
    # 4. Add scoring_version to pricing_recommendations if not exists
    #    (for tracking which pipeline version generated each recommendation)
    # ------------------------------------------------------------------
    # Check if column already exists (defensive — ie001 may have added it)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='pricing_recommendations' AND column_name='scoring_version'"
        )
    )
    if result.fetchone() is None:
        op.add_column(
            "pricing_recommendations",
            sa.Column(
                "scoring_version",
                sa.String(length=50),
                nullable=True,
                comment="IE pipeline version (e.g., ie-v1.0)",
            ),
        )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("experiment_assignments")

    op.drop_constraint("uq_bandit_state_category_id", "bandit_state")
    op.drop_table("bandit_state")

    # Drop indexes
    op.drop_index("ix_pricing_outcomes_strategy_arm", "pricing_outcomes")
    op.drop_index("ix_pricing_outcomes_bandit_unprocessed", "pricing_outcomes")

    # Drop columns from pricing_outcomes
    op.drop_column("pricing_outcomes", "scoring_version")
    op.drop_column("pricing_outcomes", "experiment_assignment_id")
    op.drop_column("pricing_outcomes", "bandit_processed")
    op.drop_column("pricing_outcomes", "is_exploration")
    op.drop_column("pricing_outcomes", "strategy_arm")

    # Conditionally drop scoring_version from pricing_recommendations
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='pricing_recommendations' AND column_name='scoring_version'"
        )
    )
    if result.fetchone() is not None:
        op.drop_column("pricing_recommendations", "scoring_version")


        