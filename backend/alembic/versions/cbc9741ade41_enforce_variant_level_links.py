"""enforce_variant_level_links

Revision ID: cbc9741ade41
Revises: shopify_billing_001
Create Date: 2026-02-21 15:57:30.305020

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cbc9741ade41"
down_revision: str | Sequence[str] | None = "shopify_billing_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE product_integration_links
        SET external_variant_id = external_product_id
        WHERE external_variant_id IS NULL
    """)

    op.create_index(
        "uq_link_integration_product_variant",
        "product_integration_links",
        ["integration_id", "external_product_id", "external_variant_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_link_integration_product_variant", "product_integration_links")
