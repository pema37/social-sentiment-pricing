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
"""

import logging
from decimal import Decimal
from typing import Optional

import httpx

from .schemas import (
    PriceUpdateRequest,
    PriceUpdateResponse,
    PriceUpdateResult,
)
from .http_client import RetryableClient
from .circuit_breaker import CircuitOpenError

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
                product = await self.fetch_single_product(
                    store_url, access_token, request.external_product_id
                )
                if product and product.variants:
                    variant_id = product.variants[0].id
                else:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.PRODUCT_NOT_FOUND,
                        external_product_id=request.external_product_id,
                        error="No variant found",
                    )

            # Get old price
            current = await self.fetch_single_product(
                store_url, access_token, request.external_product_id
            )
            old_price = current.price if current else None

            # GraphQL mutation
            mutation = """
                mutation VariantUpdate($input: ProductVariantInput!) {
                    productVariantUpdate(input: $input) {
                        productVariant { id price }
                        userErrors { field message }
                    }
                }
            """
            variant_input: dict = {
                "id": self._gid("ProductVariant", variant_id),
                "price": str(request.new_price),
            }
            if request.compare_at_price:
                variant_input["compareAtPrice"] = str(request.compare_at_price)

            async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as rc:
                data = await self._graphql(
                    rc, shop_domain, access_token, mutation, {"input": variant_input}
                )

            # Check userErrors from mutation
            user_errors = (data.get("productVariantUpdate") or {}).get("userErrors", [])
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
                f"Price update verified for product {request.external_product_id}: "
                f"${old_price} -> ${request.new_price}"
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
            updated_product = await self.fetch_single_product(
                store_url, access_token, external_product_id
            )
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

            if abs(actual_price - expected_price) <= self.PRICE_VERIFICATION_TOLERANCE:
                return {"success": True, "actual_price": actual_price, "error": None}
            return {
                "success": False,
                "actual_price": actual_price,
                "error": f"Expected ${expected_price}, but Shopify shows ${actual_price}",
            }
        except Exception as e:
            logger.exception(f"Error verifying price update for product {external_product_id}")
            return {"success": False, "actual_price": None, "error": f"Verification error: {str(e)}"}
        

        