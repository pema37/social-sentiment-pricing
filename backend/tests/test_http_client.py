"""
Tests for services/integration/http_client.py

RetryableClient — HTTP client with retry, rate limiting, circuit breaker.
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from uuid import uuid4

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED = [
    "httpx",
    "services.integration.retry",
    "services.integration.rate_limit",
    "services.integration.circuit_breaker",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# httpx
_httpx = MagicMock()
_httpx.AsyncClient = MagicMock
_httpx.Response = MagicMock
sys.modules["httpx"] = _httpx

# retry
_retry_mod = MagicMock()

class _FakeRetryConfig:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

_retry_mod.RetryConfig = _FakeRetryConfig
_retry_mod.DEFAULT_RETRY_CONFIG = _FakeRetryConfig(max_retries=3)
_retry_mod.execute_with_retry = AsyncMock()
sys.modules["services.integration.retry"] = _retry_mod

# rate_limit
_rl_mod = MagicMock()
_rl_mod.rate_limit_tracker = MagicMock()
_rl_mod.rate_limit_tracker.wait_if_needed = AsyncMock()
_rl_mod.rate_limit_tracker.update_from_response = AsyncMock()
_rl_mod.rate_limit_tracker.mark_rate_limited = AsyncMock()
sys.modules["services.integration.rate_limit"] = _rl_mod

# circuit_breaker
_cb_mod = MagicMock()
_cb_mod.circuit_breaker_registry = MagicMock()
_cb_mod.circuit_breaker_registry.get = AsyncMock()
_cb_mod.CircuitBreaker = MagicMock
sys.modules["services.integration.circuit_breaker"] = _cb_mod

from services.integration.http_client import RetryableClient

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

SVC_MOD = "services.integration.http_client"


# ──────────────────────────────────────────────
# __init__
# ──────────────────────────────────────────────
class TestInit:

    def test_stores_store_url(self):
        c = RetryableClient("https://shop.com", "shopify")
        assert c.store_url == "https://shop.com"

    def test_stores_platform(self):
        c = RetryableClient("https://shop.com", "shopify")
        assert c.platform == "shopify"

    def test_default_retry_config(self):
        c = RetryableClient("https://shop.com", "shopify")
        assert c.retry_config is not None

    def test_custom_retry_config(self):
        cfg = _FakeRetryConfig(max_retries=5)
        c = RetryableClient("https://shop.com", "shopify", retry_config=cfg)
        assert c.retry_config is cfg

    def test_default_timeout(self):
        c = RetryableClient("https://shop.com", "shopify")
        assert c.timeout == 30.0

    def test_custom_timeout(self):
        c = RetryableClient("https://shop.com", "shopify", timeout=60.0)
        assert c.timeout == 60.0

    def test_use_circuit_breaker_default_true(self):
        c = RetryableClient("https://shop.com", "shopify")
        assert c.use_circuit_breaker is True

    def test_use_circuit_breaker_false(self):
        c = RetryableClient("https://shop.com", "shopify", use_circuit_breaker=False)
        assert c.use_circuit_breaker is False

    def test_client_initially_none(self):
        c = RetryableClient("https://shop.com", "shopify")
        assert c._client is None

    def test_circuit_breaker_initially_none(self):
        c = RetryableClient("https://shop.com", "shopify")
        assert c._circuit_breaker is None


# ──────────────────────────────────────────────
# Context manager
# ──────────────────────────────────────────────
class TestContextManager:

    @pytest.mark.asyncio
    async def test_aenter_creates_client(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient") as MockClient:
            c = RetryableClient("https://shop.com", "shopify")
            result = await c.__aenter__()
            MockClient.assert_called_once_with(timeout=30.0)
            assert result is c

    @pytest.mark.asyncio
    async def test_aenter_gets_circuit_breaker(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient"):
            with patch(f"{SVC_MOD}.circuit_breaker_registry") as mock_reg:
                mock_cb = MagicMock()
                mock_reg.get = AsyncMock(return_value=mock_cb)
                c = RetryableClient("https://shop.com", "shopify")
                await c.__aenter__()
                mock_reg.get.assert_called_once_with("https://shop.com")
                assert c._circuit_breaker is mock_cb

    @pytest.mark.asyncio
    async def test_aenter_skips_circuit_breaker_when_disabled(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient"):
            with patch(f"{SVC_MOD}.circuit_breaker_registry") as mock_reg:
                c = RetryableClient("https://shop.com", "shopify", use_circuit_breaker=False)
                await c.__aenter__()
                mock_reg.get.assert_not_called()
                assert c._circuit_breaker is None

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        mock_client = AsyncMock()
        c = RetryableClient("https://shop.com", "shopify")
        c._client = mock_client
        await c.__aexit__(None, None, None)
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_handles_no_client(self):
        c = RetryableClient("https://shop.com", "shopify")
        c._client = None
        await c.__aexit__(None, None, None)  # No error


# ──────────────────────────────────────────────
# HTTP methods
# ──────────────────────────────────────────────
class TestHttpMethods:

    @pytest.mark.asyncio
    async def test_get_calls_request_with_GET(self):
        c = RetryableClient("https://shop.com", "shopify")
        c._request = AsyncMock(return_value=MagicMock())
        await c.get("https://shop.com/api/products")
        c._request.assert_called_once()
        args = c._request.call_args
        assert args[0][0] == "GET"
        assert args[0][1] == "https://shop.com/api/products"

    @pytest.mark.asyncio
    async def test_post_calls_request_with_POST(self):
        c = RetryableClient("https://shop.com", "shopify")
        c._request = AsyncMock(return_value=MagicMock())
        await c.post("https://shop.com/api/products", json={"name": "test"})
        args = c._request.call_args
        assert args[0][0] == "POST"

    @pytest.mark.asyncio
    async def test_put_calls_request_with_PUT(self):
        c = RetryableClient("https://shop.com", "shopify")
        c._request = AsyncMock(return_value=MagicMock())
        await c.put("https://shop.com/api/products/1")
        args = c._request.call_args
        assert args[0][0] == "PUT"

    @pytest.mark.asyncio
    async def test_delete_calls_request_with_DELETE(self):
        c = RetryableClient("https://shop.com", "shopify")
        c._request = AsyncMock(return_value=MagicMock())
        await c.delete("https://shop.com/api/products/1")
        args = c._request.call_args
        assert args[0][0] == "DELETE"

    @pytest.mark.asyncio
    async def test_get_passes_kwargs(self):
        c = RetryableClient("https://shop.com", "shopify")
        c._request = AsyncMock(return_value=MagicMock())
        await c.get("https://shop.com/api", headers={"X-Custom": "val"})
        kwargs = c._request.call_args[1]
        assert kwargs["headers"] == {"X-Custom": "val"}

    @pytest.mark.asyncio
    async def test_get_operation_name_contains_url(self):
        c = RetryableClient("https://shop.com", "shopify")
        c._request = AsyncMock(return_value=MagicMock())
        url = "https://shop.com/api/products"
        await c.get(url)
        op_name = c._request.call_args[0][2]
        assert "GET" in op_name
        assert url in op_name


# ──────────────────────────────────────────────
# _request — routing through circuit breaker
# ──────────────────────────────────────────────
class TestRequestRouting:

    @pytest.mark.asyncio
    async def test_with_circuit_breaker(self):
        c = RetryableClient("https://shop.com", "shopify")
        mock_cb = AsyncMock()
        mock_cb.__aenter__ = AsyncMock(return_value=mock_cb)
        mock_cb.__aexit__ = AsyncMock(return_value=False)
        c._circuit_breaker = mock_cb
        c._do_request_with_retry = AsyncMock(return_value=MagicMock())

        await c._request("GET", "https://shop.com/api", "test")
        mock_cb.__aenter__.assert_called_once()

    @pytest.mark.asyncio
    async def test_without_circuit_breaker(self):
        c = RetryableClient("https://shop.com", "shopify")
        c._circuit_breaker = None
        c._do_request_with_retry = AsyncMock(return_value=MagicMock())

        await c._request("GET", "https://shop.com/api", "test")
        c._do_request_with_retry.assert_called_once()


# ──────────────────────────────────────────────
# _do_request_with_retry
# ──────────────────────────────────────────────
class TestDoRequestWithRetry:

    @pytest.mark.asyncio
    async def test_waits_for_rate_limit(self):
        with patch(f"{SVC_MOD}.rate_limit_tracker") as mock_rl:
            mock_rl.wait_if_needed = AsyncMock()
            with patch(f"{SVC_MOD}.execute_with_retry", new_callable=AsyncMock) as mock_retry:
                mock_retry.return_value = MagicMock()
                c = RetryableClient("https://shop.com", "shopify")
                c._client = MagicMock()
                await c._do_request_with_retry("GET", "https://shop.com/api", "test")
                mock_rl.wait_if_needed.assert_called_once_with("https://shop.com")

    @pytest.mark.asyncio
    async def test_calls_execute_with_retry(self):
        with patch(f"{SVC_MOD}.rate_limit_tracker") as mock_rl:
            mock_rl.wait_if_needed = AsyncMock()
            with patch(f"{SVC_MOD}.execute_with_retry", new_callable=AsyncMock) as mock_retry:
                mock_retry.return_value = MagicMock()
                c = RetryableClient("https://shop.com", "shopify")
                c._client = MagicMock()
                await c._do_request_with_retry("GET", "https://shop.com/api", "op")
                mock_retry.assert_called_once()
                call_kw = mock_retry.call_args[1]
                assert call_kw["config"] is c.retry_config
                assert call_kw["operation_name"] == "op"



                