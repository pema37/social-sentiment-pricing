"""Convert all TIMESTAMP WITHOUT TIME ZONE columns to TIMESTAMP WITH TIME ZONE.

Revision ID: ie004
Revises: ie003
Create Date: 2026-02-20

SaaS best practice: All timestamps must be timezone-aware (TIMESTAMPTZ).
This migration converts every naive timestamp column in the database to
TIMESTAMPTZ and backfills existing rows by interpreting them as UTC.

This is a non-destructive migration:
  - ALTER COLUMN ... TYPE TIMESTAMPTZ USING column AT TIME ZONE 'UTC'
  - PostgreSQL interprets existing naive values as UTC and stores them
    with timezone info. No data is lost or shifted.
  - The migration is idempotent: running it on columns that are already
    TIMESTAMPTZ is a no-op (PostgreSQL handles this gracefully).

Safety:
  - SET lock_timeout = '4s' prevents long table locks
  - Each ALTER is independent; a failure mid-migration leaves partial
    progress that can be resumed
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "ie004"
down_revision = ("ie003_experiment_bandit", "0c9987a05f5d")
branch_labels = None
depends_on = None

# Every table + column pair that needs conversion.
# Format: (table_name, column_name)
TIMESTAMP_COLUMNS = [
    # ── users ──
    ("users", "created_at"),
    ("users", "updated_at"),

    # ── products ──
    ("products", "created_at"),
    ("products", "updated_at"),

    # ── price_recommendations ──
    ("price_recommendations", "created_at"),
    ("price_recommendations", "valid_until"),
    ("price_recommendations", "reviewed_at"),
    ("price_recommendations", "applied_at"),

    # ── recommendation_outcomes (IE Phase 1) ──
    ("recommendation_outcomes", "measured_at"),
    ("recommendation_outcomes", "created_at"),
    ("recommendation_outcomes", "price_applied_at"),
    ("recommendation_outcomes", "decided_at"),
    ("recommendation_outcomes", "measurement_started_at"),
    ("recommendation_outcomes", "measurement_completed_at"),

    # ── pricing_rules ──
    ("pricing_rules", "created_at"),
    ("pricing_rules", "updated_at"),
    ("pricing_rules", "last_triggered_at"),

    # ── pricing_settings ──
    ("pricing_settings", "created_at"),
    ("pricing_settings", "updated_at"),

    # ── price_history ──
    ("price_history", "created_at"),
    ("price_history", "changed_at"),

    # ── sentiment_results ──
    ("sentiment_results", "created_at"),
    ("sentiment_results", "analyzed_at"),

    # ── social_mentions ──
    ("social_mentions", "created_at"),
    ("social_mentions", "collected_at"),
    ("social_mentions", "published_at"),

    # ── competitors ──
    ("competitors", "created_at"),
    ("competitors", "updated_at"),
    ("competitors", "last_scraped_at"),

    # ── competitor_products ──
    ("competitor_products", "created_at"),
    ("competitor_products", "updated_at"),
    ("competitor_products", "last_checked_at"),

    # ── competitor_price_history ──
    ("competitor_price_history", "observed_at"),
    ("competitor_price_history", "created_at"),

    # ── integrations ──
    ("integrations", "created_at"),
    ("integrations", "updated_at"),

    # ── product_integration_links ──
    ("product_integration_links", "created_at"),
    ("product_integration_links", "updated_at"),
    ("product_integration_links", "last_synced_at"),
    ("product_integration_links", "last_price_push_at"),
    ("product_integration_links", "last_sync_verified_at"),

    # ── sync_logs ──
    ("sync_logs", "started_at"),
    ("sync_logs", "completed_at"),
    ("sync_logs", "created_at"),

    # ── subscriptions ──
    ("subscriptions", "created_at"),
    ("subscriptions", "updated_at"),
    ("subscriptions", "current_period_start"),
    ("subscriptions", "current_period_end"),
    ("subscriptions", "cancelled_at"),

    # ── payments ──
    ("payments", "created_at"),
    ("payments", "updated_at"),
    ("payments", "confirmed_at"),
    ("payments", "expires_at"),

    # ── alert_configurations ──
    ("alert_configurations", "created_at"),
    ("alert_configurations", "updated_at"),
    ("alert_configurations", "last_triggered_at"),

    # ── alert_notifications ──
    ("alert_notifications", "created_at"),
    ("alert_notifications", "sent_at"),
    ("alert_notifications", "acknowledged_at"),
    ("alert_notifications", "resolved_at"),

    # ── bandit_state (IE Phase 3) ──
    ("bandit_state", "last_updated"),
    ("bandit_state", "created_at"),

    # ── experiment_assignments (IE Phase 3) ──
    ("experiment_assignments", "assigned_at"),
    ("experiment_assignments", "created_at"),
]


def upgrade() -> None:
    # Prevent long locks on busy tables
    op.execute("SET lock_timeout = '4s'")

    for table, column in TIMESTAMP_COLUMNS:
        # Check if table exists before altering (safety for partial schemas)
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table}'
                    AND column_name = '{column}'
                    AND data_type = 'timestamp without time zone'
                ) THEN
                    ALTER TABLE {table}
                    ALTER COLUMN {column}
                    TYPE TIMESTAMPTZ
                    USING {column} AT TIME ZONE 'UTC';
                END IF;
            END $$;
        """)


def downgrade() -> None:
    # Reversible: convert back to naive timestamps (drops timezone info)
    op.execute("SET lock_timeout = '4s'")

    for table, column in TIMESTAMP_COLUMNS:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table}'
                    AND column_name = '{column}'
                    AND data_type = 'timestamp with time zone'
                ) THEN
                    ALTER TABLE {table}
                    ALTER COLUMN {column}
                    TYPE TIMESTAMP WITHOUT TIME ZONE
                    USING {column} AT TIME ZONE 'UTC';
                END IF;
            END $$;
        """)


        