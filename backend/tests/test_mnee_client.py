"""
Tests for services/payment/mnee_client.py — MneeClient

Covers:
- __init__: valid config, missing API key, environment mapping
- _headers property
- _get_client: creation, reuse, recreation after close
- close: open client, already closed, None client
- _request: success JSON, success text, 4xx/5xx errors, timeout, network error
- _parse_error: JSON parse, fallback to text
- API methods: get_config, get_balances, get_utxos, get_transaction,
  get_transactions, submit_transfer (str/dict), get_ticket
"""

import sys
import os
from types import ModuleType
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
#
# services/payment/__init__.py eagerly imports from mnee_service, base,
# subscription_service, eth_service, bsv_service. We pre-load the
# services.payment package as a bare ModuleType with the real __path__
# so Python can find mnee_client.py on disk WITHOUT executing __init__.py.
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session", "core.logging",
    "services.payment",
    "services.payment.exceptions",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# Ensure db.session / core.logging stubs
for _m in ("db.session", "core.logging"):
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()
if hasattr(sys.modules.get("core.logging"), "get_logger"):
    sys.modules["core.logging"].get_logger = MagicMock(return_value=MagicMock())

# Compute real filesystem paths
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure services package exists with real path
if "services" not in sys.modules:
    _svc = ModuleType("services")
    _svc.__path__ = [os.path.join(_backend_dir, "services")]
    _svc.__package__ = "services"
    sys.modules["services"] = _svc

# Pre-load services.payment as bare package (bypasses __init__.py eager imports)
_pay_pkg = ModuleType("services.payment")
_pay_pkg.__path__ = [os.path.join(_backend_dir, "services", "payment")]
_pay_pkg.__package__ = "services.payment"
sys.modules["services.payment"] = _pay_pkg

# Stub exceptions module with fake exception classes
_exc_stub = ModuleType("services.payment.exceptions")


