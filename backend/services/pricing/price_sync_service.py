# backend/services/pricing/price_sync_service.py
"""
Price Sync Service - Fetches live prices from connected e-commerce stores.

FIX (2026-01-28) Priority 1: Ensures recommendations show actual store price,
not stale DB data.
"""

import logging
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.product import Product

logger = logging.getLogger(__name__)


class PriceSyncService:
    """Fetches and syncs live prices from e-commerce platforms."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_live_price(
        self,
        product: Product,
        user_id: UUID
    ) -> Optional[Decimal]:
        """
        Fetch current live price from the connected e-commerce store.
        
        Returns:
            Live price as Decimal, or None if unable to fetch
        """
        from models.integration import Integration
        from models.product_link import ProductLink
        
        try:
            link, integration = await self._get_active_link(product.id, user_id)
            if not link:
                return None
            
            live_price = await self._fetch_from_platform(link, integration)
            if live_price:
                logger.debug(f"Fetched live price for product {product.id}: ${live_price}")
            return live_price
            
        except Exception as e:
            logger.warning(f"Failed to fetch live price for product {product.id}: {e}")
            return None
    
    async def sync_product_price(
        self,
        product: Product,
        user_id: UUID
    ) -> bool:
        """
        Sync product price from store to DB if different.
        
        Returns:
            True if price was updated, False otherwise
        """
        live_price = await self.get_live_price(product, user_id)
        
        if live_price is None:
            return False
        
        if live_price != product.current_price:
            logger.info(
                f"Product {product.id} ({product.name}) price mismatch: "
                f"DB=${product.current_price}, Store=${live_price}. Updating."
            )
            product.current_price = live_price
            self.db.add(product)
            await self.db.commit()
            await self.db.refresh(product)
            return True
        
        return False
    
    async def _get_active_link(
        self,
        product_id: UUID,
        user_id: UUID
    ) -> tuple:
        """Get active product link and integration."""
        from models.integration import Integration
        from models.product_link import ProductLink
        
        stmt = (
            select(ProductLink, Integration)
            .join(Integration, ProductLink.integration_id == Integration.id)
            .where(ProductLink.product_id == product_id)
            .where(Integration.user_id == user_id)
            .where(Integration.status == 'active')
            .where(ProductLink.sync_enabled == True)
        )
        result = await self.db.execute(stmt)
        row = result.first()
        
        if not row:
            logger.debug(f"No active integration link for product {product_id}")
            return None, None
        
        return row
    
    async def _fetch_from_platform(
        self,
        link,
        integration
    ) -> Optional[Decimal]:
        """Fetch price from specific platform."""
        if integration.platform == 'shopify':
            return await self._fetch_shopify_price(link, integration)
        elif integration.platform == 'woocommerce':
            return await self._fetch_woocommerce_price(link, integration)
        else:
            logger.warning(f"Unknown platform: {integration.platform}")
            return None
    
    async def _fetch_shopify_price(self, link, integration) -> Optional[Decimal]:
        """Fetch price from Shopify."""
        from services.integration.shopify_service import ShopifyService
        
        service = ShopifyService(self.db, integration)
        live_data = await service.get_product_price(
            link.external_product_id,
            link.external_variant_id
        )
        
        if live_data and live_data.get('price') is not None:
            return Decimal(str(live_data['price']))
        return None
    
    async def _fetch_woocommerce_price(self, link, integration) -> Optional[Decimal]:
        """Fetch price from WooCommerce."""
        from services.integration.woocommerce_service import WooCommerceService
        
        service = WooCommerceService(self.db, integration)
        live_data = await service.get_product_price(link.external_product_id)
        
        if live_data and live_data.get('price') is not None:
            return Decimal(str(live_data['price']))
        return None



        