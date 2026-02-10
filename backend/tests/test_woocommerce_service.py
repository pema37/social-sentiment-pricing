"""
Tests for services.integration.woocommerce_service
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

# Provide base class
class _FakeEcommerceService:
    def __init__(self, retry_config=None):
        self.retry_config = retry_config

    @staticmethod
    def normalize_store_url(url):
        return url.rstrip("/")

sys.modules["services.integration.base"].EcommerceService = _FakeEcommerceService

# Provide model classes (reuse same fakes as shopify tests)
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

class _FakeRetryConfig:
    def __init__(self, **kw):
        self.max_retries = kw.get("max_retries", 3)
        self.base_delay = kw.get("base_delay", 1.0)
        self.max_delay = kw.get("max_delay", 30.0)

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

sys.modules["services.integration.retry"].RetryConfig = _FakeRetryConfig
sys.modules["services.integration.http_client"].RetryableClient = MagicMock
sys.modules["services.integration.circuit_breaker"].CircuitOpenError = type("CircuitOpenError", (Exception,), {})

# --- import under test ---
from services.integration.woocommerce_service import WooCommerceService

# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_platform_name(self):
        svc = WooCommerceService()
        assert svc.platform_name == "woocommerce"

    def test_api_version(self):
        assert WooCommerceService.API_VERSION == "wc/v3"

    def test_default_retry_config(self):
        svc = WooCommerceService()
        assert svc.retry_config.max_retries == 3

    def test_custom_retry_config(self):
        cfg = _FakeRetryConfig(max_retries=5)
        svc = WooCommerceService(retry_config=cfg)
        assert svc.retry_config.max_retries == 5

    def test_price_verification_tolerance(self):
        assert WooCommerceService.PRICE_VERIFICATION_TOLERANCE == Decimal("0.02")


class TestParseCredentials:
    def test_valid_credentials(self):
        svc = WooCommerceService()
        key, secret = svc._parse_credentials("ck_abc:cs_xyz")
        assert key == "ck_abc"
        assert secret == "cs_xyz"

    def test_missing_separator_raises(self):
        svc = WooCommerceService()
        with pytest.raises(ValueError, match="consumer_key:consumer_secret"):
            svc._parse_credentials("no-separator-here")

    def test_multiple_colons(self):
        svc = WooCommerceService()
        key, secret = svc._parse_credentials("ck_abc:cs_xyz:extra")
        assert key == "ck_abc"
        assert secret == "cs_xyz:extra"


class TestGenerateOauthUrl:
    def test_returns_admin_url(self):
        svc = WooCommerceService()
        url = svc.generate_oauth_url("https://mystore.com", "state", "redirect")
        assert "wp-admin" in url
        assert "wc-settings" in url


class TestExchangeOauthCode:
    @pytest.mark.asyncio
    async def test_returns_failure(self):
        svc = WooCommerceService()
        result = await svc.exchange_oauth_code("url", "code", "redirect")
        assert result.success is False
        assert "API keys" in result.error


class TestRefreshAccessToken:
    @pytest.mark.asyncio
    async def test_returns_failure(self):
        svc = WooCommerceService()
        result = await svc.refresh_access_token("url", "token")
        assert result.success is False
        assert "expire" in result.error.lower()


class TestParseProduct:
    def test_simple_product(self):
        svc = WooCommerceService()
        data = {
            "id": 42,
            "name": "T-Shirt",
            "description": "<p>Cotton</p>",
            "sku": "TS-001",
            "price": "24.99",
            "sale_price": "",
            "regular_price": "24.99",
            "stock_quantity": 50,
            "type": "simple",
            "tags": [{"name": "clothing"}],
            "images": [{"src": "https://img.jpg"}],
            "variations": [],
        }
        product = svc._parse_product(data)
        assert product.id == "42"
        assert product.title == "T-Shirt"
        assert product.price == 24.99
        assert product.sku == "TS-001"
        assert len(product.tags) == 1

    def test_sale_product(self):
        svc = WooCommerceService()
        data = {
            "id": 1,
            "name": "Sale Item",
            "price": "15.00",
            "sale_price": "15.00",
            "regular_price": "20.00",
            "type": "simple",
            "tags": [],
            "images": [],
            "variations": [],
        }
        product = svc._parse_product(data)
        assert product.price == 15.00
        assert product.compare_at_price == 20.00

    def test_variation_as_dict(self):
        svc = WooCommerceService()
        data = {
            "id": 1,
            "name": "Variable",
            "price": "10.00",
            "type": "variable",
            "tags": [],
            "images": [],
            "variations": [
                {"id": 100, "price": "12.00", "sku": "V-1", "stock_quantity": 5, "attributes": [{"option": "Large"}]}
            ],
        }
        product = svc._parse_product(data)
        assert product.variants is not None
        assert len(product.variants) == 1
        assert product.variants[0].id == "100"

    def test_variation_as_int_skipped(self):
        svc = WooCommerceService()
        data = {
            "id": 1,
            "name": "Variable",
            "price": "10.00",
            "type": "variable",
            "tags": [],
            "images": [],
            "variations": [101, 102, 103],
        }
        product = svc._parse_product(data)
        # Int variants are skipped
        assert product.variants is None or len(product.variants) == 0

    def test_no_price(self):
        svc = WooCommerceService()
        data = {
            "id": 1,
            "name": "Draft",
            "type": "simple",
            "tags": [],
            "images": [],
            "variations": [],
        }
        product = svc._parse_product(data)
        assert product.price is None


class TestParseDatetime:
    def test_valid_iso(self):
        svc = WooCommerceService()
        result = svc._parse_datetime("2024-01-15T10:30:00")
        assert isinstance(result, datetime)

    def test_with_z(self):
        svc = WooCommerceService()
        result = svc._parse_datetime("2024-01-15T10:30:00Z")
        assert isinstance(result, datetime)

    def test_none(self):
        svc = WooCommerceService()
        assert svc._parse_datetime(None) is None

    def test_invalid(self):
        svc = WooCommerceService()
        assert svc._parse_datetime("not-a-date") is None


class TestVerifyWebhookSignature:
    def test_valid_signature(self):
        import hmac as _hmac
        import hashlib
        import base64

        svc = WooCommerceService()
        secret = "wc-secret"
        payload = b'{"id": 42}'
        sig = base64.b64encode(
            _hmac.new(secret.encode(), payload, hashlib.sha256).digest()
        ).decode()

        assert svc.verify_webhook_signature(payload, sig, secret) is True

    def test_invalid_signature(self):
        svc = WooCommerceService()
        assert svc.verify_webhook_signature(b"data", "bad-sig", "secret") is False



        