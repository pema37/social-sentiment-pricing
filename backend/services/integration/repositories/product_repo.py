# backend/services/integration/repositories/product_repo.py

"""
Product Repository

Handles all database operations for Product model.
Single Responsibility: Only Product CRUD operations.

PATCHED (2026-02-21):
- create(): Uses flush() instead of commit() for batch compatibility
- update(): No longer commits — caller batches commits per page

PATCHED (2026-02-22):
- update(): Added base_price param (Shopify-owned, synced from platform)
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.product import Product

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time as naive datetime."""
    return datetime.now(UTC)


class ProductRepository:
    """
    Repository for Product database operations.

    Note on commits: create() and update() do NOT commit.
    The caller (ProductSyncHandler) batches commits per page for performance.
    Callers outside the sync flow (e.g., API routes) must commit themselves.

    Methods:
    - find_by_id: Get product by UUID
    - find_by_sku: Get product by SKU for a user
    - create: Create new product (flush only — caller commits)
    - update: Update existing product (no commit — caller commits)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_id(self, product_id: UUID) -> Product | None:
        """Find a product by its ID."""
        return await self.db.get(Product, product_id)

    async def find_by_sku(self, user_id: UUID, sku: str) -> Product | None:
        """Find a product by SKU for a specific user."""
        stmt = select(Product).where(
            Product.user_id == user_id,
            Product.sku == sku,
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def create(
        self,
        user_id: UUID,
        name: str,
        sku: str,
        base_price: float,
        current_price: float,
        description: str | None = None,
        category: str | None = None,
        image_url: str | None = None,
    ) -> Product:
        """Create a new product.

        Uses flush() to get the generated ID without committing.
        Caller is responsible for committing (batched per page).
        """
        product = Product(
            user_id=user_id,
            name=name,
            sku=sku,
            description=description,
            category=category,
            image_url=image_url,
            base_price=base_price,
            current_price=current_price,
            cost=None,
        )
        self.db.add(product)
        await self.db.flush()
        return product

    async def update(
        self,
        product: Product,
        name: str | None = None,
        sku: str | None = None,
        current_price: float | None = None,
        base_price: float | None = None,
    ) -> Product:
        """Update an existing product.

        Only updates fields that are explicitly passed (not None).
        Does NOT commit — caller batches commits per page.

        Field ownership (enforced by caller, not here):
        - name: platform-owned (Shopify sync updates this)
        - sku: set-once (only filled if empty)
        - base_price: platform-owned (Shopify sync updates this)
        - current_price: SSP-owned (pricing engine only)
        """
        if name is not None:
            product.name = name
        if sku is not None:
            product.sku = sku
        if current_price is not None:
            product.current_price = current_price
        if base_price is not None:
            product.base_price = base_price

        product.updated_at = utc_now()
        self.db.add(product)
        return product
