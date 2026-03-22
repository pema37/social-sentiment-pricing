"""add ondelete cascades to FK relationships

Revision ID: fk_ondelete_001
Revises: eb1b1cb111ad
Create Date: 2026-03-22

Adds ON DELETE CASCADE / SET NULL to FK constraints that were missing
ondelete rules. Without these, deleting a user or product either raises
a constraint violation or leaves orphaned rows.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fk_ondelete_001"
down_revision: Union[str, Sequence[str], None] = "eb1b1cb111ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _replace_fk(table, column, ref_table, ref_column, ondelete, constraint_name):
    """Drop old FK and recreate with ondelete rule."""
    # Drop the existing FK constraint by naming convention
    op.drop_constraint(constraint_name, table, type_="foreignkey")
    op.create_foreign_key(
        constraint_name, table, ref_table, [column], [ref_column], ondelete=ondelete
    )


def upgrade() -> None:
    # --- integrations.user_id → CASCADE ---
    _replace_fk(
        "integrations", "user_id", "users", "id",
        "CASCADE", "integrations_user_id_fkey",
    )

    # --- integration_sync_logs.integration_id → CASCADE ---
    _replace_fk(
        "integration_sync_logs", "integration_id", "integrations", "id",
        "CASCADE", "integration_sync_logs_integration_id_fkey",
    )

    # --- product_integration_links.product_id → CASCADE ---
    _replace_fk(
        "product_integration_links", "product_id", "products", "id",
        "CASCADE", "product_integration_links_product_id_fkey",
    )

    # --- product_integration_links.integration_id → CASCADE ---
    _replace_fk(
        "product_integration_links", "integration_id", "integrations", "id",
        "CASCADE", "product_integration_links_integration_id_fkey",
    )

    # --- products.user_id → CASCADE ---
    _replace_fk(
        "products", "user_id", "users", "id",
        "CASCADE", "products_user_id_fkey",
    )

    # --- social_mentions.user_id → CASCADE ---
    _replace_fk(
        "social_mentions", "user_id", "users", "id",
        "CASCADE", "social_mentions_user_id_fkey",
    )

    # --- social_mentions.product_id → SET NULL ---
    _replace_fk(
        "social_mentions", "product_id", "products", "id",
        "SET NULL", "social_mentions_product_id_fkey",
    )

    # --- sentiments.product_id → CASCADE ---
    _replace_fk(
        "sentiments", "product_id", "products", "id",
        "CASCADE", "sentiments_product_id_fkey",
    )

    # --- alert_configurations.user_id → CASCADE ---
    _replace_fk(
        "alert_configurations", "user_id", "users", "id",
        "CASCADE", "alert_configurations_user_id_fkey",
    )

    # --- alerts.user_id → CASCADE ---
    _replace_fk(
        "alerts", "user_id", "users", "id",
        "CASCADE", "alerts_user_id_fkey",
    )

    # --- alerts.configuration_id → SET NULL ---
    _replace_fk(
        "alerts", "configuration_id", "alert_configurations", "id",
        "SET NULL", "alerts_configuration_id_fkey",
    )

    # --- alerts.product_id → SET NULL ---
    _replace_fk(
        "alerts", "product_id", "products", "id",
        "SET NULL", "alerts_product_id_fkey",
    )

    # --- alerts.competitor_id → SET NULL ---
    _replace_fk(
        "alerts", "competitor_id", "competitors", "id",
        "SET NULL", "alerts_competitor_id_fkey",
    )

    # --- alerts.recommendation_id → SET NULL ---
    _replace_fk(
        "alerts", "recommendation_id", "price_recommendations", "id",
        "SET NULL", "alerts_recommendation_id_fkey",
    )


def downgrade() -> None:
    """Remove ondelete rules (revert to no action)."""
    _replace_fk("alerts", "recommendation_id", "price_recommendations", "id", None, "alerts_recommendation_id_fkey")
    _replace_fk("alerts", "competitor_id", "competitors", "id", None, "alerts_competitor_id_fkey")
    _replace_fk("alerts", "product_id", "products", "id", None, "alerts_product_id_fkey")
    _replace_fk("alerts", "configuration_id", "alert_configurations", "id", None, "alerts_configuration_id_fkey")
    _replace_fk("alerts", "user_id", "users", "id", None, "alerts_user_id_fkey")
    _replace_fk("alert_configurations", "user_id", "users", "id", None, "alert_configurations_user_id_fkey")
    _replace_fk("sentiments", "product_id", "products", "id", None, "sentiments_product_id_fkey")
    _replace_fk("social_mentions", "product_id", "products", "id", None, "social_mentions_product_id_fkey")
    _replace_fk("social_mentions", "user_id", "users", "id", None, "social_mentions_user_id_fkey")
    _replace_fk("products", "user_id", "users", "id", None, "products_user_id_fkey")
    _replace_fk("product_integration_links", "integration_id", "integrations", "id", None, "product_integration_links_integration_id_fkey")
    _replace_fk("product_integration_links", "product_id", "products", "id", None, "product_integration_links_product_id_fkey")
    _replace_fk("integration_sync_logs", "integration_id", "integrations", "id", None, "integration_sync_logs_integration_id_fkey")
    _replace_fk("integrations", "user_id", "users", "id", None, "integrations_user_id_fkey")
