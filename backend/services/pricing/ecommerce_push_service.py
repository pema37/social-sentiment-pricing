# backend/services/pricing/ecommerce_push_service.py
"""
E-commerce Push Service - Handles pushing prices to connected platforms.

Supports multi-platform: pushes to ALL active integrations for a product.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.product import Product
from models.integration import Integration, ProductIntegrationLink, IntegrationStatus

logger = logging.getLogger(__name__)


class EcommercePushService:
    """Handles pushing price updates to e-commerce platforms."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def push_price(self, product: Product) -> dict:
        """
        Push price update to ALL connected e-commerce platforms.
        
        Returns:
            dict with success status, platforms pushed, and details
        """
        from core.encryption import decrypt_token
        from services.integration.shopify_service import ShopifyService
        from services.integration.woocommerce_service import WooCommerceService
        from services.integration.base import PriceUpdateRequest, PriceUpdateResult
        
        try:
            # Get ALL active product integration links (not just the first one!)
            stmt = (
                select(ProductIntegrationLink)
                .join(Integration, ProductIntegrationLink.integration_id == Integration.id)
                .where(ProductIntegrationLink.product_id == product.id)
                .where(ProductIntegrationLink.sync_enabled == True)
                .where(Integration.status == IntegrationStatus.ACTIVE)
            )
            result = await self.db.execute(stmt)
            links = list(result.scalars().all())
            
            if not links:
                logger.warning(f"Product {product.id} not linked to any ACTIVE platform")
                return {
                    "platform": None, 
                    "success": False, 
                    "error": "Product not linked to any active platform",
                    "error_code": "NO_ACTIVE_INTEGRATION_LINK"
                }
            
            # Push to EACH active platform
            push_results = []
            for link in links:
                single_result = await self._push_to_platform(product, link)
                push_results.append(single_result)
            
            # Aggregate results
            successful = [r for r in push_results if r["success"]]
            failed = [r for r in push_results if not r["success"]]
            overall_success = len(successful) > 0
            
            # Build summary
            platforms_pushed = [r["platform"] for r in successful]
            platforms_failed = [f"{r['platform']}: {r['error']}" for r in failed]
            
            if overall_success:
                return {
                    "platform": ", ".join(platforms_pushed),
                    "success": True,
                    "platforms_pushed": len(successful),
                    "platforms_failed": len(failed),
                    "details": push_results,
                }
            else:
                return {
                    "platform": None,
                    "success": False,
                    "error": f"All platforms failed: {'; '.join(platforms_failed)}",
                    "error_code": "ALL_PLATFORMS_FAILED",
                    "details": push_results,
                }
            
        except Exception as e:
            logger.exception(f"Error pushing to e-commerce for product {product.id}")
            return {
                "platform": None, 
                "success": False, 
                "error": str(e),
                "error_code": "EXCEPTION"
            }

    async def _push_to_platform(self, product: Product, link: ProductIntegrationLink) -> dict:
        """Push price update to a single e-commerce platform."""
        from core.encryption import decrypt_token
        from services.integration.shopify_service import ShopifyService
        from services.integration.woocommerce_service import WooCommerceService
        from services.integration.base import PriceUpdateRequest, PriceUpdateResult
        
        try:
            # Get the integration
            integration = await self.db.get(Integration, link.integration_id)
            
            if not integration:
                return {
                    "platform": "unknown", 
                    "success": False, 
                    "error": "Integration not found",
                    "error_code": "INTEGRATION_NOT_FOUND"
                }
            
            platform_name = integration.platform.value
            
            # Double-check status (should already be filtered, but be safe)
            if integration.status != IntegrationStatus.ACTIVE:
                return {
                    "platform": platform_name, 
                    "success": False, 
                    "error": f"Integration status: {integration.status.value}",
                    "error_code": "INTEGRATION_INACTIVE"
                }
            
            # Decrypt access token
            try:
                access_token = decrypt_token(integration.access_token_encrypted)
            except Exception as e:
                return {
                    "platform": platform_name, 
                    "success": False, 
                    "error": f"Failed to decrypt token: {str(e)}",
                    "error_code": "TOKEN_DECRYPT_FAILED"
                }
            
            # Build price update request
            request = PriceUpdateRequest(
                external_product_id=link.external_product_id,
                external_variant_id=link.external_variant_id,
                new_price=float(product.current_price),
            )
            
            # Call appropriate service
            if platform_name == "shopify":
                service = ShopifyService()
                response = await service.update_price(
                    store_url=integration.store_url,
                    access_token=access_token,
                    request=request
                )
            elif platform_name == "woocommerce":
                service = WooCommerceService()
                response = await service.update_price(
                    store_url=integration.store_url,
                    access_token=access_token,
                    request=request
                )
            else:
                return {
                    "platform": platform_name, 
                    "success": False, 
                    "error": "Unsupported platform",
                    "error_code": "UNSUPPORTED_PLATFORM"
                }
            
            # Update link metadata on success
            if response.result == PriceUpdateResult.SUCCESS:
                link.last_price_push_at = datetime.utcnow()
                link.external_price = Decimal(str(product.current_price))
                link.updated_at = datetime.utcnow()
                self.db.add(link)
                
                return {
                    "platform": platform_name,
                    "success": True,
                    "external_id": link.external_product_id,
                    "new_price": float(product.current_price),
                    "old_price": response.old_price,
                }
            else:
                return {
                    "platform": platform_name,
                    "success": False,
                    "external_id": link.external_product_id,
                    "error": response.error,
                    "error_code": "API_ERROR",
                }
                
        except Exception as e:
            logger.exception(f"Error pushing to platform for link {link.id}")
            return {
                "platform": "unknown", 
                "success": False, 
                "error": str(e),
                "error_code": "EXCEPTION"
            }
        


        