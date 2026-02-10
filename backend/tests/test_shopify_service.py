"""
Tests for services.integration.shopify_service
"""

import sys
import types
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Stub heavy external deps
# ---------------------------------------------------------------------------
_stubs: dict[str, types.ModuleType] = {}

_needed = [
    "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlmodel",
    "core", "core.config",
    "services.integration.base",
    "services.integration.models",
    "services.integration.retry",
    "services.integration.http_client",
    "services.integration.circuit_breaker",
]

for _mod_name in _needed:
    if _mod_name not in sys.modules:
        _stubs[_mod_name] = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _stubs[_mod_name]

# Provide settings
_settings = MagicMock()
_settings.SHOPIFY_CLIENT_ID = "test-client-id"
_settings.SHOPIFY_CLIENT_SECRET = "test-client-secret"
sys.modules["core.config"].settings = _settings

# Provide base class
class _FakeEcommerceService:
    def __init__(self, retry_config=None):
        self.retry_config = retry_config

    @staticmethod
    def normalize_store_url(url):
        return url.rstrip("/")

sys.modules["services.integration.base"].EcommerceService = _FakeEcommerceService

# Provide model classes
class _FakeExternalProduct:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

class _FakeExternalProductVariant:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

class _FakeProductSyncResult:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

class _FakeOAuthResult:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

class _FakePriceUpdateResult:
    SUCCESS = "success"
    FAILED = "failed"
    UNAUTHORIZED = "unauthorized"
    PRODUCT_NOT_FOUND = "product_not_found"
    RATE_LIMITED = "rate_limited"

class _FakePriceUpdateResponse:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

class _FakeWebhookRegistration:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

class _FakeConnectionStatus:
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"

class _FakePriceUpdateRequest:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

_models = sys.modules["services.integration.models"]
_models.OAuthResult = _FakeOAuthResult
_models.ExternalProduct = _FakeExternalProduct
_models.ExternalProductVariant = _FakeExternalProductVariant
_models.ProductSyncResult = _FakeProductSyncResult
_models.PriceUpdateRequest = _FakePriceUpdateRequest
_models.PriceUpdateResponse = _FakePriceUpdateResponse
_models.PriceUpdateResult = _FakePriceUpdateResult
_models.WebhookRegistration = _FakeWebhookRegistration
_models.ConnectionStatus = _FakeConnectionStatus

# Provide retry
class _FakeRetryConfig:
    def __init__(self, **kw):
        self.max_retries = kw.get("max_retries", 3)
        self.base_delay = kw.get("base_delay", 1.0)
        self.max_delay = kw.get("max_delay", 30.0)

sys.modules["services.integration.retry"].RetryConfig = _FakeRetryConfig
sys.modules["services.integration.retry"].execute_with_retry = AsyncMock()
sys.modules["services.integration.http_client"].RetryableClient = MagicMock
sys.modules["services.integration.circuit_breaker"].CircuitOpenError = type("CircuitOpenError", (Exception,), {})

# Force-clean any MagicMock pollution from earlier tests
for _clean in ["services.integration.shopify_service", "services.integration.woocommerce_service"]:
    if _clean in sys.modules and not isinstance(sys.modules[_clean], types.ModuleType):
        del sys.modules[_clean]

# --- import under test ---
from services.integration.shopify_service import ShopifyService

# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_platform_name(self):
        svc = ShopifyService()
        assert svc.platform_name == "shopify"

    def test_api_version(self):
        assert ShopifyService.API_VERSION == "2024-01"

    def test_default_retry_config(self):
        svc = ShopifyService()
        assert svc.retry_config.max_retries == 3

    def test_custom_retry_config(self):
        cfg = _FakeRetryConfig(max_retries=5)
        svc = ShopifyService(retry_config=cfg)
        assert svc.retry_config.max_retries == 5

    def test_price_verification_tolerance(self):
        assert ShopifyService.PRICE_VERIFICATION_TOLERANCE == Decimal("0.02")


class TestGetShopDomain:
    def test_plain_name(self):
        svc = ShopifyService()
        assert svc._get_shop_domain("myshop") == "myshop.myshopify.com"

    def test_full_domain(self):
        svc = ShopifyService()
        assert svc._get_shop_domain("myshop.myshopify.com") == "myshop.myshopify.com"

    def test_with_https(self):
        svc = ShopifyService()
        assert svc._get_shop_domain("https://myshop.myshopify.com") == "myshop.myshopify.com"

    def test_strips_trailing_slash(self):
        svc = ShopifyService()
        result = svc._get_shop_domain("https://myshop.myshopify.com/")
        assert not result.endswith("/")

    def test_custom_domain_preserved(self):
        svc = ShopifyService()
        result = svc._get_shop_domain("shop.example.com")
        # Has a dot, so should NOT append .myshopify.com
        assert result == "shop.example.com"


