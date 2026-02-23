# backend/services/integration/handlers/product_sync_handler.py

"""
Product Sync Handler

Contains the business logic for syncing products from external platforms.
Uses repositories for data access - keeps business logic separate from DB operations.

Key features:
- One link per variant (not per product)
- Sibling variant check before creating new Products
- Explicit field ownership (PLATFORM_OWNED vs SSP_OWNED)
- Never overwrites SSP-owned fields during sync
- Paginates through external products with batched commits
- Tracks sync progress with cursors

PATCHED (2026-02-21):
- Variant-aware sync: one link per variant, not per product
- Removed SKU fallback matching — uses external IDs only
- Never overwrites current_price during sync (pricing engine owns it)
- Batched commits per page instead of per product
- Tracks (product_id, variant_id) tuples for deletion detection

PATCHED (2026-02-22):
- Explicit field ownership separation (PLATFORM_OWNED_FIELDS / SSP_OWNED_FIELDS)
- SKU: only set on create, never overwrite merchant's value
- base_price: now synced from Shopify (Shopify-owned anchor price)
- _update_existing respects field ownership strictly
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


# ═══════════════════════════════════════════════════════════════════════════════
# FIELD OWNERSHIP
#
# Defines which system "owns" each Product field during sync.
# Platform-owned fields are updated from Shopify/WooCommerce on every sync.
# SSP-owned fields are NEVER touched by sync — they belong to the merchant
# or the pricing engine.
#
# This prevents the class of bugs where a sync silently overwrites data
# that the merchant or pricing engine intentionally set.
# ═══════════════════════════════════════════════════════════════════════════════

# Updated from Shopify/WooCommerce on every sync
PLATFORM_OWNED_FIELDS = {
    "name",           # Product title — always matches Shopify
    "base_price",     # Merchant's list price — pricing engine anchor
    # Future: "description", "category", "image_url"
}

# Set ONCE on product creation, never overwritten by sync
SET_ONCE_FIELDS = {
    "sku",            # Set from Shopify on import, merchant owns after that
}

# NEVER touched by sync — owned by ActualPrice systems or merchant config
SSP_OWNED_FIELDS = {
    "current_price",          # Owned by pricing engine
    "min_price",              # Merchant guardrail
    "max_price",              # Merchant guardrail
    "cost",                   # Merchant input
    "sentiment_multiplier",   # Merchant/system config
    "auto_pricing_enabled",   # Merchant preference
    "keywords",               # Merchant/system config
    "is_active",              # Merchant control
}


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
    - Respect field ownership (see PLATFORM_OWNED_FIELDS, SSP_OWNED_FIELDS)
    
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
            
            integration.sync_cursor = cursor
            self.db.add(integration)
            await self.db.commit()
        
        if sync_type == "full":
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
        
        One link per variant, not one per product.
        Does NOT commit — caller batches commits per page.
        
        Returns:
            Tuple of (created, updated) counts
        """
        created, updated = 0, 0
        
        variants = external_product.variants or []
        if not variants:
            existing_link = await self.link_repo.find_by_external_id(
                integration.id,
                external_product.id,
                external_variant_id=None,
            )
            if existing_link:
                return await self._update_existing(
                    existing_link, external_product,
                    variant_price=external_product.price,
                )
            return await self._create_or_link(
                integration, external_product,
                variant_id=None,
                variant_sku=external_product.sku,
                variant_price=external_product.price,
                variant_compare_at_price=external_product.compare_at_price,
            )
        
        for variant in variants:
            existing_link = await self.link_repo.find_by_external_id(
                integration.id,
                external_product.id,
                external_variant_id=variant.id,
            )
            if existing_link:
                c, u = await self._update_existing(
                    existing_link, external_product,
                    variant_price=variant.price,
                )
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
        variant_price: Optional[float] = None,
    ) -> Tuple[int, int]:
        """Update existing product and link respecting field ownership.
        
        FIELD OWNERSHIP RULES:
        - PLATFORM_OWNED_FIELDS: update from Shopify if changed
        - SET_ONCE_FIELDS: never overwrite (merchant owns after import)
        - SSP_OWNED_FIELDS: never touch
        
        Does NOT commit — caller batches commits per page.
        """
        product = await self.product_repo.find_by_id(link.product_id)
        
        if not product:
            logger.warning(f"Product {link.product_id} not found for link, skipping update")
            return 0, 0
        
        update_kwargs = {}
        
        # ── PLATFORM_OWNED_FIELDS: always sync from Shopify ──
        if external_product.title and external_product.title != product.name:
            update_kwargs["name"] = external_product.title
        
        if variant_price is not None and variant_price != float(product.base_price):
            update_kwargs["base_price"] = variant_price
        
        # ── SET_ONCE_FIELDS: only fill if empty ──
        # SKU: merchant owns it after import. Only populate if currently blank.
        if not product.sku and external_product.sku:
            update_kwargs["sku"] = external_product.sku
        
        # ── SSP_OWNED_FIELDS: never touched ──
        # current_price, min_price, max_price, cost, sentiment_multiplier,
        # auto_pricing_enabled, keywords, is_active — all untouched.
        
        if update_kwargs:
            await self.product_repo.update(product, **update_kwargs)
        
        # Update link prices (platform-owned data on the link)
        await self.link_repo.update_prices(
            link,
            external_price=variant_price,
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
        
        Uses external IDs only for matching (no SKU fallback).
        Checks sibling variants before creating new Products.
        
        Does NOT commit — caller batches commits per page.
        """
        sku = variant_sku or self._generate_sku(integration.platform, external_product)
        if variant_id and not variant_sku:
            sku = f"{integration.platform.value.upper()}-{variant_id}"
        
        # Check if another variant of same product already created a Product
        sibling_link = await self.link_repo.find_any_by_external_product(
            integration.id,
            external_product.id,
        )
        
        if sibling_link:
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
    


    