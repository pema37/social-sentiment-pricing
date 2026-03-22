# backend/services/pricing/ecommerce_push_service.py
"""
E-commerce Push Service - Handles pushing prices to connected platforms.

Supports multi-platform: pushes to ALL active integrations for a product.

PATCHED (2026-02-21):
- Added missing db.commit() after updating link metadata on successful push
- Fixed Decimal → float type mismatch on external_price assignment
- Moved imports to module level
- Reuse cached service instances instead of re-instantiating per push
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.encryption import decrypt_token
from models.integration import (
    EcommercePlatform,
    Integration,
    IntegrationStatus,
    ProductIntegrationLink,
)
from models.product import Product
from services.integration.base import (
    EcommerceService,
    PriceUpdateRequest,
    PriceUpdateResult,
)
from services.integration.shopify_service import ShopifyService
from services.integration.woocommerce_service import WooCommerceService

logger = logging.getLogger(__name__)


class EcommercePushService:
    """Handles pushing price updates to e-commerce platforms."""

    # Cached service instances (same pattern as SyncService)
    _services: dict[EcommercePlatform, EcommerceService] = {}

    def __init__(self, db: AsyncSession):
        self.db = db

    @classmethod
    def _get_service(cls, platform: EcommercePlatform) -> EcommerceService:
        """Get the appropriate e-commerce service (cached)."""
        if platform not in cls._services:
            if platform == EcommercePlatform.SHOPIFY:
                cls._services[platform] = ShopifyService()
            elif platform == EcommercePlatform.WOOCOMMERCE:
                cls._services[platform] = WooCommerceService()
            else:
                raise ValueError(f"Unsupported platform: {platform}")
        return cls._services[platform]

    async def push_price(self, product: Product) -> dict:
        """
        Push price update to ALL connected e-commerce platforms.

        Returns:
            dict with success status, platforms pushed, and details
        """
        try:
            # Get ALL active product integration links
            stmt = (
                select(ProductIntegrationLink)
                .join(Integration, ProductIntegrationLink.integration_id == Integration.id)
                .where(ProductIntegrationLink.product_id == product.id)
                .where(ProductIntegrationLink.sync_enabled)
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
                    "error_code": "NO_ACTIVE_INTEGRATION_LINK",
                }

            # Push to EACH active platform/variant link
            push_results = []
            for link in links:
                single_result = await self._push_to_platform(product, link)
                push_results.append(single_result)

            # Flush link metadata updates (last_price_push_at, external_price)
            # after all pushes. Using flush() instead of commit() so the caller
            # (auto_approve_and_apply) controls the transaction boundary.
            # This keeps product price change + link metadata + approval status
            # in a single atomic commit.
            try:
                await self.db.flush()
            except Exception as flush_err:
                logger.error(
                    f"Failed to flush link metadata for product {product.id}: {flush_err}"
                )
                await self.db.rollback()
                return {
                    "platform": None,
                    "success": False,
                    "error": f"Metadata update failed after platform push: {flush_err}",
                    "error_code": "METADATA_FLUSH_FAILED",
                    "details": push_results,
                }

            # Aggregate results
            successful = [r for r in push_results if r["success"]]
            failed = [r for r in push_results if not r["success"]]
            overall_success = len(successful) > 0

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
                "error_code": "EXCEPTION",
            }

    async def _push_to_platform(self, product: Product, link: ProductIntegrationLink) -> dict:
        """Push price update to a single e-commerce platform/variant link."""
        try:
            integration = await self.db.get(Integration, link.integration_id)

            if not integration:
                return {
                    "platform": "unknown",
                    "success": False,
                    "error": "Integration not found",
                    "error_code": "INTEGRATION_NOT_FOUND",
                }

            platform_name = integration.platform.value

            if integration.status != IntegrationStatus.ACTIVE:
                return {
                    "platform": platform_name,
                    "success": False,
                    "error": f"Integration status: {integration.status.value}",
                    "error_code": "INTEGRATION_INACTIVE",
                }

            try:
                access_token = decrypt_token(integration.access_token_encrypted)
            except Exception as e:
                return {
                    "platform": platform_name,
                    "success": False,
                    "error": f"Failed to decrypt token: {e!s}",
                    "error_code": "TOKEN_DECRYPT_FAILED",
                }

            # Build price update request (includes variant_id for variant-level targeting)
            request = PriceUpdateRequest(
                external_product_id=link.external_product_id,
                external_variant_id=link.external_variant_id,
                new_price=float(product.current_price),
            )

            # FIX: Use cached service instance instead of re-instantiating
            try:
                service = self._get_service(integration.platform)
            except ValueError:
                return {
                    "platform": platform_name,
                    "success": False,
                    "error": "Unsupported platform",
                    "error_code": "UNSUPPORTED_PLATFORM",
                }

            response = await service.update_price(
                store_url=integration.store_url,
                access_token=access_token,
                request=request,
            )

            if response.result == PriceUpdateResult.SUCCESS:
                now = datetime.now(UTC)
                link.last_price_push_at = now
                # FIX: Use float, not Decimal. Model field is Optional[float].
                link.external_price = float(product.current_price)
                link.updated_at = now
                self.db.add(link)
                # Note: commit happens in push_price() after all links are processed

                return {
                    "platform": platform_name,
                    "success": True,
                    "external_id": link.external_product_id,
                    "external_variant_id": link.external_variant_id,
                    "new_price": float(product.current_price),
                    "old_price": response.old_price,
                }
            else:
                return {
                    "platform": platform_name,
                    "success": False,
                    "external_id": link.external_product_id,
                    "external_variant_id": link.external_variant_id,
                    "error": response.error,
                    "error_code": "API_ERROR",
                }

        except Exception as e:
            logger.exception(f"Error pushing to platform for link {link.id}")
            return {
                "platform": "unknown",
                "success": False,
                "error": str(e),
                "error_code": "EXCEPTION",
            }
