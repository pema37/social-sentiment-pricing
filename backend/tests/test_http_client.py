"""
Tests for services/integration/http_client.py — RetryableClient

Covers:
- __init__ defaults and overrides
- __aenter__ / __aexit__ lifecycle
- _request with and without circuit breaker
- _do_request_with_retry: rate limiting, retry delegation, 429 handling
- Convenience methods: get, post, put, delete
"""

import sys
import os
from types import ModuleType
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session",
    "services.integration.retry",
    "services.integration.rate_limit",
    "services.integration.circuit_breaker",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# Ensure db.session stub
for _m in ("db.session"):
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

# Ensure parent packages exist with REAL filesystem paths
# so Python can resolve submodule imports on disk
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _pkg, _subdir in [
    ("services", "services"),
    ("services.integration", "services/integration"),
]:
    if _pkg not in sys.modules:
        _mod = ModuleType(_pkg)
        _mod.__path__ = [os.path.join(_backend_dir, _subdir)]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod

# Stub retry
_retry_stub = ModuleType("services.integration.retry")
_FakeRetryConfig = type("RetryConfig", (), {})
_retry_stub.RetryConfig = _FakeRetryConfig
_retry_stub.DEFAULT_RETRY_CONFIG = _FakeRetryConfig()
_retry_stub.execute_with_retry = AsyncMock()
sys.modules["services.integration.retry"] = _retry_stub

# Stub rate_limit
_rate_limit_stub = ModuleType("services.integration.rate_limit")
_fake_tracker = MagicMock()
_fake_tracker.wait_if_needed = AsyncMock()
_fake_tracker.update_from_response = AsyncMock()
_fake_tracker.mark_rate_limited = AsyncMock()
_rate_limit_stub.rate_limit_tracker = _fake_tracker
sys.modules["services.integration.rate_limit"] = _rate_limit_stub

# Stub circuit_breaker
_cb_stub = ModuleType("services.integration.circuit_breaker")


class _FakeCircuitBreaker:
    """Fake circuit breaker that supports async context manager."""
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        pass


_fake_registry = MagicMock()
_fake_registry.get = AsyncMock(return_value=_FakeCircuitBreaker())
_cb_stub.circuit_breaker_registry = _fake_registry
_cb_stub.CircuitBreaker = _FakeCircuitBreaker
sys.modules["services.integration.circuit_breaker"] = _cb_stub

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.integration.http_client import RetryableClient

# ---------------------------------------------------------------------------
# 3. Restore sys.modules
# ---------------------------------------------------------------------------
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

# Keep references for test use
_execute_with_retry = _retry_stub.execute_with_retry
_rate_limit_tracker = _fake_tracker
_circuit_breaker_registry = _fake_registry


# ===========================================================================
# Helpers
# ===========================================================================

