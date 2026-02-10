"""
Tests for services/integration/base.py

EcommerceService ABC — tests concrete methods: __init__, get_client,
bulk_update_prices, normalize_store_url. Uses a concrete subclass stub.
"""

import sys
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Optional, List

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED_MODULES = [
    "services.integration.models",
    "services.integration.retry",
    "services.integration.rate_limit",
    "services.integration.http_client",
]
_originals = {mod: sys.modules.get(mod) for mod in _MOCKED_MODULES}

for mod in _MOCKED_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Wire up specific names the module expects
_retry_mod = sys.modules["services.integration.retry"]
_retry_mod.RetryConfig = type("RetryConfig", (), {"__init__": lambda self, **kw: None})
_default_cfg = _retry_mod.RetryConfig()
_retry_mod.DEFAULT_RETRY_CONFIG = _default_cfg

_rate_mod = sys.modules["services.integration.rate_limit"]
_rate_mod.rate_limit_tracker = MagicMock()
_rate_mod.rate_limit_tracker.wait_if_needed = AsyncMock(return_value=0.0)

_http_mod = sys.modules["services.integration.http_client"]
_http_mod.RetryableClient = MagicMock()

# Models — simple classes
_models_mod = sys.modules["services.integration.models"]
for _name in [
    "OAuthResult", "ExternalProduct", "ProductSyncResult",
    "PriceUpdateRequest", "PriceUpdateResponse", "PriceUpdateResult",
    "WebhookRegistration", "ConnectionStatus",
]:
    setattr(_models_mod, _name, type(_name, (), {}))

from services.integration.base import EcommerceService

# ── Restore modules ──────────────────────────────────────────────
for _mod in _MOCKED_MODULES:
    if _originals[_mod] is None:
        sys.modules.pop(_mod, None)
    else:
        sys.modules[_mod] = _originals[_mod]
del _mod

SVC_MOD = "services.integration.base"


# ── Concrete stub for testing ────────────────────────────────────
class _StubService(EcommerceService):
    """Concrete implementation of all abstract methods for testing."""

    @property
    def platform_name(self) -> str:
        return "test_platform"

    def generate_oauth_url(self, store_url, state, redirect_uri):
        return f"https://oauth.test/{store_url}"

    async def exchange_oauth_code(self, store_url, code, redirect_uri):
        return MagicMock()

    async def refresh_access_token(self, store_url, refresh_token):
        return MagicMock()

    async def verify_credentials(self, store_url, access_token):
        return True

    async def fetch_products(self, store_url, access_token, cursor=None, limit=50):
        return MagicMock()

    async def fetch_single_product(self, store_url, access_token, external_product_id):
        return MagicMock()

    async def update_price(self, store_url, access_token, request):
        return MagicMock(success=True)

    async def register_webhooks(self, store_url, access_token, callback_url):
        return []

    async def unregister_webhooks(self, store_url, access_token, webhook_ids):
        return True

    def verify_webhook_signature(self, payload, signature, secret):
        return True

    async def health_check(self, store_url, access_token):
        return MagicMock()


# ──────────────────────────────────────────────
# __init__
# ──────────────────────────────────────────────
class TestEcommerceServiceInit:

    def test_default_retry_config(self):
        svc = _StubService()
        assert svc.retry_config is _default_cfg

    def test_custom_retry_config(self):
        custom = MagicMock()
        svc = _StubService(retry_config=custom)
        assert svc.retry_config is custom

    def test_none_uses_default(self):
        svc = _StubService(retry_config=None)
        assert svc.retry_config is _default_cfg


# ──────────────────────────────────────────────
# platform_name (abstract property)
# ──────────────────────────────────────────────
class TestPlatformName:

    def test_returns_string(self):
        svc = _StubService()
        assert svc.platform_name == "test_platform"

    def test_is_property(self):
        # platform_name is defined as @property on the stub
        svc = _StubService()
        assert isinstance(svc.platform_name, str)


