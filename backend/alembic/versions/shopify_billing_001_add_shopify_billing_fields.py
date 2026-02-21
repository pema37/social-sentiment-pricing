"""Add Shopify billing fields to subscriptions

Revision ID: shopify_billing_001
Revises: REPLACE_WITH_YOUR_LATEST_REVISION
Create Date: 2026-02-20

Adds shopify_charge_id and shopify_plan_name columns to the subscriptions table
for Shopify Billing API support. Both columns are nullable — only populated
for merchants who subscribe via the Shopify App Store.
"""
from alembic import op
import sqlalchemy as sa


# IMPORTANT: Replace this with your actual latest revision ID.
# Run: alembic heads
# to find it.
revision = "shopify_billing_001"
down_revision = None  # <-- REPLACE with output of `alembic heads`
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("shopify_charge_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("shopify_plan_name", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "shopify_plan_name")
    op.drop_column("subscriptions", "shopify_charge_id")

    