def _make_response(status_code=200, headers=None, json_data=None):
    """Build a fake httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx as _httpx
        resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


# ===========================================================================
# Tests
# ===========================================================================

class TestRetryableClientInit:
    """Test __init__ defaults and overrides."""

    def test_defaults(self):
        c = RetryableClient("https://store.myshopify.com", "shopify")
        assert c.store_url == "https://store.myshopify.com"
        assert c.platform == "shopify"
        assert c.timeout == 30.0
        assert c.use_circuit_breaker is True
        assert c._client is None
        assert c._circuit_breaker is None

    def test_custom_timeout(self):
        c = RetryableClient("https://store.com", "woocommerce", timeout=60.0)
        assert c.timeout == 60.0

    def test_custom_retry_config(self):
        custom = _FakeRetryConfig()
        c = RetryableClient("https://s.com", "shopify", retry_config=custom)
        assert c.retry_config is custom

    def test_circuit_breaker_disabled(self):
        c = RetryableClient("https://s.com", "shopify", use_circuit_breaker=False)
        assert c.use_circuit_breaker is False


class TestRetryableClientLifecycle:
    """Test __aenter__ / __aexit__."""

    @pytest.mark.asyncio
    async def test_aenter_creates_client(self):
        rc = RetryableClient("https://s.com", "shopify")
        with patch("services.integration.http_client.httpx.AsyncClient") as MockClient:
            mock_instance = AsyncMock()
            MockClient.return_value = mock_instance
            result = await rc.__aenter__()
            assert result is rc
            MockClient.assert_called_once_with(timeout=30.0)
            assert rc._client is mock_instance

    @pytest.mark.asyncio
    async def test_aenter_gets_circuit_breaker(self):
        rc = RetryableClient("https://s.com", "shopify", use_circuit_breaker=True)
        with patch("services.integration.http_client.circuit_breaker_registry", _fake_registry):
            with patch("services.integration.http_client.httpx.AsyncClient"):
                await rc.__aenter__()
                _fake_registry.get.assert_awaited_with("https://s.com")

    @pytest.mark.asyncio
    async def test_aenter_no_circuit_breaker_when_disabled(self):
        rc = RetryableClient("https://s.com", "shopify", use_circuit_breaker=False)
        with patch("services.integration.http_client.httpx.AsyncClient"):
            await rc.__aenter__()
            assert rc._circuit_breaker is None

    @pytest.mark.asyncio
    async def test_aexit_closes_client(self):
        rc = RetryableClient("https://s.com", "shopify")
        mock_client = AsyncMock()
        rc._client = mock_client
        await rc.__aexit__(None, None, None)
        mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_aexit_no_client(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._client = None
        await rc.__aexit__(None, None, None)


class TestRequestWithCircuitBreaker:
    """Test _request dispatches through circuit breaker when enabled."""

    @pytest.mark.asyncio
    async def test_request_with_circuit_breaker(self):
        rc = RetryableClient("https://s.com", "shopify")
        cb = _FakeCircuitBreaker()
        rc._circuit_breaker = cb
        rc._do_request_with_retry = AsyncMock(return_value="ok")

        result = await rc._request("GET", "/test", "op")
        rc._do_request_with_retry.assert_awaited_once_with("GET", "/test", "op")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_request_without_circuit_breaker(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._circuit_breaker = None
        rc._do_request_with_retry = AsyncMock(return_value="direct")

        result = await rc._request("POST", "/x", "op")
        rc._do_request_with_retry.assert_awaited_once_with("POST", "/x", "op")
        assert result == "direct"


class TestDoRequestWithRetry:
    """Test _do_request_with_retry: rate limit waits, response header updates, 429 handling."""

    def setup_method(self):
        """Reset shared mocks before each test."""
        _rate_limit_tracker.wait_if_needed.reset_mock()
        _rate_limit_tracker.update_from_response.reset_mock()
        _rate_limit_tracker.mark_rate_limited.reset_mock()
        
    @pytest.mark.asyncio
    async def test_calls_rate_limit_wait(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._client = AsyncMock()
        fake_resp = _make_response(200)
        rc._client.request = AsyncMock(return_value=fake_resp)

        with patch("services.integration.http_client.rate_limit_tracker", _rate_limit_tracker):
            with patch("services.integration.http_client.execute_with_retry", new_callable=AsyncMock) as mock_ewr:
                async def run_callback(fn, config=None, operation_name=None):
                    return await fn()
                mock_ewr.side_effect = run_callback

                await rc._do_request_with_retry("GET", "/url", "op")
                _rate_limit_tracker.wait_if_needed.assert_awaited_with("https://s.com")

    @pytest.mark.asyncio
    async def test_updates_rate_limit_from_response(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._client = AsyncMock()
        fake_resp = _make_response(200, headers={"X-Rate-Limit": "40"})
        rc._client.request = AsyncMock(return_value=fake_resp)

        with patch("services.integration.http_client.rate_limit_tracker", _rate_limit_tracker):
            with patch("services.integration.http_client.execute_with_retry", new_callable=AsyncMock) as mock_ewr:
                async def run_callback(fn, config=None, operation_name=None):
                    return await fn()
                mock_ewr.side_effect = run_callback

                await rc._do_request_with_retry("GET", "/url", "op")
                _rate_limit_tracker.update_from_response.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_429_marks_rate_limited(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._client = AsyncMock()
        fake_resp = _make_response(429, headers={"Retry-After": "5"})
        rc._client.request = AsyncMock(return_value=fake_resp)

        with patch("services.integration.http_client.rate_limit_tracker", _rate_limit_tracker):
            with patch("services.integration.http_client.execute_with_retry", new_callable=AsyncMock) as mock_ewr:
                async def run_callback(fn, config=None, operation_name=None):
                    return await fn()
                mock_ewr.side_effect = run_callback

                with pytest.raises(Exception):
                    await rc._do_request_with_retry("GET", "/url", "op")

                _rate_limit_tracker.mark_rate_limited.assert_awaited_with("https://s.com", 5)

    @pytest.mark.asyncio
    async def test_429_no_retry_after_header(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._client = AsyncMock()
        fake_resp = _make_response(429, headers={})
        rc._client.request = AsyncMock(return_value=fake_resp)

        with patch("services.integration.http_client.rate_limit_tracker", _rate_limit_tracker):
            with patch("services.integration.http_client.execute_with_retry", new_callable=AsyncMock) as mock_ewr:
                async def run_callback(fn, config=None, operation_name=None):
                    return await fn()
                mock_ewr.side_effect = run_callback

                with pytest.raises(Exception):
                    await rc._do_request_with_retry("GET", "/url", "op")

                _rate_limit_tracker.mark_rate_limited.assert_awaited_with("https://s.com", None)

    @pytest.mark.asyncio
    async def test_passes_kwargs_to_client_request(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._client = AsyncMock()
        fake_resp = _make_response(200)
        rc._client.request = AsyncMock(return_value=fake_resp)

        with patch("services.integration.http_client.rate_limit_tracker", _rate_limit_tracker):
            with patch("services.integration.http_client.execute_with_retry", new_callable=AsyncMock) as mock_ewr:
                async def run_callback(fn, config=None, operation_name=None):
                    return await fn()
                mock_ewr.side_effect = run_callback

                await rc._do_request_with_retry("POST", "/url", "op", json={"a": 1})
                rc._client.request.assert_awaited_with("POST", "/url", json={"a": 1})

    @pytest.mark.asyncio
    async def test_delegates_to_execute_with_retry(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._client = AsyncMock()

        with patch("services.integration.http_client.rate_limit_tracker", _rate_limit_tracker):
            with patch("services.integration.http_client.execute_with_retry", new_callable=AsyncMock) as mock_ewr:
                mock_ewr.return_value = "retry_result"
                result = await rc._do_request_with_retry("GET", "/x", "my_op")
                mock_ewr.assert_awaited_once()
                call_kwargs = mock_ewr.call_args
                assert call_kwargs.kwargs.get("config") is rc.retry_config
                assert call_kwargs.kwargs.get("operation_name") == "my_op"
                assert result == "retry_result"


class TestConvenienceMethods:
    """Test get/post/put/delete convenience wrappers."""

    @pytest.mark.asyncio
    async def test_get(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._request = AsyncMock(return_value="resp")
        result = await rc.get("/products", headers={"X": "1"})
        rc._request.assert_awaited_once_with("GET", "/products", "GET /products", headers={"X": "1"})
        assert result == "resp"

    @pytest.mark.asyncio
    async def test_post(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._request = AsyncMock(return_value="resp")
        result = await rc.post("/products", json={"title": "T"})
        rc._request.assert_awaited_once_with("POST", "/products", "POST /products", json={"title": "T"})
        assert result == "resp"

    @pytest.mark.asyncio
    async def test_put(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._request = AsyncMock(return_value="resp")
        result = await rc.put("/products/1", json={"title": "U"})
        rc._request.assert_awaited_once_with("PUT", "/products/1", "PUT /products/1", json={"title": "U"})
        assert result == "resp"

    @pytest.mark.asyncio
    async def test_delete(self):
        rc = RetryableClient("https://s.com", "shopify")
        rc._request = AsyncMock(return_value="resp")
        result = await rc.delete("/products/1")
        rc._request.assert_awaited_once_with("DELETE", "/products/1", "DELETE /products/1")
        assert result == "resp"

        