class _FakeMneeApiError(Exception):
    def __init__(self, message="", status_code=None, response=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response = response


class _FakeMneeNetworkError(Exception):
    def __init__(self, message="", original_error=None):
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class _FakeMneeConfigError(Exception):
    def __init__(self, message="", missing_key=None):
        super().__init__(message)
        self.message = message
        self.missing_key = missing_key


_exc_stub.MneeApiError = _FakeMneeApiError
_exc_stub.MneeNetworkError = _FakeMneeNetworkError
_exc_stub.MneeConfigError = _FakeMneeConfigError
sys.modules["services.payment.exceptions"] = _exc_stub

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.payment.mnee_client import MneeClient, MneeEnvironment

# ---------------------------------------------------------------------------
# 3. Restore sys.modules
# ---------------------------------------------------------------------------
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m


# ===========================================================================
# Helpers
# ===========================================================================

def _make_response(status_code=200, headers=None, json_data=None, text="", content_type="application/json"):
    """Build a fake httpx.Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    _h = headers or {}
    if content_type:
        _h["content-type"] = content_type
    resp.headers = _h
    resp.json.return_value = json_data if json_data is not None else {}
    resp.text = text
    return resp


def _make_client(api_key="test-key-123", environment="sandbox", timeout=30.0):
    return MneeClient(api_key=api_key, environment=environment, timeout=timeout)


# ===========================================================================
# Tests
# ===========================================================================

class TestMneeEnvironment:
    """Test the MneeEnvironment enum."""

    def test_sandbox_value(self):
        assert MneeEnvironment.SANDBOX.value == "sandbox"

    def test_production_value(self):
        assert MneeEnvironment.PRODUCTION.value == "production"

    def test_is_str_enum(self):
        assert isinstance(MneeEnvironment.SANDBOX, str)


class TestMneeClientInit:
    """Test __init__."""

    def test_valid_sandbox(self):
        c = _make_client()
        assert c.api_key == "test-key-123"
        assert c.environment == MneeEnvironment.SANDBOX
        assert "sandbox" in c.base_url
        assert c.timeout == 30.0
        assert c._client is None

    def test_valid_production(self):
        c = _make_client(environment="production")
        assert c.environment == MneeEnvironment.PRODUCTION
        assert "proxy-api.mnee.net" in c.base_url
        assert "sandbox" not in c.base_url

    def test_custom_timeout(self):
        c = _make_client(timeout=60.0)
        assert c.timeout == 60.0

    def test_missing_api_key_raises(self):
        with pytest.raises(_FakeMneeConfigError):
            MneeClient(api_key="", environment="sandbox")

    def test_none_api_key_raises(self):
        with pytest.raises((_FakeMneeConfigError, TypeError)):
            MneeClient(api_key=None, environment="sandbox")

    def test_invalid_environment_raises(self):
        with pytest.raises(ValueError):
            MneeClient(api_key="key", environment="staging")


class TestHeaders:
    """Test _headers property."""

    def test_contains_auth_token(self):
        c = _make_client(api_key="my-secret")
        assert c._headers["auth_token"] == "my-secret"

    def test_content_type(self):
        c = _make_client()
        assert c._headers["Content-Type"] == "application/json"

    def test_accept_header(self):
        c = _make_client()
        assert c._headers["Accept"] == "application/json"


class TestGetClient:
    """Test _get_client."""

    @pytest.mark.asyncio
    async def test_creates_client_when_none(self):
        c = _make_client()
        with patch("services.payment.mnee_client.httpx.AsyncClient") as MockClient:
            mock_inst = MagicMock()
            mock_inst.is_closed = False
            MockClient.return_value = mock_inst

            result = await c._get_client()
            assert result is mock_inst
            MockClient.assert_called_once_with(
                base_url=c.base_url,
                headers=c._headers,
                timeout=c.timeout,
            )

    @pytest.mark.asyncio
    async def test_reuses_existing_client(self):
        c = _make_client()
        mock_client = MagicMock()
        mock_client.is_closed = False
        c._client = mock_client

        with patch("services.payment.mnee_client.httpx.AsyncClient") as MockClient:
            result = await c._get_client()
            assert result is mock_client
            MockClient.assert_not_called()

    @pytest.mark.asyncio
    async def test_recreates_closed_client(self):
        c = _make_client()
        old_client = MagicMock()
        old_client.is_closed = True
        c._client = old_client

        with patch("services.payment.mnee_client.httpx.AsyncClient") as MockClient:
            new_client = MagicMock()
            new_client.is_closed = False
            MockClient.return_value = new_client

            result = await c._get_client()
            assert result is new_client


class TestClose:
    """Test close method."""

    @pytest.mark.asyncio
    async def test_close_open_client(self):
        c = _make_client()
        mock_client = AsyncMock()
        mock_client.is_closed = False
        c._client = mock_client

        await c.close()
        mock_client.aclose.assert_awaited_once()
        assert c._client is None

    @pytest.mark.asyncio
    async def test_close_already_closed(self):
        c = _make_client()
        mock_client = AsyncMock()
        mock_client.is_closed = True
        c._client = mock_client

        await c.close()
        mock_client.aclose.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_none_client(self):
        c = _make_client()
        c._client = None
        await c.close()  # Should not raise


class TestRequest:
    """Test _request method."""

    @pytest.mark.asyncio
    async def test_success_json(self):
        c = _make_client()
        resp = _make_response(200, json_data={"approver": "0x123"})
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)
        mock_client.is_closed = False
        c._client = mock_client

        result = await c._request("GET", "/v1/config")
        assert result == {"approver": "0x123"}
        mock_client.request.assert_awaited_once_with(
            method="GET", url="/v1/config", params=None, json=None
        )

    @pytest.mark.asyncio
    async def test_success_text_response(self):
        c = _make_client()
        resp = _make_response(200, text="ticket-abc", content_type="text/plain")
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)
        mock_client.is_closed = False
        c._client = mock_client

        result = await c._request("POST", "/v2/transfer", json_data={"rawtx": "base64"})
        assert result == "ticket-abc"

    @pytest.mark.asyncio
    async def test_api_error_4xx(self):
        c = _make_client()
        resp = _make_response(400, json_data={"error": "bad request"})
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)
        mock_client.is_closed = False
        c._client = mock_client

        with pytest.raises(_FakeMneeApiError) as exc_info:
            await c._request("POST", "/v2/balance", json_data=["addr1"])
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_api_error_5xx(self):
        c = _make_client()
        resp = _make_response(500, json_data={"error": "server error"})
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)
        mock_client.is_closed = False
        c._client = mock_client

        with pytest.raises(_FakeMneeApiError) as exc_info:
            await c._request("GET", "/v1/config")
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_timeout_raises_network_error(self):
        import httpx as _httpx
        c = _make_client()
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=_httpx.TimeoutException("timeout"))
        mock_client.is_closed = False
        c._client = mock_client

        with pytest.raises(_FakeMneeNetworkError) as exc_info:
            await c._request("GET", "/v1/config")
        assert "timed out" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_request_error_raises_network_error(self):
        import httpx as _httpx
        c = _make_client()
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=_httpx.RequestError("conn refused", request=MagicMock())
        )
        mock_client.is_closed = False
        c._client = mock_client

        with pytest.raises(_FakeMneeNetworkError) as exc_info:
            await c._request("GET", "/v1/config")
        assert "Network error" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_passes_params_and_json(self):
        c = _make_client()
        resp = _make_response(200, json_data=[])
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=resp)
        mock_client.is_closed = False
        c._client = mock_client

        await c._request("POST", "/v2/utxos", params={"page": "1"}, json_data=["addr"])
        mock_client.request.assert_awaited_once_with(
            method="POST", url="/v2/utxos", params={"page": "1"}, json=["addr"]
        )


class TestParseError:
    """Test _parse_error."""

    def test_json_error(self):
        c = _make_client()
        resp = MagicMock()
        resp.json.return_value = {"error": "bad", "code": 123}
        result = c._parse_error(resp)
        assert result == {"error": "bad", "code": 123}

    def test_non_json_error(self):
        c = _make_client()
        resp = MagicMock()
        resp.json.side_effect = Exception("not json")
        resp.text = "Internal Server Error"
        resp.status_code = 500
        result = c._parse_error(resp)
        assert result["message"] == "Internal Server Error"
        assert result["status"] == 500


class TestGetConfig:
    """Test get_config API method."""

    @pytest.mark.asyncio
    async def test_get_config(self):
        c = _make_client()
        c._request = AsyncMock(return_value={"approver": "02bed", "decimals": 5})
        result = await c.get_config()
        c._request.assert_awaited_once_with("GET", "/v1/config")
        assert result["decimals"] == 5


class TestGetBalances:
    """Test get_balances API method."""

    @pytest.mark.asyncio
    async def test_get_balances(self):
        c = _make_client()
        expected = [{"address": "1A1Q", "amt": 30300303, "precised": 34.22}]
        c._request = AsyncMock(return_value=expected)
        result = await c.get_balances(["1A1Q"])
        c._request.assert_awaited_once_with("POST", "/v2/balance", json_data=["1A1Q"])
        assert result == expected

    @pytest.mark.asyncio
    async def test_get_balances_multiple(self):
        c = _make_client()
        c._request = AsyncMock(return_value=[])
        await c.get_balances(["addr1", "addr2", "addr3"])
        c._request.assert_awaited_once_with("POST", "/v2/balance", json_data=["addr1", "addr2", "addr3"])


class TestGetUtxos:
    """Test get_utxos API method."""

    @pytest.mark.asyncio
    async def test_get_utxos_defaults(self):
        c = _make_client()
        c._request = AsyncMock(return_value=[])
        await c.get_utxos(["addr1"])
        c._request.assert_awaited_once_with(
            "POST", "/v2/utxos",
            params={"page": "1", "size": "10"},
            json_data=["addr1"],
        )

    @pytest.mark.asyncio
    async def test_get_utxos_custom_page(self):
        c = _make_client()
        c._request = AsyncMock(return_value=[])
        await c.get_utxos(["addr1"], page=3, size=25)
        c._request.assert_awaited_once_with(
            "POST", "/v2/utxos",
            params={"page": "3", "size": "25"},
            json_data=["addr1"],
        )


class TestGetTransaction:
    """Test get_transaction API method."""

    @pytest.mark.asyncio
    async def test_get_transaction(self):
        c = _make_client()
        c._request = AsyncMock(return_value={"rawtx": "0x..."})
        result = await c.get_transaction("txid123")
        c._request.assert_awaited_once_with("GET", "/v1/tx/txid123")
        assert result["rawtx"] == "0x..."


class TestGetTransactions:
    """Test get_transactions API method."""

    @pytest.mark.asyncio
    async def test_defaults(self):
        c = _make_client()
        c._request = AsyncMock(return_value=[])
        await c.get_transactions(["addr1"])
        c._request.assert_awaited_once_with(
            "POST", "/v1/sync", params={"limit": 100}, json_data=["addr1"]
        )

    @pytest.mark.asyncio
    async def test_custom_limit(self):
        c = _make_client()
        c._request = AsyncMock(return_value=[])
        await c.get_transactions(["addr1"], limit=50)
        c._request.assert_awaited_once_with(
            "POST", "/v1/sync", params={"limit": 50}, json_data=["addr1"]
        )

    @pytest.mark.asyncio
    async def test_with_from_score(self):
        c = _make_client()
        c._request = AsyncMock(return_value=[])
        await c.get_transactions(["addr1"], from_score=999)
        c._request.assert_awaited_once_with(
            "POST", "/v1/sync", params={"limit": 100, "from": 999}, json_data=["addr1"]
        )

    @pytest.mark.asyncio
    async def test_from_score_zero_not_included(self):
        """from_score=0 is falsy, so 'from' param should NOT be included."""
        c = _make_client()
        c._request = AsyncMock(return_value=[])
        await c.get_transactions(["addr1"], from_score=0)
        call_kwargs = c._request.call_args
        assert "from" not in call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))


class TestSubmitTransfer:
    """Test submit_transfer API method."""

    @pytest.mark.asyncio
    async def test_returns_string_directly(self):
        c = _make_client()
        c._request = AsyncMock(return_value="ticket-abc-123")
        result = await c.submit_transfer("base64rawtx")
        c._request.assert_awaited_once_with("POST", "/v2/transfer", json_data={"rawtx": "base64rawtx"})
        assert result == "ticket-abc-123"

    @pytest.mark.asyncio
    async def test_returns_ticket_id_from_dict(self):
        c = _make_client()
        c._request = AsyncMock(return_value={"ticketId": "t-xyz"})
        result = await c.submit_transfer("rawtx")
        assert result == "t-xyz"

    @pytest.mark.asyncio
    async def test_returns_full_dict_when_no_ticket_id(self):
        c = _make_client()
        c._request = AsyncMock(return_value={"status": "queued"})
        result = await c.submit_transfer("rawtx")
        assert result == {"status": "queued"}


class TestGetTicket:
    """Test get_ticket API method."""

    @pytest.mark.asyncio
    async def test_get_ticket(self):
        c = _make_client()
        expected = {"id": "abc", "status": "confirmed", "tx_id": "0x123"}
        c._request = AsyncMock(return_value=expected)
        result = await c.get_ticket("abc")
        c._request.assert_awaited_once_with("GET", "/v2/ticket", params={"ticketID": "abc"})
        assert result == expected


        