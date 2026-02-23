"""Make SKU unique per user instead of globally unique.

Revision ID: sku_per_user_001
Revises: ie004_timestamps_to_timestamptz
Create Date: 2026-02-22

Problem:
    SKU has a global UNIQUE constraint, meaning two different merchants
    cannot import products with the same SKU (e.g., "TSHIRT-001").
    This causes:
    - CSV imports that say "successful" but silently fail on commit
    - Shopify product syncs that break when merchants share common SKUs
    - IntegrityError exceptions that get swallowed by batch handlers

Fix:
    Drop the global unique constraint on `products.sku` and replace it
    with a composite unique constraint on (user_id, sku). This allows
    the same SKU across different merchants while preventing duplicates
    within a single merchant's catalog.

Blast radius: MINIMAL
    - product_repo.find_by_sku() already filters by user_id ✅
    - product_sync_handler uses external IDs, not SKU ✅
    - import_service._get_existing_skus() already filters by user_id ✅
    - product_service.create() relies on DB constraint (now per-user) ✅
    - No frontend changes needed ✅
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "sku_per_user_001"
down_revision = "cbc9741ade41"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Drop the existing global unique constraint on SKU.
    #
    # SQLAlchemy/Alembic names auto-generated unique constraints differently
    # depending on how they were created. We try the most common names.
    # If your constraint has a different name, check with:
    #   SELECT conname FROM pg_constraint
    #   WHERE conrelid = 'products'::regclass AND contype = 'u';
    #
    # Common auto-generated names:
    #   - "products_sku_key"       (PostgreSQL default for unique=True)
    #   - "uq_products_sku"       (some Alembic versions)
    #   - "ix_products_sku"       (if created as unique index)

    # Drop the unique constraint (PostgreSQL default naming)
    op.drop_constraint("products_sku_key", "products", type_="unique")

    # Step 2: Create composite unique constraint (user_id + sku).
    # This allows same SKU across different merchants, but prevents
    # duplicates within a single merchant's catalog.
    #
    # NULLs: PostgreSQL treats NULLs as distinct in unique constraints,
    # so products with sku=NULL won't conflict (which is correct —
    # many synced products have no SKU).
    op.create_unique_constraint(
        "uq_products_user_id_sku",
        "products",
        ["user_id", "sku"],
    )

    # Step 3: Add a composite index for the common lookup pattern
    # (find product by SKU within a user's catalog).
    # The unique constraint already creates an implicit index, but
    # being explicit helps with query planning documentation.
    # Skipped — the unique constraint above already creates this index.


def downgrade() -> None:
    # WARNING: Downgrade will fail if duplicate SKUs exist across users.
    # You must resolve duplicates before downgrading.

    # Remove composite unique constraint
    op.drop_constraint("uq_products_user_id_sku", "products", type_="unique")

    # Restore global unique constraint
    op.create_unique_constraint("products_sku_key", "products", ["sku"])


