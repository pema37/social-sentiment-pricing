# backend/services/integration/handlers/product_sync_handler.py

"""
Product Sync Handler

Contains the business logic for syncing products from external platforms.
Uses repositories for data access - keeps business logic separate from DB operations.

Key features:
- One link per variant (not per product)
- Sibling variant check before creating new Products
- Never overwrites current_price (owned by pricing engine)
- Paginates through external products with batched commits
- Tracks sync progress with cursors

PATCHED (2026-02-21):
- Variant-aware sync: one link per variant, not per product
- Removed SKU fallback matching — uses external IDs only
- Never overwrites current_price during sync (pricing engine owns it)
- Batched commits per page instead of per product
- Tracks (product_id, variant_id) tuples for deletion detection
"""

import logging
from datetime import datetime, UTC
from typing import Optional, Tuple
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
    - Upsert products with one link per variant
    - Handle sibling variants (multiple variants → same Product)
    - Track sync progress with cursors
    - Never overwrite pricing-engine-owned fields
    
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
    
    # ─── Main sync orchestration ─────────────────────────────────
    
    async def sync_all_products(
        self,
        integration: Integration,
        sync_type: str,
    ) -> Tuple[int, int, int]:
        """
        Sync all products from external platform.
        
        Commits are batched per page (100 products) for performance.
        Tracks (external_product_id, external_variant_id) tuples for
        accurate deletion detection of individual variants.
        
        Args:
            integration: The integration to sync
            sync_type: "full" or "incremental"
            
        Returns:
            Tuple of (created, updated, deleted) counts
        """
        service = self.get_service(integration.platform)
        access_token = decrypt_token(integration.access_token_encrypted)
        
        created, updated, deleted = 0, 0, 0
        # FIX: Track (product_id, variant_id) tuples instead of just product_id
        seen_link_keys: set = set()
        
        cursor = integration.sync_cursor if sync_type == "incremental" else None
        
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
            
            for external_product in result.products:
                # FIX: Track all variant keys for deletion detection
                if external_product.variants:
                    for variant in external_product.variants:
                        seen_link_keys.add((external_product.id, variant.id))
                else:
                    seen_link_keys.add((external_product.id, None))
                
                c, u = await self.upsert_product(integration, external_product)
                created += c
                updated += u
            
            cursor = result.next_cursor
            has_more = result.has_more
            
            # FIX: Single commit per page — covers all upserts in this batch
            integration.sync_cursor = cursor
            self.db.add(integration)
            await self.db.commit()
        
        if sync_type == "full":
            # FIX: Pass tuples to disable_missing
            deleted = await self.link_repo.disable_missing(
                integration.id,
                seen_link_keys,
            )
        
        return created, updated, deleted
    
    # ─── Product upsert logic ────────────────────────────────────
    
    async def upsert_product(
        self,
        integration: Integration,
        external_product: ExternalProduct,
    ) -> Tuple[int, int]:
        """
        Create or update product variant links from external data.
        
        FIX: One link per variant, not one per product.
        Does NOT commit — caller batches commits per page.
        
        Returns:
            Tuple of (created, updated) counts
        """
        created, updated = 0, 0
        
        variants = external_product.variants or []
        if not variants:
            # No variants — single product-level link
            existing_link = await self.link_repo.find_by_external_id(
                integration.id,
                external_product.id,
                external_variant_id=None,
            )
            if existing_link:
                return await self._update_existing(existing_link, external_product)
            return await self._create_or_link(
                integration, external_product,
                variant_id=None,
                variant_sku=external_product.sku,
                variant_price=external_product.price,
                variant_compare_at_price=external_product.compare_at_price,
            )
        
        # FIX: One link per variant
        for variant in variants:
            existing_link = await self.link_repo.find_by_external_id(
                integration.id,
                external_product.id,
                external_variant_id=variant.id,
            )
            if existing_link:
                c, u = await self._update_existing(existing_link, external_product)
            else:
                c, u = await self._create_or_link(
                    integration, external_product,
                    variant_id=variant.id,
                    variant_sku=variant.sku,
                    variant_price=variant.price,
                    variant_compare_at_price=getattr(variant, 'compare_at_price', None),
                )
            created += c
            updated += u
        
        return created, updated
    
    async def _update_existing(
        self,
        link,
        external_product: ExternalProduct,
    ) -> Tuple[int, int]:
        """Update existing product and link.
        
        RULES:
        - Only update platform-owned fields (name, sku)
        - NEVER overwrite current_price (owned by pricing engine)
        - Only write Product if something actually changed
        
        Does NOT commit — caller batches commits per page.
        """
        product = await self.product_repo.find_by_id(link.product_id)
        
        if not product:
            logger.warning(f"Product {link.product_id} not found for link, skipping update")
            return 0, 0
        
        # FIX: Only update platform-owned fields, NEVER current_price
        update_kwargs = {}
        if external_product.title and external_product.title != product.name:
            update_kwargs["name"] = external_product.title
        if external_product.sku and external_product.sku != product.sku:
            update_kwargs["sku"] = external_product.sku
        
        # REMOVED: current_price=external_product.price
        # current_price is owned by the pricing engine, not platform sync.
        
        if update_kwargs:
            await self.product_repo.update(product, **update_kwargs)
        
        # Update link prices (platform-owned data on the link)
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
        variant_id: Optional[str] = None,
        variant_sku: Optional[str] = None,
        variant_price: Optional[float] = None,
        variant_compare_at_price: Optional[float] = None,
    ) -> Tuple[int, int]:
        """Create new product or link new variant to existing product.
        
        FIX: Removed SKU fallback matching — uses external IDs only.
        FIX: Added sibling variant check (same external product, different variant).
        
        Does NOT commit — caller batches commits per page.
        """
        sku = variant_sku or self._generate_sku(integration.platform, external_product)
        if variant_id and not variant_sku:
            sku = f"{integration.platform.value.upper()}-{variant_id}"
        
        # REMOVED: find_by_sku fallback
        # ADDED: Check if another variant of same product already created a Product
        sibling_link = await self.link_repo.find_any_by_external_product(
            integration.id,
            external_product.id,
        )
        
        if sibling_link:
            # Product already exists via another variant — just add this variant's link
            logger.info(
                f"Product for {external_product.id} exists (via sibling variant), "
                f"adding variant link {variant_id}"
            )
            await self.link_repo.create(
                product_id=sibling_link.product_id,
                integration_id=integration.id,
                external_product_id=external_product.id,
                external_variant_id=variant_id,
                external_price=variant_price,
                external_compare_at_price=variant_compare_at_price,
            )
            return 0, 1
        
        # No product exists — create Product + first variant link
        product = await self.product_repo.create(
            user_id=integration.user_id,
            name=external_product.title,
            sku=sku,
            base_price=variant_price or 0.0,
            current_price=variant_price or 0.0,
        )
        
        await self.link_repo.create(
            product_id=product.id,
            integration_id=integration.id,
            external_product_id=external_product.id,
            external_variant_id=variant_id,
            external_price=variant_price,
            external_compare_at_price=variant_compare_at_price,
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



        