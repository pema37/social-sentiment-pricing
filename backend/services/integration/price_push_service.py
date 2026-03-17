# backend/services/integration/price_push_service.py

"""
Price Push Service - PUSH operations

Pushes price changes FROM SSP TO e-commerce platforms.

PATCHED: Added error codes for frontend handling (Issue 2 fix)

PATCHED (2026-02-21):
- Added optional external_variant_id param for variant-level targeting
- push_all_pending_prices now handles multiple variant links per product
- Cleaned up unused List import
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.encryption import decrypt_token
from models.integration import (
    Integration,
    IntegrationStatus,
    ProductIntegrationLink,
)
from models.product import Product

from .schemas import PriceUpdateRequest, PriceUpdateResult
from .sync_service import SyncService  # Reuse get_service()

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time as naive datetime."""
    return datetime.now(UTC)


class PricePushService:
    """
    Pushes price changes to e-commerce platforms.

    Methods:
    - push_price_to_platform: Push single product price (optionally variant-specific)
    - push_all_pending_prices: Push all products with price differences
    - check_product_can_push: Frontend preflight check
    """

    PUSH_TIMEOUT_SECONDS = 30

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_integration(self, integration_id: UUID, user_id: UUID | None) -> Integration:
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
        user_id: UUID | None = None,
        external_variant_id: str | None = None,
    ) -> dict:
        """
        Push a price update to the e-commerce platform.

        Args:
            integration_id: Target integration
            product_id: SSP product ID
            new_price: New price to push
            user_id: Optional owner filter
            external_variant_id: Optional. If provided, targets this specific
                variant. If not, picks the first enabled link (backward compat).

        Returns:
            dict with result details including error_code for frontend
        """
        try:
            integration = await self._get_integration(integration_id, user_id)
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg.lower():
                return {
                    "success": False,
                    "product_id": str(product_id),
                    "error": "Store integration not found",
                    "error_code": "INTEGRATION_NOT_FOUND",
                    "suggestion": "Reconnect your store in the Integrations page.",
                }
            elif "not active" in error_msg.lower():
                return {
                    "success": False,
                    "product_id": str(product_id),
                    "error": "Store integration is not active",
                    "error_code": "INTEGRATION_INACTIVE",
                    "suggestion": "Check your store connection status in Integrations.",
                }
            raise

        # FIX: Build link query with optional variant filter
        stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration_id,
            ProductIntegrationLink.product_id == product_id,
            ProductIntegrationLink.sync_enabled == True,
        )
        if external_variant_id is not None:
            stmt = stmt.where(ProductIntegrationLink.external_variant_id == external_variant_id)

        result = await self.db.execute(stmt)
        link = result.scalars().first()

        if not link:
            # Check if link exists but sync is disabled
            stmt_check = select(ProductIntegrationLink).where(
                ProductIntegrationLink.integration_id == integration_id,
                ProductIntegrationLink.product_id == product_id,
            )
            if external_variant_id is not None:
                stmt_check = stmt_check.where(ProductIntegrationLink.external_variant_id == external_variant_id)
            result_check = await self.db.execute(stmt_check)
            link_disabled = result_check.scalars().first()

            if link_disabled:
                logger.warning(f"Sync disabled for product {product_id}")
                return {
                    "success": False,
                    "product_id": str(product_id),
                    "error": "Price sync is disabled for this product",
                    "error_code": "SYNC_DISABLED",
                    "suggestion": "Enable sync for this product in the Integrations page.",
                }

            logger.error(f"No ProductIntegrationLink for product {product_id}")
            return {
                "success": False,
                "product_id": str(product_id),
                "error": "Product not linked to store. Please sync your products first.",
                "error_code": "MISSING_INTEGRATION_LINK",
                "suggestion": "Go to Integrations → Your Store → Sync Products",
            }

        service = SyncService.get_service(integration.platform)

        try:
            access_token = decrypt_token(integration.access_token_encrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for integration {integration_id}: {e}")
            return {
                "success": False,
                "product_id": str(product_id),
                "error": "Failed to decrypt store credentials",
                "error_code": "CREDENTIAL_ERROR",
                "suggestion": "Reconnect your store to refresh credentials.",
            }

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
                timeout=self.PUSH_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.error(f"Price push timed out for product {product_id}")
            return {
                "success": False,
                "product_id": str(product_id),
                "error": "Request timed out - store not responding",
                "error_code": "TIMEOUT",
                "suggestion": "Your store may be slow. Please try again later.",
            }

        if response.result == PriceUpdateResult.SUCCESS:
            now = utc_now()
            link.last_price_push_at = now
            link.external_price = new_price
            link.updated_at = now
            self.db.add(link)

            # Also update the product's current_price (pricing engine owns this)
            stmt = select(Product).where(Product.id == product_id)
            result = await self.db.execute(stmt)
            product = result.scalars().first()
            if product:
                product.current_price = new_price
                product.updated_at = now
                self.db.add(product)

            await self.db.commit()

            logger.info(
                f"Price pushed to {integration.platform.value}: "
                f"product={product_id}, variant={link.external_variant_id}, price={new_price}"
            )

            return {
                "success": True,
                "product_id": str(product_id),
                "external_product_id": link.external_product_id,
                "external_variant_id": link.external_variant_id,
                "old_price": float(response.old_price) if response.old_price else None,
                "new_price": new_price,
            }
        else:
            error_code = "UPDATE_FAILED"
            suggestion = "Check your store and try again."

            if response.result == PriceUpdateResult.UNAUTHORIZED:
                error_code = "INVALID_CREDENTIALS"
                suggestion = "Your store credentials have expired. Please reconnect your store."
            elif response.result == PriceUpdateResult.PRODUCT_NOT_FOUND:
                error_code = "PRODUCT_NOT_FOUND_IN_STORE"
                suggestion = "This product may have been deleted from your store. Re-sync products."
            elif response.result == PriceUpdateResult.RATE_LIMITED:
                error_code = "RATE_LIMITED"
                suggestion = "Too many requests to your store. Please wait a few minutes."

            logger.error(f"Price push failed for product {product_id}: {response.error} (code: {error_code})")

            return {
                "success": False,
                "product_id": str(product_id),
                "external_product_id": link.external_product_id,
                "external_variant_id": link.external_variant_id,
                "error": response.error or response.result.value,
                "error_code": error_code,
                "suggestion": suggestion,
            }

    async def push_all_pending_prices(
        self,
        integration_id: UUID,
        user_id: UUID | None = None,
    ) -> dict:
        """
        Push all products where local price differs from external price.

        FIX: Now iterates over variant-level links, so each variant gets
        pushed individually with the correct external_variant_id.

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
        errors: list[dict] = []

        for link, product in links_with_products:
            local_price = float(product.current_price) if product.current_price else 0
            external_price = float(link.external_price) if link.external_price else 0

            # Skip if prices match (within $0.01)
            if abs(local_price - external_price) < 0.01:
                skipped += 1
                continue

            try:
                # FIX: Pass external_variant_id so each variant link is targeted correctly
                push_result = await self.push_price_to_platform(
                    integration_id=integration_id,
                    product_id=product.id,
                    new_price=local_price,
                    user_id=user_id,
                    external_variant_id=link.external_variant_id,
                )

                if push_result["success"]:
                    pushed += 1
                else:
                    failed += 1
                    errors.append(
                        {
                            "product_id": str(product.id),
                            "product_name": product.name,
                            "external_variant_id": link.external_variant_id,
                            "error": push_result.get("error"),
                            "error_code": push_result.get("error_code"),
                        }
                    )

            except Exception as e:
                logger.error(f"Failed to push price for product {product.id}: {e}")
                failed += 1
                errors.append(
                    {
                        "product_id": str(product.id),
                        "product_name": product.name,
                        "external_variant_id": link.external_variant_id,
                        "error": str(e),
                        "error_code": "UNKNOWN_ERROR",
                    }
                )

        logger.info(
            f"Price push completed for {integration.store_url}: pushed={pushed}, failed={failed}, skipped={skipped}"
        )

        return {
            "total": len(links_with_products),
            "pushed": pushed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors[:10],
        }

    async def check_product_can_push(
        self,
        product_id: UUID,
        user_id: UUID,
    ) -> dict:
        """
        Check if a product is ready for price push.

        Useful for frontend to show status before attempting push.
        Returns details about what's missing if not ready.
        """
        int_stmt = select(Integration).where(
            Integration.user_id == user_id,
            Integration.status == IntegrationStatus.ACTIVE,
        )
        int_result = await self.db.execute(int_stmt)
        integrations = list(int_result.scalars().all())

        if not integrations:
            return {
                "ready": False,
                "error_code": "NO_ACTIVE_INTEGRATION",
                "message": "No active store connection found.",
                "suggestion": "Connect your WooCommerce or Shopify store first.",
            }

        link_stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.product_id == product_id,
            ProductIntegrationLink.integration_id.in_([i.id for i in integrations]),
        )
        link_result = await self.db.execute(link_stmt)
        link = link_result.scalars().first()

        if not link:
            return {
                "ready": False,
                "error_code": "MISSING_INTEGRATION_LINK",
                "message": "Product not linked to store.",
                "suggestion": "Go to Integrations → Your Store → Sync Products",
            }

        if not link.sync_enabled:
            return {
                "ready": False,
                "error_code": "SYNC_DISABLED",
                "message": "Price sync is disabled for this product.",
                "suggestion": "Enable sync in the product's integration settings.",
            }

        integration = next((i for i in integrations if i.id == link.integration_id), None)

        return {
            "ready": True,
            "integration_id": str(link.integration_id),
            "platform": integration.platform.value if integration else None,
            "store_url": integration.store_url if integration else None,
            "external_product_id": link.external_product_id,
            "external_variant_id": link.external_variant_id,
            "last_push_at": link.last_price_push_at.isoformat() if link.last_price_push_at else None,
            "current_external_price": link.external_price,
        }