# ──────────────────────────────────────────────
# get_client
# ──────────────────────────────────────────────
class TestGetClient:

    def test_creates_retryable_client(self):
        svc = _StubService()
        with patch(f"{SVC_MOD}.RetryableClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = svc.get_client("mystore.myshopify.com")

            mock_cls.assert_called_once_with(
                store_url="mystore.myshopify.com",
                platform="test_platform",
                retry_config=svc.retry_config,
            )

    def test_returns_client_instance(self):
        svc = _StubService()
        with patch(f"{SVC_MOD}.RetryableClient") as mock_cls:
            sentinel = MagicMock()
            mock_cls.return_value = sentinel
            result = svc.get_client("store")
            assert result is sentinel


# ──────────────────────────────────────────────
# normalize_store_url
# ──────────────────────────────────────────────
class TestNormalizeStoreUrl:

    def test_strips_whitespace(self):
        svc = _StubService()
        assert svc.normalize_store_url("  example.com  ") == "https://example.com"

    def test_strips_trailing_slash(self):
        svc = _StubService()
        assert svc.normalize_store_url("https://example.com/") == "https://example.com"

    def test_multiple_trailing_slashes(self):
        svc = _StubService()
        # rstrip("/") only strips one layer of slashes
        result = svc.normalize_store_url("https://example.com///")
        assert result == "https://example.com"

    def test_adds_https_for_production(self):
        svc = _StubService()
        assert svc.normalize_store_url("mystore.myshopify.com") == "https://mystore.myshopify.com"

    def test_adds_http_for_localhost(self):
        svc = _StubService()
        assert svc.normalize_store_url("localhost:8888") == "http://localhost:8888"

    def test_adds_http_for_127_0_0_1(self):
        svc = _StubService()
        assert svc.normalize_store_url("127.0.0.1:3000") == "http://127.0.0.1:3000"

    def test_preserves_existing_https(self):
        svc = _StubService()
        assert svc.normalize_store_url("https://mystore.com") == "https://mystore.com"

    def test_preserves_existing_http(self):
        svc = _StubService()
        assert svc.normalize_store_url("http://localhost:8888") == "http://localhost:8888"

    def test_localhost_without_port(self):
        svc = _StubService()
        assert svc.normalize_store_url("localhost") == "http://localhost"

    def test_subdomain_with_localhost(self):
        svc = _StubService()
        # "localhost" is in the string
        assert svc.normalize_store_url("api.localhost") == "http://api.localhost"

    def test_complex_url_preserved(self):
        svc = _StubService()
        result = svc.normalize_store_url("https://store.example.com/api/v2")
        assert result == "https://store.example.com/api/v2"

    def test_empty_string_gets_https(self):
        svc = _StubService()
        result = svc.normalize_store_url("")
        assert result == "https://"

    def test_whitespace_only(self):
        svc = _StubService()
        result = svc.normalize_store_url("   ")
        assert result == "https://"

    def test_url_with_path(self):
        svc = _StubService()
        result = svc.normalize_store_url("mystore.com/shop")
        assert result == "https://mystore.com/shop"

    def test_trailing_slash_with_whitespace(self):
        svc = _StubService()
        result = svc.normalize_store_url("  https://store.com/  ")
        assert result == "https://store.com"


# ──────────────────────────────────────────────
# bulk_update_prices (default implementation)
# ──────────────────────────────────────────────
class TestBulkUpdatePrices:

    @pytest.mark.asyncio
    async def test_calls_update_price_for_each(self):
        svc = _StubService()
        svc.update_price = AsyncMock(return_value=MagicMock(success=True))

        requests = [MagicMock(), MagicMock(), MagicMock()]

        with patch(f"{SVC_MOD}.rate_limit_tracker") as mock_tracker:
            mock_tracker.wait_if_needed = AsyncMock(return_value=0.0)
            with patch(f"{SVC_MOD}.asyncio.sleep", new_callable=AsyncMock):
                results = await svc.bulk_update_prices("store", "token", requests)

        assert len(results) == 3
        assert svc.update_price.call_count == 3

    @pytest.mark.asyncio
    async def test_passes_store_and_token(self):
        svc = _StubService()
        svc.update_price = AsyncMock(return_value=MagicMock())

        req = MagicMock()

        with patch(f"{SVC_MOD}.rate_limit_tracker") as mock_tracker:
            mock_tracker.wait_if_needed = AsyncMock(return_value=0.0)
            with patch(f"{SVC_MOD}.asyncio.sleep", new_callable=AsyncMock):
                await svc.bulk_update_prices("my-store", "my-token", [req])

        svc.update_price.assert_called_once_with("my-store", "my-token", req)

    @pytest.mark.asyncio
    async def test_empty_requests(self):
        svc = _StubService()
        svc.update_price = AsyncMock()

        with patch(f"{SVC_MOD}.rate_limit_tracker") as mock_tracker:
            mock_tracker.wait_if_needed = AsyncMock(return_value=0.0)
            results = await svc.bulk_update_prices("store", "token", [])

        assert results == []
        svc.update_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_waits_for_rate_limit(self):
        svc = _StubService()
        svc.update_price = AsyncMock(return_value=MagicMock())

        with patch(f"{SVC_MOD}.rate_limit_tracker") as mock_tracker:
            mock_tracker.wait_if_needed = AsyncMock(return_value=0.0)
            with patch(f"{SVC_MOD}.asyncio.sleep", new_callable=AsyncMock):
                await svc.bulk_update_prices("store", "token", [MagicMock()])

            mock_tracker.wait_if_needed.assert_called_with("store")

    @pytest.mark.asyncio
    async def test_sleeps_between_requests(self):
        svc = _StubService()
        svc.update_price = AsyncMock(return_value=MagicMock())

        with patch(f"{SVC_MOD}.rate_limit_tracker") as mock_tracker:
            mock_tracker.wait_if_needed = AsyncMock(return_value=0.0)
            with patch(f"{SVC_MOD}.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                await svc.bulk_update_prices("store", "token", [MagicMock(), MagicMock()])

                assert mock_sleep.call_count == 2
                mock_sleep.assert_called_with(0.1)

    @pytest.mark.asyncio
    async def test_returns_list_of_responses(self):
        resp1, resp2 = MagicMock(), MagicMock()
        svc = _StubService()
        svc.update_price = AsyncMock(side_effect=[resp1, resp2])

        with patch(f"{SVC_MOD}.rate_limit_tracker") as mock_tracker:
            mock_tracker.wait_if_needed = AsyncMock(return_value=0.0)
            with patch(f"{SVC_MOD}.asyncio.sleep", new_callable=AsyncMock):
                results = await svc.bulk_update_prices(
                    "store", "token", [MagicMock(), MagicMock()]
                )

        assert results == [resp1, resp2]


# ──────────────────────────────────────────────
# ABC enforcement
# ──────────────────────────────────────────────
class TestABCEnforcement:

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            EcommerceService()

    def test_missing_abstract_method_raises(self):
        class Incomplete(EcommerceService):
            @property
            def platform_name(self):
                return "test"

        with pytest.raises(TypeError):
            Incomplete()

    def test_stub_is_instantiable(self):
        svc = _StubService()
        assert svc is not None

    def test_abstract_methods_exist(self):
        abstract_names = {
            "platform_name",
            "generate_oauth_url",
            "exchange_oauth_code",
            "refresh_access_token",
            "verify_credentials",
            "fetch_products",
            "fetch_single_product",
            "update_price",
            "register_webhooks",
            "unregister_webhooks",
            "verify_webhook_signature",
            "health_check",
        }
        actual = set(EcommerceService.__abstractmethods__)
        assert actual == abstract_names


# ──────────────────────────────────────────────
# Abstract method signatures (via stub)
# ──────────────────────────────────────────────
class TestAbstractMethodSignatures:

    def test_generate_oauth_url_sync(self):
        svc = _StubService()
        result = svc.generate_oauth_url("store", "state", "redirect")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_exchange_oauth_code_async(self):
        svc = _StubService()
        result = await svc.exchange_oauth_code("store", "code", "redirect")
        assert result is not None

    @pytest.mark.asyncio
    async def test_verify_credentials_async(self):
        svc = _StubService()
        result = await svc.verify_credentials("store", "token")
        assert result is True

    @pytest.mark.asyncio
    async def test_fetch_products_async(self):
        svc = _StubService()
        result = await svc.fetch_products("store", "token")
        assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_single_product_async(self):
        svc = _StubService()
        result = await svc.fetch_single_product("store", "token", "prod-1")
        assert result is not None

    @pytest.mark.asyncio
    async def test_update_price_async(self):
        svc = _StubService()
        result = await svc.update_price("store", "token", MagicMock())
        assert result is not None

    @pytest.mark.asyncio
    async def test_register_webhooks_async(self):
        svc = _StubService()
        result = await svc.register_webhooks("store", "token", "callback")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_unregister_webhooks_async(self):
        svc = _StubService()
        result = await svc.unregister_webhooks("store", "token", ["wh-1"])
        assert result is True

    def test_verify_webhook_signature_sync(self):
        svc = _StubService()
        result = svc.verify_webhook_signature(b"payload", "sig", "secret")
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_async(self):
        svc = _StubService()
        result = await svc.health_check("store", "token")
        assert result is not None

        