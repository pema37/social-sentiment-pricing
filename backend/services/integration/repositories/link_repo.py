# backend/services/integration/repositories/link_repo.py

"""
Product Integration Link Repository

Handles all database operations for ProductIntegrationLink model.
Single Responsibility: Only link CRUD operations.

PATCHED (2026-02-21):
- find_by_external_id: Added external_variant_id param for variant-level lookup
- find_any_by_external_product: NEW — sibling variant check (ignores variant_id)
- count_active: Uses COUNT() query instead of loading all rows
- disable_missing: Accepts (product_id, variant_id) tuples
- create/update_prices: No longer commit — caller batches commits
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.integration import ProductIntegrationLink

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time as naive datetime."""
    return datetime.now(UTC)


class LinkRepository:
    """
    Repository for ProductIntegrationLink database operations.

    Lookup key: (integration_id, external_product_id, external_variant_id)

    Note on commits: create() and update_prices() do NOT commit.
    The caller (ProductSyncHandler) batches commits per page for performance.
    Methods that are called standalone (disable_sync, disable_missing)
    DO commit since they have no batching caller.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Lookups ─────────────────────────────────────────────────

    async def find_by_external_id(
        self,
        integration_id: UUID,
        external_product_id: str,
        external_variant_id: str | None = None,
    ) -> ProductIntegrationLink | None:
        """Find a link by integration + external product ID + variant ID.

        FIX: Added external_variant_id param. Without it, a multi-variant
        product's lookup would return an arbitrary variant's link.
        """
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.external_product_id == external_product_id,
        )
        if external_variant_id is not None:
            stmt = stmt.where(ProductIntegrationLink.external_variant_id == external_variant_id)
        else:
            stmt = stmt.where(ProductIntegrationLink.external_variant_id.is_(None))

        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def find_any_by_external_product(
        self,
        integration_id: UUID,
        external_product_id: str,
    ) -> ProductIntegrationLink | None:
        """Find ANY link for this external product (ignoring variant).

        Used to check if a sibling variant already created a Product record.
        For example, if variant "Red" already created a Product, variant "Blue"
        should link to the same Product instead of creating a new one.
        """
        stmt = (
            select(ProductIntegrationLink)
            .where(
                ProductIntegrationLink.integration_id == integration_id,
                ProductIntegrationLink.external_product_id == external_product_id,
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def find_active_by_integration(
        self,
        integration_id: UUID,
    ) -> list[ProductIntegrationLink]:
        """Find all active (sync_enabled=True) links for an integration."""
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.sync_enabled == True,
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_active(self, integration_id: UUID) -> int:
        """Count active links for an integration.

        FIX: Uses COUNT() query instead of loading all rows into memory.
        """
        stmt = select(func.count(ProductIntegrationLink.id)).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.sync_enabled == True,
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    # ─── Create / Update ─────────────────────────────────────────

    async def create(
        self,
        product_id: UUID,
        integration_id: UUID,
        external_product_id: str,
        external_variant_id: str | None,
        external_price: float | None,
        external_compare_at_price: float | None,
    ) -> ProductIntegrationLink:
        """Create a new integration link.

        Does NOT commit — caller batches commits per page.
        """
        link = ProductIntegrationLink(
            product_id=product_id,
            integration_id=integration_id,
            external_product_id=external_product_id,
            external_variant_id=external_variant_id,
            external_price=external_price,
            external_compare_at_price=external_compare_at_price,
            last_price_pull_at=utc_now(),
        )
        self.db.add(link)
        # FIX: Removed commit + refresh. Caller batches commits per page.
        # If caller needs the ID immediately, they should flush().
        return link

    async def update_prices(
        self,
        link: ProductIntegrationLink,
        external_price: float | None,
        external_compare_at_price: float | None,
    ) -> ProductIntegrationLink:
        """Update link with price data from external product.

        Does NOT commit — caller batches commits per page.
        """
        now = utc_now()

        link.external_price = external_price
        link.external_compare_at_price = external_compare_at_price
        link.last_price_pull_at = now
        link.updated_at = now

        self.db.add(link)
        # FIX: Removed commit + refresh. Caller batches commits per page.
        return link

    # ─── Disable / Soft Delete ───────────────────────────────────

    async def disable_sync(self, link: ProductIntegrationLink) -> ProductIntegrationLink:
        """Disable sync for a link (soft delete).

        This IS called standalone (not part of a batch), so it commits.
        """
        link.sync_enabled = False
        link.updated_at = utc_now()
        self.db.add(link)
        await self.db.commit()
        return link

    async def disable_missing(
        self,
        integration_id: UUID,
        seen_link_keys: set,
    ) -> int:
        """Disable sync for links whose external products/variants are gone.

        FIX: Accepts (external_product_id, external_variant_id) tuples
        instead of a flat set of product IDs. This correctly handles
        individual variant deletions — if variant "Red" is removed from
        Shopify but "Blue" still exists, only the Red link is disabled.

        Args:
            integration_id: The integration to check
            seen_link_keys: Set of (external_product_id, external_variant_id) tuples
                seen during the current sync

        Returns:
            Number of links disabled.
        """
        links = await self.find_active_by_integration(integration_id)

        disabled_count = 0
        for link in links:
            # FIX: Check (product_id, variant_id) tuple, not just product_id
            key = (link.external_product_id, link.external_variant_id)
            if key not in seen_link_keys:
                link.sync_enabled = False
                link.updated_at = utc_now()
                self.db.add(link)
                disabled_count += 1

        if disabled_count > 0:
            await self.db.commit()
            logger.info(f"Disabled sync for {disabled_count} deleted products/variants")

        return disabled_count
