# backend/services/integration/handlers/product_sync_handler.py

"""
Product Sync Handler

Contains the business logic for syncing products from external platforms.
Uses repositories for data access - keeps business logic separate from DB operations.

Key features:
- Handles SKU conflicts gracefully (links to existing product if SKU exists)
- Paginates through external products
- Tracks sync progress with cursors

ADDED (2026-03-28): upsert_products() — accepts a pre-fetched list of
  ExternalProduct objects and upserts them in bulk. Called by the parallel
  chunk tasks in sync_tasks.py. Each chunk task fetches its own page from
  Shopify and passes the result here so the handler only owns DB logic,
  not pagination.
"""

import logging
from datetime import datetime, UTC
from typing import Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.integration import Integration, EcommercePlatform
from core.encryption import decrypt_token

from ..schemas import ExternalProduct
from ..base import EcommerceService
from ..shopify_service import ShopifyService
from ..woocommerce_service import WooCommerceService
from ..repositories import ProductRepository, LinkRepository

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time as naive datetime."""
    return datetime.now(UTC)


class SyncError(Exception):
    """Base exception for sync errors."""
    pass


class ProductSyncHandler:
    """
    Handles product synchronization business logic.

    Responsibilities:
    - Fetch products from external platforms
    - Upsert products (create or update)
    - Handle SKU conflicts gracefully
    - Track sync progress with cursors

    Uses repository pattern for all database operations.
    """

    # Service instances (cached at class level)
    _services: dict[EcommercePlatform, EcommerceService] = {}

    def __init__(
        self,
        db: AsyncSession,
        product_repo: ProductRepository,
        link_repo: LinkRepository,
    ):
        self.db = db
        self.product_repo = product_repo
        self.link_repo = link_repo

    @classmethod
    def get_service(cls, platform: EcommercePlatform) -> EcommerceService:
        """Get the appropriate e-commerce service (cached)."""
        if platform not in cls._services:
            if platform == EcommercePlatform.SHOPIFY:
                cls._services[platform] = ShopifyService()
            elif platform == EcommercePlatform.WOOCOMMERCE:
                cls._services[platform] = WooCommerceService()
            else:
                raise ValueError(f"Unsupported platform: {platform}")
        return cls._services[platform]

    async def sync_all_products(
        self,
        integration: Integration,
        sync_type: str,
    ) -> Tuple[int, int, int]:
        """
        Sync all products from external platform.

        Used by:
        - WooCommerce (always single-pass)
        - Small Shopify stores (≤ 1 page / ≤ CHUNK_SIZE products)

        For large Shopify stores the parallel chunk path in sync_tasks.py
        calls fetch_product_cursors() + upsert_products() instead.

        Args:
            integration: The integration to sync
            sync_type: "full" or "incremental"

        Returns:
            Tuple of (created, updated, deleted) counts
        """
        service = self.get_service(integration.platform)
        access_token = decrypt_token(integration.access_token_encrypted)

        created, updated, deleted = 0, 0, 0
        seen_external_ids = set()

        # Determine starting cursor
        cursor = integration.sync_cursor if sync_type == "incremental" else None

        # Paginate through all products
        has_more = True
        while has_more:
            result = await service.fetch_products(
                store_url=integration.store_url,
                access_token=access_token,
                cursor=cursor,
                limit=100,
            )

            if not result.success:
                raise SyncError(f"Failed to fetch products: {result.error}")

            # Process each product
            for external_product in result.products:
                seen_external_ids.add(external_product.id)
                c, u = await self.upsert_product(integration, external_product)
                created += c
                updated += u

            # Update cursor and check for more
            cursor = result.next_cursor
            has_more = result.has_more

            # Save cursor progress
            integration.sync_cursor = cursor
            self.db.add(integration)
            await self.db.commit()

        # Handle deletions (only for full sync)
        if sync_type == "full":
            deleted = await self.link_repo.disable_missing(
                integration.id,
                seen_external_ids,
            )

        return created, updated, deleted

    async def upsert_products(
        self,
        integration: Integration,
        external_products: list[ExternalProduct],
    ) -> Tuple[int, int, int]:
        """
        Upsert a pre-fetched list of ExternalProduct objects into the local DB.

        Called by sync_tasks.sync_integration_products_chunk after it has
        already fetched one page from Shopify via fetch_products(cursor=cursor).

        The chunk task owns pagination; this method owns DB upsert logic.
        Deletion is NOT performed here — deletions only run at the end of a
        full sync once all chunks have completed (handled in
        sync_integration_products_complete if needed, or left for the next
        scheduled full sync).

        Args:
            integration:       The integration being synced.
            external_products: Pre-fetched list of ExternalProduct from one page.

        Returns:
            Tuple of (created, updated, deleted) — deleted is always 0 here
            because partial-chunk deletion would be incorrect.
        """
        created = 0
        updated = 0

        for external_product in external_products:
            try:
                c, u = await self.upsert_product(integration, external_product)
                created += c
                updated += u
            except Exception as exc:
                # Log and continue — one bad product should not abort the chunk.
                # The chunk task's retry logic handles transient failures at
                # the Shopify API level; individual product failures are logged
                # and skipped to maximise sync coverage.
                logger.error(
                    "upsert_products: failed to upsert product %s: %s",
                    getattr(external_product, "id", "unknown"),
                    exc,
                )

        return created, updated, 0

    async def upsert_product(
        self,
        integration: Integration,
        external_product: ExternalProduct,
    ) -> Tuple[int, int]:
        """
        Create or update a product from external data.

        Logic:
        1. Check if link exists → update existing product
        2. Check if SKU exists → create link to existing product
        3. Otherwise → create new product and link

        Returns:
            Tuple of (created, updated) - one will be 1, other 0
        """
        # Check for existing link first
        existing_link = await self.link_repo.find_by_external_id(
            integration.id,
            external_product.id,
        )

        if existing_link:
            return await self._update_existing(existing_link, external_product)

        return await self._create_or_link(integration, external_product)

    async def _update_existing(
        self,
        link,
        external_product: ExternalProduct,
    ) -> Tuple[int, int]:
        """Update existing product and link."""
        product = await self.product_repo.find_by_id(link.product_id)

        if not product:
            logger.warning(f"Product {link.product_id} not found for link, skipping update")
            return 0, 0

        # Update product
        await self.product_repo.update(
            product,
            name=external_product.title,
            sku=external_product.sku or product.sku,
            current_price=external_product.price or product.current_price,
        )

        # Set before update_prices so the commit inside the repo persists it
        link.sync_enabled = True
        await self.link_repo.update_prices(
            link,
            external_price=external_product.price,
            external_compare_at_price=external_product.compare_at_price,
        )

        return 0, 1

    async def _create_or_link(
        self,
        integration: Integration,
        external_product: ExternalProduct,
    ) -> Tuple[int, int]:
        """Create new product or link to existing one with same SKU."""
        sku = self._generate_sku(integration.platform, external_product)

        # Check if product with this SKU already exists for this user
        existing_product = await self.product_repo.find_by_sku(
            integration.user_id,
            sku,
        )

        if existing_product:
            # Product exists - just create the link
            logger.info(f"Product with SKU {sku} already exists, creating link only")

            variant_id = None
            if external_product.variants:
                variant_id = external_product.variants[0].id

            await self.link_repo.create(
                product_id=existing_product.id,
                integration_id=integration.id,
                external_product_id=external_product.id,
                external_variant_id=variant_id,
                external_price=external_product.price,
                external_compare_at_price=external_product.compare_at_price,
                sync_enabled=True,
            )

            return 0, 1  # Count as update since product existed

        # Create new product
        product = await self.product_repo.create(
            user_id=integration.user_id,
            name=external_product.title,
            sku=sku,
            base_price=external_product.price or 0.0,
            current_price=external_product.price or 0.0,
        )

        # Create link
        variant_id = None
        if external_product.variants:
            variant_id = external_product.variants[0].id

        await self.link_repo.create(
            product_id=product.id,
            integration_id=integration.id,
            external_product_id=external_product.id,
            external_variant_id=variant_id,
            external_price=external_product.price,
            external_compare_at_price=external_product.compare_at_price,
            sync_enabled=True,
        )

        return 1, 0

    def _generate_sku(
        self,
        platform: EcommercePlatform,
        external_product: ExternalProduct,
    ) -> str:
        """Generate SKU from external product or create a default one."""
        if external_product.sku:
            return external_product.sku
        return f"{platform.value.upper()}-{external_product.id}"
    


    