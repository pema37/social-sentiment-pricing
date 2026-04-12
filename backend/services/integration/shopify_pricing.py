"""
Shopify Pricing Mixin - Price updates with post-push verification.

Methods:
  - update_price: Push new price to Shopify variant via GraphQL mutation
  - _verify_price_update: Re-fetch product to confirm price was applied

Uses from ShopifyService (via self):
  - _graphql(), _get_shop_domain(), _gid(), _auth_headers()
  - fetch_single_product() (from ShopifyProductsMixin)
  - retry_config, PRICE_VERIFICATION_TOLERANCE

FIXED (2026-02-22): Replaced deprecated `productVariantUpdate` mutation with
`productVariantsBulkUpdate`. Shopify removed `productVariantUpdate` after
sunsetting API version 2025-10. The new mutation requires `productId` as a
top-level argument alongside a `variants` array.
See: https://shopify.dev/docs/api/admin-graphql/latest/mutations/productVariantsBulkUpdate

FIXED (2026-03-29): AP-003 — Three verification bugs resolved:

BUG 1 — Verification direction: diff = actual - expected then checked >= 0
  only passed when actual >= expected. Any float representation where
  actual < expected by even $0.001 caused false failure. Fixed: use abs(diff)
  with symmetric tolerance on both sides.

BUG 2 — No delay before re-fetch: Shopify GraphQL has propagation delay.
  Re-fetching immediately returned the old price, causing false verification
  failure even on successful mutations. Fixed: asyncio.sleep(1.5) before
  re-fetch (minimal delay, avoids most propagation lag without slowing the
  approval flow significantly).

BUG 3 — Scope errors buried in generic FAILED: userErrors containing a
  permissions error (write_products scope missing) returned PriceUpdateResult.FAILED
  with no signal for the caller to surface a reconnect/re-auth CTA.
  Fixed: scan userErrors for "ACCESS_DENIED" / "unauthorized" and return
  PriceUpdateResult.UNAUTHORIZED so approval_service can surface the right error.
"""

import asyncio
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

# Seconds to wait before re-fetching after a mutation.
# Shopify GraphQL has propagation delay — immediate re-fetch can return stale data.
_VERIFICATION_DELAY_SECONDS = 1.5


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
            # Resolve variant ID and capture old price in a single fetch.
            variant_id = request.external_variant_id
            if not variant_id:
                product = await self.fetch_single_product(store_url, access_token, request.external_product_id)
                if product and product.variants:
                    variant_id = product.variants[0].id
                    old_price = product.price
                else:
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.PRODUCT_NOT_FOUND,
                        external_product_id=request.external_product_id,
                        error="No variant found",
                    )
            else:
                current = await self.fetch_single_product(store_url, access_token, request.external_product_id)
                old_price = current.price if current else None

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
                            code
                        }
                    }
                }
            """

            variant_input = {
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

            mutation_result = data.get("productVariantsBulkUpdate") or {}
            user_errors = mutation_result.get("userErrors", [])

            if user_errors:
                # AP-003 BUG 3: Detect scope/permission errors specifically.
                # "code": "ACCESS_DENIED" or message containing "unauthorized"
                # means write_products scope is missing — surface UNAUTHORIZED
                # so the caller can show a reconnect CTA, not a generic error.
                is_auth_error = any(
                    e.get("code", "").upper() in ("ACCESS_DENIED", "UNAUTHORIZED")
                    or "unauthorized" in e.get("message", "").lower()
                    or "access" in e.get("message", "").lower()
                    for e in user_errors
                )
                msg = "; ".join(e.get("message", "") for e in user_errors)

                if is_auth_error:
                    logger.warning(
                        f"Shopify price update rejected — scope/permission error "
                        f"for product {request.external_product_id}: {msg}. "
                        "Merchant may need to reconnect to grant write_products scope."
                    )
                    return PriceUpdateResponse(
                        result=PriceUpdateResult.UNAUTHORIZED,
                        external_product_id=request.external_product_id,
                        error=f"Missing write_products scope — reconnect required: {msg}",
                    )

                return PriceUpdateResponse(
                    result=PriceUpdateResult.FAILED,
                    external_product_id=request.external_product_id,
                    error=f"Shopify rejected update: {msg}",
                )

            # AP-003 BUG 2: Wait for Shopify propagation before re-fetching.
            await asyncio.sleep(_VERIFICATION_DELAY_SECONDS)

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
        """
        Verify that a price update was actually applied in Shopify.

        AP-003 BUG 1 FIX: Use abs(diff) with symmetric tolerance.
        The original check (0 <= diff <= tolerance) only passed when
        actual >= expected, causing false failures when Shopify returned
        a float like 19.989999 for an expected 19.99.
        """
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

            actual_decimal = Decimal(str(actual_price))
            expected_decimal = Decimal(str(expected_price))

            # FIX: symmetric abs() tolerance — passes for both upward and
            # downward float representation differences within $0.02.
            diff = abs(actual_decimal - expected_decimal)
            if diff <= self.PRICE_VERIFICATION_TOLERANCE:
                return {"success": True, "actual_price": actual_decimal, "error": None}

            return {
                "success": False,
                "actual_price": actual_decimal,
                "error": f"Expected ${expected_decimal}, but Shopify shows ${actual_decimal} (diff ${diff})",
            }
        except Exception as e:
            logger.exception(f"Error verifying price update for product {external_product_id}")
            return {"success": False, "actual_price": None, "error": f"Verification error: {e!s}"}
        


        