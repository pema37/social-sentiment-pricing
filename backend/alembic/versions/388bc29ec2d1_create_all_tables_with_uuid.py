"""create_all_tables_with_uuid

Revision ID: 388bc29ec2d1
Revises:
Create Date: 2025-11-28 09:14:55.657848

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "388bc29ec2d1"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Users table
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=False)

    # Products table
    op.create_table(
        "products",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("base_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("current_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("min_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("max_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("sentiment_multiplier", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("auto_pricing_enabled", sa.Boolean(), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku"),
    )
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=False)
    op.create_index(op.f("ix_products_user_id"), "products", ["user_id"], unique=False)

    # Price history table
    op.create_table(
        "price_history",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        sa.Column("old_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("new_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("change_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("change_reason", sa.String(length=50), nullable=False),
        sa.Column("sentiment_score_at_change", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("sentiment_volume", sa.Integer(), nullable=True),
        sa.Column("triggered_by", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_price_history_product_id"), "price_history", ["product_id"], unique=False)

    # Sentiments table
    op.create_table(
        "sentiments",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("raw_text", sa.String(), nullable=False),
        sa.Column("compound_score", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("positive_score", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("negative_score", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("neutral_score", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sentiments_product_id"), "sentiments", ["product_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_sentiments_product_id"), table_name="sentiments")
    op.drop_table("sentiments")
    op.drop_index(op.f("ix_price_history_product_id"), table_name="price_history")
    op.drop_table("price_history")
    op.drop_index(op.f("ix_products_user_id"), table_name="products")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
