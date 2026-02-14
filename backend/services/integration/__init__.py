# backend/services/integration/__init__.py
"""
Integration services for Shopify, WooCommerce, etc.
Lazy imports to avoid breaking test stubs.
"""

_LAZY_IMPORTS = {
    "EcommerceService": "services.integration.base",
    "ShopifyService": "services.integration.shopify_service",
    "WooCommerceService": "services.integration.woocommerce_service",
    "WebhookRegistrationService": "services.integration.webhook_registration",
    "SyncService": "services.integration.sync_service",
    "SyncTemporarilyUnavailable": "services.integration.sync_service",
    "PricePushService": "services.integration.price_push_service",
    "PriceUpdateRequest": "services.integration.schemas",
    "PriceUpdateResult": "services.integration.schemas",
    "CircuitOpenError": "services.integration.circuit_breaker",
}

def __getattr__(name):
    if name in _LAZY_IMPORTS:
        import importlib
        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = list(_LAZY_IMPORTS.keys())