class TestAuthHeaders:
    def test_contains_access_token(self):
        svc = ShopifyService()
        headers = svc._auth_headers("shpat_abc123")
        assert headers["X-Shopify-Access-Token"] == "shpat_abc123"

    def test_contains_content_type(self):
        svc = ShopifyService()
        headers = svc._auth_headers("token")
        assert headers["Content-Type"] == "application/json"


class TestGenerateOauthUrl:
    def test_contains_client_id(self):
        svc = ShopifyService()
        url = svc.generate_oauth_url("myshop.myshopify.com", "state123", "https://callback.com")
        assert "test-client-id" in url

    def test_contains_redirect_uri(self):
        svc = ShopifyService()
        url = svc.generate_oauth_url("myshop", "state123", "https://callback.com")
        assert "callback.com" in url

    def test_contains_state(self):
        svc = ShopifyService()
        url = svc.generate_oauth_url("myshop", "state123", "https://cb.com")
        assert "state123" in url


class TestRefreshAccessToken:
    @pytest.mark.asyncio
    async def test_returns_failure(self):
        svc = ShopifyService()
        result = await svc.refresh_access_token("url", "token")
        assert result.success is False
        assert "expire" in result.error.lower()


class TestParseProduct:
    def test_basic_product(self):
        svc = ShopifyService()
        data = {
            "id": 123,
            "title": "Test Widget",
            "body_html": "<p>Nice</p>",
            "product_type": "Gadget",
            "vendor": "TestCo",
            "tags": "tag1, tag2",
            "images": [{"src": "https://img.jpg"}],
            "variants": [
                {
                    "id": 456,
                    "title": "Default",
                    "price": "19.99",
                    "sku": "W-001",
                    "inventory_quantity": 10,
                    "compare_at_price": None,
                }
            ],
        }
        product = svc._parse_product(data)
        assert product.id == "123"
        assert product.title == "Test Widget"
        assert product.price == 19.99
        assert product.sku == "W-001"
        assert len(product.tags) == 2
        assert len(product.images) == 1

    def test_no_variants(self):
        svc = ShopifyService()
        data = {"id": 1, "title": "Bare", "variants": [], "images": []}
        product = svc._parse_product(data)
        assert product.price is None
        assert product.sku is None

    def test_compare_at_price(self):
        svc = ShopifyService()
        data = {
            "id": 1,
            "title": "Sale",
            "variants": [{"id": 2, "title": "D", "price": "15.00", "compare_at_price": "20.00"}],
            "images": [],
        }
        product = svc._parse_product(data)
        assert product.compare_at_price == 20.00


class TestExtractNextCursor:
    def test_extracts_next_cursor(self):
        svc = ShopifyService()
        header = '<https://shop.myshopify.com/products.json?page_info=abc123>; rel="next"'
        assert svc._extract_next_cursor(header) == "abc123"

    def test_returns_none_when_no_next(self):
        svc = ShopifyService()
        header = '<https://shop.myshopify.com/products.json?page_info=abc>; rel="previous"'
        assert svc._extract_next_cursor(header) is None

    def test_returns_none_for_none_header(self):
        svc = ShopifyService()
        assert svc._extract_next_cursor(None) is None

    def test_returns_none_for_empty_header(self):
        svc = ShopifyService()
        assert svc._extract_next_cursor("") is None


class TestParseDatetime:
    def test_valid_iso(self):
        svc = ShopifyService()
        result = svc._parse_datetime("2024-01-15T10:30:00Z")
        assert isinstance(result, datetime)

    def test_none_input(self):
        svc = ShopifyService()
        assert svc._parse_datetime(None) is None

    def test_invalid_string(self):
        svc = ShopifyService()
        assert svc._parse_datetime("not-a-date") is None


class TestVerifyWebhookSignature:
    def test_valid_signature(self):
        import hmac as _hmac
        import hashlib
        import base64

        svc = ShopifyService()
        secret = "test-secret"
        payload = b'{"id": 123}'
        sig = base64.b64encode(
            _hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        ).decode()

        assert svc.verify_webhook_signature(payload, sig, secret) is True

    def test_invalid_signature(self):
        svc = ShopifyService()
        assert svc.verify_webhook_signature(b"data", "bad-sig", "secret") is False


        