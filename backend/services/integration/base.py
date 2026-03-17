# backend/services/integration/base.py

"""
Abstract base class for e-commerce platform integrations.
"""

import asyncio
from abc import ABC, abstractmethod

from .http_client import RetryableClient
from .rate_limit import rate_limit_tracker
from .retry import DEFAULT_RETRY_CONFIG, RetryConfig
from .schemas import (
    ConnectionStatus,
    ExternalProduct,
    OAuthResult,
    PriceUpdateRequest,
    PriceUpdateResponse,
    ProductSyncResult,
    WebhookRegistration,
)


class EcommerceService(ABC):
    """
    Abstract base class for e-commerce integrations.

    All platform services (Shopify, WooCommerce, etc.) must
    implement this interface.
    """

    def __init__(self, retry_config: RetryConfig | None = None):
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return platform name (e.g., 'shopify')"""
        pass

    def get_client(self, store_url: str) -> RetryableClient:
        """Get HTTP client for this store"""
        return RetryableClient(store_url=store_url, platform=self.platform_name, retry_config=self.retry_config)

    # ========== OAuth / Authentication ==========

    @abstractmethod
    def generate_oauth_url(self, store_url: str, state: str, redirect_uri: str) -> str:
        """Generate OAuth authorization URL."""
        pass

    @abstractmethod
    async def exchange_oauth_code(self, store_url: str, code: str, redirect_uri: str) -> OAuthResult:
        """Exchange authorization code for access token."""
        pass

    @abstractmethod
    async def refresh_access_token(self, store_url: str, refresh_token: str) -> OAuthResult:
        """Refresh an expired access token."""
        pass

    @abstractmethod
    async def verify_credentials(self, store_url: str, access_token: str) -> bool:
        """Verify credentials are valid."""
        pass

    # ========== Product Operations ==========

    @abstractmethod
    async def fetch_products(
        self, store_url: str, access_token: str, cursor: str | None = None, limit: int = 50
    ) -> ProductSyncResult:
        """Fetch products from platform."""
        pass

    @abstractmethod
    async def fetch_single_product(
        self, store_url: str, access_token: str, external_product_id: str
    ) -> ExternalProduct | None:
        """Fetch a single product by ID."""
        pass

    @abstractmethod
    async def update_price(self, store_url: str, access_token: str, request: PriceUpdateRequest) -> PriceUpdateResponse:
        """Update a product's price."""
        pass

    async def bulk_update_prices(
        self, store_url: str, access_token: str, requests: list[PriceUpdateRequest]
    ) -> list[PriceUpdateResponse]:
        """
        Update multiple prices. Default calls update_price for each.
        Override for platform-specific bulk APIs.
        """
        results = []
        for request in requests:
            await rate_limit_tracker.wait_if_needed(store_url)
            result = await self.update_price(store_url, access_token, request)
            results.append(result)
            await asyncio.sleep(0.1)  # Small delay between requests
        return results

    # ========== Webhooks ==========

    @abstractmethod
    async def register_webhooks(
        self, store_url: str, access_token: str, callback_url: str
    ) -> list[WebhookRegistration]:
        """Register webhooks for product events."""
        pass

    @abstractmethod
    async def unregister_webhooks(self, store_url: str, access_token: str, webhook_ids: list[str]) -> bool:
        """Unregister webhooks by ID."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        """Verify webhook payload signature."""
        pass

    # ========== Health Check ==========

    @abstractmethod
    async def health_check(self, store_url: str, access_token: str) -> ConnectionStatus:
        """Check connection health."""
        pass

    # ========== Utility ==========

    def normalize_store_url(self, store_url: str) -> str:
        """Normalize store URL to consistent format."""
        url = store_url.strip().rstrip("/")
        # Check if URL has a port (like localhost:8888) - assume HTTP for local dev
        if not url.startswith(("http://", "https://")):
            if "localhost" in url or "127.0.0.1" in url:
                url = f"http://{url}"  # Use HTTP for local development
            else:
                url = f"https://{url}"  # Use HTTPS for production
        return url
