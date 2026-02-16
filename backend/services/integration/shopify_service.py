# backend/services/integration/shopify_service.py

"""
Shopify Integration Service.

MIGRATED (2026-02-15): REST Admin API → GraphQL Admin API
Shopify requires all new apps to use GraphQL as of April 2025.
https://shopify.dev/docs/apps/build/graphql/migrate

PATCHED (2025-01-07): Added price verification after push to detect
when Shopify silently rejects or modifies price updates.

FIXED (2026-02-16): _graphql() now routes through RetryableClient
instead of bypassing it via raw httpx.AsyncClient. This restores
retry, rate limiting, and circuit breaker protections.
"""

import hmac
import hashlib
import base64
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from urllib.parse import urlencode

import httpx

from core.config import settings
from .base import EcommerceService
from .schemas import (
    OAuthResult,
    ExternalProduct,
    ExternalProductVariant,
    ProductSyncResult,
    PriceUpdateRequest,
    PriceUpdateResponse,
    PriceUpdateResult,
    WebhookRegistration,
    ConnectionStatus,
)
from .retry import RetryConfig, execute_with_retry
from .http_client import RetryableClient
from .circuit_breaker import CircuitOpenError

logger = logging.getLogger(__name__)


class ShopifyService(EcommerceService):
    """
    Shopify GraphQL Admin API integration.

    Migrated from REST to GraphQL per Shopify requirement (April 2025).
    All admin calls go to: POST /admin/api/{version}/graphql.json

    Rate Limits: 1,000 cost points per second (throttled query cost)
    """

    API_VERSION = "2024-01"
    REQUIRED_SCOPES = ["read_products", "write_products"]
    WEBHOOK_TOPICS = ["products/create", "products/update", "products/delete"]

    # GraphQL webhook topics use SCREAMING_SNAKE format
    WEBHOOK_TOPICS_GQL = ["PRODUCTS_CREATE", "PRODUCTS_UPDATE", "PRODUCTS_DELETE"]

    # Price verification tolerance (rounding: $19.999 -> $20.00)
    PRICE_VERIFICATION_TOLERANCE = Decimal("0.02")

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        config = retry_config or RetryConfig(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
        )
        super().__init__(config)

    @property
    def platform_name(self) -> str:
        return "shopify"

    # ================================================================
    # GraphQL helpers
    # ================================================================

    def _graphql_url(self, shop_domain: str) -> str:
        """Single endpoint for ALL Shopify Admin API calls."""
        return f"https://{shop_domain}/admin/api/{self.API_VERSION}/graphql.json"

    async def _graphql(
        self,
        rc: RetryableClient,
        shop_domain: str,
        access_token: str,
        query: str,
        variables: Optional[dict] = None,
    ) -> dict:
        """
        Execute a GraphQL query/mutation against Shopify Admin API.

        Routes through RetryableClient.post() so every call gets:
        - Automatic retries with exponential backoff
        - Rate limit tracking & wait-if-needed
        - Circuit breaker protection

        Args:
            rc: RetryableClient instance (uses rc.post(), NOT rc._client)
            shop_domain: e.g. "mystore.myshopify.com"
            access_token: Shopify access token
            query: GraphQL query or mutation string
            variables: Optional dict of variables

        Returns:
            The "data" portion of the GraphQL response.

        Raises:
            httpx.HTTPStatusError: on HTTP-level failures (401, 429, etc.)
            ValueError: if GraphQL returns top-level errors
        """
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables

        # rc.post() handles retry, rate limit, circuit breaker, AND raise_for_status()
        response = await rc.post(
            self._graphql_url(shop_domain),
            headers=self._auth_headers(access_token),
            json=payload,
        )
        body = response.json()

        # Top-level GraphQL errors (syntax, auth, throttled, etc.)
        if body.get("errors"):
            msgs = "; ".join(e.get("message", "") for e in body["errors"])
            raise ValueError(f"GraphQL error: {msgs}")

        return body.get("data", {})

    @staticmethod
    def _gid(resource: str, numeric_id: str) -> str:
        """Build Shopify Global ID → gid://shopify/Product/123"""
        return f"gid://shopify/{resource}/{numeric_id}"

    @staticmethod
    def _numeric_id(gid: str) -> str:
        """Extract '123' from gid://shopify/Product/123"""
        return gid.rsplit("/", 1)[-1] if gid else gid

    # ================================================================
    # OAuth (unchanged – OAuth endpoints are NOT Admin API)
    # ================================================================

    def generate_oauth_url(
        self, store_url: str, state: str, redirect_uri: str
    ) -> str:
        shop_domain = self._get_shop_domain(store_url)
        params = {
            "client_id": settings.SHOPIFY_CLIENT_ID,
            "scope": ",".join(self.REQUIRED_SCOPES),
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params)}"

    async def exchange_oauth_code(
        self, store_url: str, code: str, redirect_uri: str
    ) -> OAuthResult:
        shop_domain = self._get_shop_domain(store_url)

        async def _exchange():
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"https://{shop_domain}/admin/oauth/access_token",
                    json={
                        "client_id": settings.SHOPIFY_CLIENT_ID,
                        "client_secret": settings.SHOPIFY_CLIENT_SECRET,
                        "code": code,
                    },
                )
                response.raise_for_status()
                return response.json()

        try:
            data = await execute_with_retry(
                _exchange, config=self.retry_config, operation_name="shopify_oauth"
            )
            return OAuthResult(
                success=True,
                access_token=data.get("access_token"),
                scope=data.get("scope"),
            )
        except httpx.HTTPStatusError as e:
            return OAuthResult(success=False, error=f"HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            return OAuthResult(success=False, error=str(e))

    async def refresh_access_token(self, store_url: str, refresh_token: str) -> OAuthResult:
        return OAuthResult(success=False, error="Shopify tokens don't expire")

    # ================================================================
    # verify_credentials  (was: GET /shop.json)
    # ================================================================

    async def verify_credentials(self, store_url: str, access_token: str) -> bool:
        shop_domain = self._get_shop_domain(store_url)
        query = "{ shop { name } }"
        try:
            async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as rc:
                await self._graphql(rc, shop_domain, access_token, query)
                return True
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
            return False

    # ================================================================
    # Products  (was: GET /products.json, GET /products/{id}.json)
    # ================================================================

    _PRODUCT_FIELDS = """
        fragment ProductFields on Product {
            id
            title
            bodyHtml
            vendor
            productType
            tags
            status
            createdAt
            updatedAt
            images(first: 10) {
                edges { node { url } }
            }
            variants(first: 100) {
                edges {
                    node {
                        id
                        title
                        price
                        sku
                        compareAtPrice
                        inventoryQuantity
                    }
                }
            }
        }
    """

    async def fetch_products(
        self,
        store_url: str,
        access_token: str,
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> ProductSyncResult:
        """Fetch products with cursor-based pagination (replaces page_info REST param)."""
        shop_domain = self._get_shop_domain(store_url)
        safe_limit = min(limit, 250)

        after_clause = f', after: "{cursor}"' if cursor else ""
        query = f"""
            {self._PRODUCT_FIELDS}
            query FetchProducts {{
                products(first: {safe_limit}{after_clause}) {{
                    edges {{
                        node {{ ...ProductFields }}
                        cursor
                    }}
                    pageInfo {{ hasNextPage }}
                }}
            }}
        """
        try:
            async with RetryableClient(store_url, "shopify", self.retry_config, 30.0) as rc:
                data = await self._graphql(rc, shop_domain, access_token, query)

            edges = data.get("products", {}).get("edges", [])
            page_info = data.get("products", {}).get("pageInfo", {})
            products = [self._parse_graphql_product(e["node"]) for e in edges]
            next_cursor = edges[-1]["cursor"] if edges and page_info.get("hasNextPage") else None

            return ProductSyncResult(
                success=True,
                products=products,
                has_more=page_info.get("hasNextPage", False),
                next_cursor=next_cursor,
            )
        except CircuitOpenError:
            return ProductSyncResult(success=False, error="Service temporarily unavailable")
        except httpx.HTTPStatusError as e:
            error_map = {401: "Unauthorized", 429: "Rate limited"}
            return ProductSyncResult(
                success=False,
                error=error_map.get(e.response.status_code, f"HTTP {e.response.status_code}"),
            )
        except (httpx.RequestError, ValueError) as e:
            return ProductSyncResult(success=False, error=str(e))

    async def fetch_single_product(
        self,
        store_url: str,
        access_token: str,
        external_product_id: str,
    ) -> Optional[ExternalProduct]:
        """Fetch one product by numeric ID."""
        shop_domain = self._get_shop_domain(store_url)
        gid = self._gid("Product", external_product_id)

        query = f"""
            {self._PRODUCT_FIELDS}
            query FetchProduct($id: ID!) {{
                product(id: $id) {{ ...ProductFields }}
            }}
        """
        try:
            async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as rc:
                data = await self._graphql(
                    rc, shop_domain, access_token, query, {"id": gid}
                )
            node = data.get("product")
            return self._parse_graphql_product(node) if node else None
        except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
            return None

    # ================================================================
    # Price update  (was: PUT /variants/{id}.json)
    # ================================================================

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

            # GraphQL mutation (replaces PUT /variants/{id}.json)
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

    # ================================================================
    # Price verification (logic unchanged, now uses GQL-based fetch)
    # ================================================================

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

    # ================================================================
    # Webhooks  (was: POST/DELETE /webhooks.json)
    # ================================================================

    async def register_webhooks(
        self,
        store_url: str,
        access_token: str,
        callback_url: str,
    ) -> List[WebhookRegistration]:
        shop_domain = self._get_shop_domain(store_url)
        results: List[WebhookRegistration] = []

        mutation = """
            mutation WebhookCreate($topic: WebhookSubscriptionTopic!, $url: URL!) {
                webhookSubscriptionCreate(
                    topic: $topic
                    webhookSubscription: { callbackUrl: $url, format: JSON }
                ) {
                    webhookSubscription { id }
                    userErrors { field message }
                }
            }
        """

        async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as rc:
            for gql_topic, rest_topic in zip(self.WEBHOOK_TOPICS_GQL, self.WEBHOOK_TOPICS):
                try:
                    data = await self._graphql(
                        rc, shop_domain, access_token, mutation,
                        {"topic": gql_topic, "url": callback_url},
                    )
                    result = data.get("webhookSubscriptionCreate", {})
                    errors = result.get("userErrors", [])
                    if errors:
                        msg = "; ".join(e.get("message", "") for e in errors)
                        results.append(WebhookRegistration(success=False, topic=rest_topic, error=msg))
                    else:
                        wh = result.get("webhookSubscription", {})
                        wh_id = self._numeric_id(wh.get("id", ""))
                        results.append(WebhookRegistration(success=True, webhook_id=wh_id, topic=rest_topic))
                except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as e:
                    results.append(WebhookRegistration(success=False, topic=rest_topic, error=str(e)))

        return results

    async def unregister_webhooks(
        self,
        store_url: str,
        access_token: str,
        webhook_ids: List[str],
    ) -> bool:
        shop_domain = self._get_shop_domain(store_url)
        success = True

        mutation = """
            mutation WebhookDelete($id: ID!) {
                webhookSubscriptionDelete(id: $id) {
                    deletedWebhookSubscriptionId
                    userErrors { field message }
                }
            }
        """

        async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as rc:
            for wid in webhook_ids:
                try:
                    gid = self._gid("WebhookSubscription", wid)
                    data = await self._graphql(
                        rc, shop_domain, access_token, mutation, {"id": gid}
                    )
                    errors = (data.get("webhookSubscriptionDelete") or {}).get("userErrors", [])
                    if errors:
                        logger.warning(f"Failed to delete webhook {wid}: {errors}")
                        success = False
                except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
                    success = False

        return success

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        computed = base64.b64encode(
            hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(computed, signature)

    # ================================================================
    # Health check  (was: GET /shop.json)
    # ================================================================

    async def health_check(self, store_url: str, access_token: str) -> ConnectionStatus:
        shop_domain = self._get_shop_domain(store_url)
        query = "{ shop { name } }"
        try:
            async with RetryableClient(store_url, "shopify", RetryConfig(max_retries=1), 10.0) as rc:
                await self._graphql(rc, shop_domain, access_token, query)
                return ConnectionStatus.HEALTHY
        except httpx.HTTPStatusError as e:
            status_map = {401: ConnectionStatus.UNAUTHORIZED, 429: ConnectionStatus.RATE_LIMITED}
            return status_map.get(e.response.status_code, ConnectionStatus.UNHEALTHY)
        except (httpx.RequestError, ValueError):
            return ConnectionStatus.UNHEALTHY

    # ================================================================
    # Internal helpers
    # ================================================================

    def _get_shop_domain(self, store_url: str) -> str:
        url = store_url.strip().lower().replace("https://", "").replace("http://", "").rstrip("/")
        if not url.endswith(".myshopify.com") and "." not in url:
            url = f"{url}.myshopify.com"
        return url

    def _auth_headers(self, access_token: str) -> dict:
        return {"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"}

    def _parse_graphql_product(self, node: dict) -> ExternalProduct:
        """
        Parse a GraphQL product node into ExternalProduct.

        GraphQL returns:
          - IDs as GIDs (gid://shopify/Product/123) → we extract numeric
          - variants/images as edges[] → we flatten
          - tags as list of strings → direct use
          - prices as strings → we convert to float
        """
        # Parse variants
        variant_edges = node.get("variants", {}).get("edges", [])
        variants = [
            ExternalProductVariant(
                id=self._numeric_id(v["node"]["id"]),
                title=v["node"].get("title", ""),
                price=float(v["node"]["price"]) if v["node"].get("price") else 0,
                sku=v["node"].get("sku"),
                inventory_quantity=v["node"].get("inventoryQuantity"),
                compare_at_price=(
                    float(v["node"]["compareAtPrice"])
                    if v["node"].get("compareAtPrice")
                    else None
                ),
            )
            for v in variant_edges
        ]

        # Parse images
        image_edges = node.get("images", {}).get("edges", [])
        images = [e["node"]["url"] for e in image_edges if e.get("node", {}).get("url")]

        # Tags: GraphQL returns a list, REST returned comma-separated string
        tags = node.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        return ExternalProduct(
            id=self._numeric_id(node.get("id", "")),
            title=node.get("title", ""),
            price=variants[0].price if variants else None,
            compare_at_price=variants[0].compare_at_price if variants else None,
            sku=variants[0].sku if variants else None,
            description=node.get("bodyHtml", ""),
            inventory_quantity=variants[0].inventory_quantity if variants else None,
            product_type=node.get("productType", ""),
            vendor=node.get("vendor", ""),
            tags=tags,
            images=images,
            variants=variants,
            created_at=self._parse_datetime(node.get("createdAt")),
            updated_at=self._parse_datetime(node.get("updatedAt")),
        )

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None



            