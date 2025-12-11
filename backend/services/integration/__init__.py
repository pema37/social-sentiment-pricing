# backend/services/integration/__init__.py

"""
E-commerce platform integrations.

Usage:
    from services.integration import ShopifyService, WooCommerceService
    
    shopify = ShopifyService()
    products = await shopify.fetch_products(store_url, token)
"""

# Models
from .models import (
    PriceUpdateResult,
    ConnectionStatus,
    OAuthResult,
    ExternalProduct,
    ExternalProductVariant,
    ProductSyncResult,
    PriceUpdateRequest,
    PriceUpdateResponse,
    WebhookRegistration,
)

# Retry
from .retry import (
    RetryConfig,
    DEFAULT_RETRY_CONFIG,
    execute_with_retry,
    with_retry,
)

# Rate limiting
from .rate_limit import (
    RateLimitState,
    RateLimitTracker,
    rate_limit_tracker,
)

# Circuit breaker
from .circuit_breaker import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitOpenError,
    CircuitBreakerRegistry,
    circuit_breaker_registry,
)

# HTTP client
from .http_client import RetryableClient

# Base class
from .base import EcommerceService

# Platform services
from .shopify_service import ShopifyService
from .woocommerce_service import WooCommerceService

# Sync orchestration
from .sync_service import (
    SyncService,
    SyncError,
    SyncTemporarilyUnavailable,
    run_product_sync,
)

# Webhook registration
from .webhook_registration import (
    WebhookRegistrationService,
    register_webhooks_for_integration,
    unregister_webhooks_for_integration,
)


__all__ = [
    # Models
    "PriceUpdateResult",
    "ConnectionStatus",
    "OAuthResult",
    "ExternalProduct",
    "ExternalProductVariant",
    "ProductSyncResult",
    "PriceUpdateRequest",
    "PriceUpdateResponse",
    "WebhookRegistration",
    # Retry
    "RetryConfig",
    "DEFAULT_RETRY_CONFIG",
    "execute_with_retry",
    "with_retry",
    # Rate limiting
    "RateLimitState",
    "RateLimitTracker",
    "rate_limit_tracker",
    # Circuit breaker
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitBreakerRegistry",
    "circuit_breaker_registry",
    # HTTP client
    "RetryableClient",
    # Base class
    "EcommerceService",
    # Services
    "ShopifyService",
    "WooCommerceService",
    # Sync
    "SyncService",
    "SyncError",
    "SyncTemporarilyUnavailable",
    "run_product_sync",
    # Webhook registration
    "WebhookRegistrationService",
    "register_webhooks_for_integration",
    "unregister_webhooks_for_integration",
]
