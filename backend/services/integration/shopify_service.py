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

MODULARIZED (2026-02-17): Split into mixins for maintainability.
  - shopify_products.py  → Product fetching + parsing
  - shopify_pricing.py   → Price updates + verification
  - shopify_orders.py    → Orders API for outcome measurement
  - shopify_webhooks.py  → Webhook registration + verification

All downstream callers unchanged: ShopifyService().method() still works.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode

import httpx

from core.config import settings
from .base import EcommerceService
from .schemas import OAuthResult, ConnectionStatus
from .retry import RetryConfig, execute_with_retry
from .http_client import RetryableClient
from .circuit_breaker import CircuitOpenError

# Mixins
from .shopify_products import ShopifyProductsMixin
from .shopify_pricing import ShopifyPricingMixin
from .shopify_orders import ShopifyOrdersMixin
from .shopify_webhooks import ShopifyWebhooksMixin

logger = logging.getLogger(__name__)


class ShopifyService(
    ShopifyProductsMixin,
    ShopifyPricingMixin,
    ShopifyOrdersMixin,
    ShopifyWebhooksMixin,
    EcommerceService,
):
    """
    Shopify GraphQL Admin API integration.

    Migrated from REST to GraphQL per Shopify requirement (April 2025).
    All admin calls go to: POST /admin/api/{version}/graphql.json

    Rate Limits: 1,000 cost points per second (throttled query cost)

    Methods are organized into mixins by domain:
    - Products:  fetch_products, fetch_single_product
    - Pricing:   update_price (with verification)
    - Orders:    fetch_product_sales_data (for outcome measurement)
    - Webhooks:  register_webhooks, unregister_webhooks, verify_webhook_signature
    """

    API_VERSION = "2024-01"
    REQUIRED_SCOPES = ["read_products", "write_products", "read_orders"]
    WEBHOOK_TOPICS = ["products/create", "products/update", "products/delete"]
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
    # GraphQL core (used by all mixins)
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

        Returns:
            The "data" portion of the GraphQL response.

        Raises:
            httpx.HTTPStatusError: on HTTP-level failures (401, 429, etc.)
            ValueError: if GraphQL returns top-level errors
        """
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables

        response = await rc.post(
            self._graphql_url(shop_domain),
            headers=self._auth_headers(access_token),
            json=payload,
        )
        body = response.json()

        if body.get("errors"):
            msgs = "; ".join(e.get("message", "") for e in body["errors"])
            raise ValueError(f"GraphQL error: {msgs}")

        return body.get("data", {})

    # ================================================================
    # GID helpers (used by all mixins)
    # ================================================================

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
    # Verify credentials
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
    # Health check
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

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None

            