"""
Shopify Pricing Mixin - Price updates with post-push verification.

Methods:
  - update_price: Push new price to Shopify variant via GraphQL mutation
  - _verify_price_update: Re-fetch product to confirm price was applied

Uses from ShopifyService (via self):
  - _graphql(), _get_shop_domain(), _gid(), _auth_headers()
  - fetch_single_product() (from ShopifyProductsMixin)
  - retry_config, PRICE_VERIFICATION_TOLERANCE

Place at: backend/services/integration/shopify_pricing.py

FIXED (2026-02-22): Replaced deprecated `productVariantUpdate` mutation with
`productVariantsBulkUpdate`. Shopify removed `productVariantUpdate` after
sunsetting API version 2025-10. The new mutation requires `productId` as a
top-level argument alongside a `variants` array.
See: https://shopify.dev/docs/api/admin-graphql/latest/mutations/productVariantsBulkUpdate
"""

import logging
from decimal import Decimal

import httpx

from .circuit_breaker import CircuitOpenError
from .http_client import RetryableClient
from .schemas import (
    PriceUpdateRequest,
    PriceUpdateResponse,
    PriceUpdateResult,
)

logger = logging.getLogger(__name__)


class ShopifyPricingMixin:
    """Price update and verification for ShopifyService."""

    async def update_price(
        self,
        store_url: str,
        access_token: str,
        request: PriceUpdateRequest,
    ) -> PriceUpdateResponse:
        shop_domain = self._get_shop_domain(store_url)

        try:
            # Resolve variant ID
            variant_id = request.external_variant_id
            if not variant_id:
                product = await self.fetch_single_product(store_url, access_token, request.external_product_id)
                if product and product.variants:
                    variant_id = product.variants[0].id
                else:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.PRODUCT_NOT_FOUND,
                        external_product_id=request.external_product_id,
                        error="No variant found",
                    )

            # Get old price
            current = await self.fetch_single_product(store_url, access_token, request.external_product_id)
            old_price = current.price if current else None

            # ══════════════════════════════════════════════════════════════
            # FIX (2026-02-22): Use productVariantsBulkUpdate instead of
            # the removed productVariantUpdate mutation.
            #
            # productVariantUpdate was deprecated when Shopify sunset
            # API version 2025-10. The replacement requires:
            #   - productId (GID) as a top-level argument
            #   - variants array of ProductVariantsBulkInput objects
            #
            # Even for a single variant update, this bulk mutation is
            # the correct approach per Shopify's documentation.
            # ══════════════════════════════════════════════════════════════
            mutation = """
                mutation ProductVariantsBulkUpdate(
                    $productId: ID!,
                    $variants: [ProductVariantsBulkInput!]!
                ) {
                    productVariantsBulkUpdate(
                        productId: $productId,
                        variants: $variants
                    ) {
                        productVariants {
                            id
                            price
                        }
                        userErrors {
                            field
                            message
                        }
                    }
                }
            """

            # Build variant input
            variant_input: dict = {
                "id": self._gid("ProductVariant", variant_id),
                "price": str(request.new_price),
            }
            if request.compare_at_price:
                variant_input["compareAtPrice"] = str(request.compare_at_price)

            variables = {
                "productId": self._gid("Product", request.external_product_id),
                "variants": [variant_input],
            }

            async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as rc:
                data = await self._graphql(rc, shop_domain, access_token, mutation, variables)

            # Check userErrors from mutation
            mutation_result = data.get("productVariantsBulkUpdate") or {}
            user_errors = mutation_result.get("userErrors", [])
            if user_errors:
                msg = "; ".join(e.get("message", "") for e in user_errors)
                return PriceUpdateResponse(
                    result=PriceUpdateResult.FAILED,
                    external_product_id=request.external_product_id,
                    error=f"Shopify rejected update: {msg}",
                )

            # Verify price was actually set
            verification = await self._verify_price_update(
                store_url=store_url,
                access_token=access_token,
                external_product_id=request.external_product_id,
                variant_id=variant_id,
                expected_price=request.new_price,
            )

            if not verification["success"]:
                logger.error(
                    f"Price verification failed for product {request.external_product_id}: "
                    f"expected ${request.new_price}, got ${verification.get('actual_price')}. "
                    f"Reason: {verification.get('error')}"
                )
                return PriceUpdateResponse(
                    result=PriceUpdateResult.FAILED,
                    external_product_id=request.external_product_id,
                    old_price=old_price,
                    new_price=request.new_price,
                    error=f"Price verification failed: {verification.get('error')}",
                )

            logger.info(
                f"Price update verified for product {request.external_product_id}: ${old_price} -> ${request.new_price}"
            )
            return PriceUpdateResponse(
                result=PriceUpdateResult.SUCCESS,
                external_product_id=request.external_product_id,
                old_price=old_price,
                new_price=request.new_price,
            )

        except CircuitOpenError:
            return PriceUpdateResponse(
                result=PriceUpdateResult.FAILED,
                external_product_id=request.external_product_id,
                error="Service temporarily unavailable",
            )
        except httpx.HTTPStatusError as e:
            result_map = {
                401: PriceUpdateResult.UNAUTHORIZED,
                404: PriceUpdateResult.PRODUCT_NOT_FOUND,
                429: PriceUpdateResult.RATE_LIMITED,
            }
            return PriceUpdateResponse(
                result=result_map.get(e.response.status_code, PriceUpdateResult.FAILED),
                external_product_id=request.external_product_id,
                error=f"HTTP {e.response.status_code}",
            )
        except (httpx.RequestError, ValueError) as e:
            return PriceUpdateResponse(
                result=PriceUpdateResult.FAILED,
                external_product_id=request.external_product_id,
                error=str(e),
            )

    async def _verify_price_update(
        self,
        store_url: str,
        access_token: str,
        external_product_id: str,
        variant_id: str,
        expected_price: Decimal,
    ) -> dict:
        """Verify that a price update was actually applied in Shopify."""
        try:
            updated_product = await self.fetch_single_product(store_url, access_token, external_product_id)
            if not updated_product:
                return {"success": False, "actual_price": None, "error": "Could not fetch product after update"}

            actual_price = None
            if updated_product.variants:
                for variant in updated_product.variants:
                    if str(variant.id) == str(variant_id):
                        actual_price = variant.price
                        break

            if actual_price is None:
                actual_price = updated_product.price
            if actual_price is None:
                return {"success": False, "actual_price": None, "error": "Product has no price after update"}

            actual_price = Decimal(str(actual_price))
            expected_price = Decimal(str(expected_price))

            diff = actual_price - expected_price
            # Only tolerate upward rounding (e.g. $19.99 → $20.00).
            # Downward differences (actual < expected) indicate a wrong price.
            if Decimal("0") <= diff <= self.PRICE_VERIFICATION_TOLERANCE:
                return {"success": True, "actual_price": actual_price, "error": None}
            return {
                "success": False,
                "actual_price": actual_price,
                "error": f"Expected ${expected_price}, but Shopify shows ${actual_price}",
            }
        except Exception as e:
            logger.exception(f"Error verifying price update for product {external_product_id}")
            return {"success": False, "actual_price": None, "error": f"Verification error: {e!s}"}
