# backend/services/integration/price_push_service.py

"""
Price Push Service - PUSH operations

Pushes price changes FROM SSP TO e-commerce platforms.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.integration import (
    Integration,
    ProductIntegrationLink,
    IntegrationStatus,
    EcommercePlatform,
)
from models.product import Product
from core.encryption import decrypt_token

from .models import PriceUpdateRequest, PriceUpdateResult
from .sync_service import SyncService  # Reuse get_service()

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time as naive datetime."""
    return datetime.utcnow()


class PricePushService:
    """
    Pushes price changes to e-commerce platforms.
    
    Methods:
    - push_price_to_platform: Push single product price
    - push_all_pending_prices: Push all products with price differences
    """
    
    PUSH_TIMEOUT_SECONDS = 30
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def _get_integration(self, integration_id: UUID, user_id: Optional[UUID]) -> Integration:
        """Fetch and validate integration."""
        query = select(Integration).where(Integration.id == integration_id)
        if user_id:
            query = query.where(Integration.user_id == user_id)
        
        result = await self.db.execute(query)
        integration = result.scalars().first()
        
        if not integration:
            raise ValueError("Integration not found")
        if integration.status != IntegrationStatus.ACTIVE:
            raise ValueError("Integration is not active")
        
        return integration
    
    async def push_price_to_platform(
        self,
        integration_id: UUID,
        product_id: UUID,
        new_price: float,
        user_id: Optional[UUID] = None,
    ) -> dict:
        """
        Push a price update to the e-commerce platform.
        
        Returns:
            dict with result details
        """
        integration = await self._get_integration(integration_id, user_id)
        
        # Get the product link
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.product_id == product_id,
            ProductIntegrationLink.sync_enabled == True,
        )
        result = await self.db.execute(stmt)
        link = result.scalars().first()
        
        if not link:
            raise ValueError(f"No active integration link for product {product_id}")
        
        service = SyncService.get_service(integration.platform)
        access_token = decrypt_token(integration.access_token_encrypted)
        
        request = PriceUpdateRequest(
            external_product_id=link.external_product_id,
            external_variant_id=link.external_variant_id,
            new_price=new_price,
        )
        
        try:
            response = await asyncio.wait_for(
                service.update_price(
                    store_url=integration.store_url,
                    access_token=access_token,
                    request=request,
                ),
                timeout=self.PUSH_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            logger.error(f"Price push timed out for product {product_id}")
            return {
                "success": False,
                "product_id": str(product_id),
                "error": "Request timed out",
            }
        
        if response.result == PriceUpdateResult.SUCCESS:
            link.last_price_push_at = utc_now()
            link.external_price = new_price
            self.db.add(link)
            await self.db.commit()
            
            logger.info(f"Price pushed to {integration.platform.value}: product={product_id}, price={new_price}")
            
            return {
                "success": True,
                "product_id": str(product_id),
                "external_product_id": link.external_product_id,
                "old_price": float(response.old_price) if response.old_price else None,
                "new_price": new_price,
            }
        else:
            logger.error(f"Price push failed for product {product_id}: {response.error}")
            return {
                "success": False,
                "product_id": str(product_id),
                "external_product_id": link.external_product_id,
                "error": response.error or response.result.value,
            }
    
    async def push_all_pending_prices(
        self,
        integration_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> dict:
        """
        Push all products where local price differs from external price.
        
        Returns:
            dict with summary of results
        """
        integration = await self._get_integration(integration_id, user_id)
        
        stmt = (
            select(ProductIntegrationLink, Product)
            .join(Product, ProductIntegrationLink.product_id == Product.id)
            .where(ProductIntegrationLink.integration_id == integration_id)
            .where(ProductIntegrationLink.sync_enabled == True)
        )
        result = await self.db.execute(stmt)
        links_with_products = result.all()
        
        pushed = 0
        failed = 0
        skipped = 0
        errors: List[dict] = []
        
        for link, product in links_with_products:
            local_price = float(product.current_price) if product.current_price else 0
            external_price = float(link.external_price) if link.external_price else 0
            
            # Skip if prices match (within $0.01)
            if abs(local_price - external_price) < 0.01:
                skipped += 1
                continue
            
            try:
                push_result = await self.push_price_to_platform(
                    integration_id=integration_id,
                    product_id=product.id,
                    new_price=local_price,
                    user_id=user_id,
                )
                
                if push_result["success"]:
                    pushed += 1
                else:
                    failed += 1
                    errors.append({
                        "product_id": str(product.id),
                        "product_name": product.name,
                        "error": push_result.get("error"),
                    })
                    
            except Exception as e:
                logger.error(f"Failed to push price for product {product.id}: {e}")
                failed += 1
                errors.append({
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "error": str(e),
                })
        
        logger.info(f"Price push completed for {integration.store_url}: pushed={pushed}, failed={failed}, skipped={skipped}")
        
        return {
            "total": len(links_with_products),
            "pushed": pushed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors[:10],
        }
    
    