"""
Tests for services/payment/mnee_client.py

MneeEnvironment enum, MneeClient — low-level HTTP client for MNEE API.
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from enum import Enum

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED = [
    "httpx",
    "services.payment.exceptions",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# httpx
_httpx = MagicMock()
_httpx.AsyncClient = MagicMock
_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
_httpx.RequestError = type("RequestError", (Exception,), {})
sys.modules["httpx"] = _httpx

# exceptions
class MneeApiError(Exception):
    def __init__(self, message="", status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

class MneeNetworkError(Exception):
    def __init__(self, message="", original_error=None):
        super().__init__(message)
        self.original_error = original_error

class MneeConfigError(Exception):
    def __init__(self, message="", missing_key=None):
        super().__init__(message)
        self.missing_key = missing_key

_exc_mod = MagicMock()
_exc_mod.MneeApiError = MneeApiError
_exc_mod.MneeNetworkError = MneeNetworkError
_exc_mod.MneeConfigError = MneeConfigError
sys.modules["services.payment.exceptions"] = _exc_mod

from services.payment.mnee_client import MneeClient, MneeEnvironment

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

SVC_MOD = "services.payment.mnee_client"


# ──────────────────────────────────────────────
# MneeEnvironment
# ──────────────────────────────────────────────
class TestMneeEnvironment:

    def test_sandbox(self):
        assert MneeEnvironment.SANDBOX.value == "sandbox"

    def test_production(self):
        assert MneeEnvironment.PRODUCTION.value == "production"

    def test_is_str_enum(self):
        assert isinstance(MneeEnvironment.SANDBOX, str)

    def test_count(self):
        assert len(MneeEnvironment) == 2


# ──────────────────────────────────────────────
# MneeClient.__init__
# ──────────────────────────────────────────────
class TestMneeClientInit:

    def test_stores_api_key(self):
        c = MneeClient(api_key="test-key")
        assert c.api_key == "test-key"

    def test_default_sandbox(self):
        c = MneeClient(api_key="key")
        assert c.environment == MneeEnvironment.SANDBOX

    def test_production_env(self):
        c = MneeClient(api_key="key", environment="production")
        assert c.environment == MneeEnvironment.PRODUCTION

    def test_sandbox_base_url(self):
        c = MneeClient(api_key="key", environment="sandbox")
        assert "sandbox" in c.base_url

    def test_production_base_url(self):
        c = MneeClient(api_key="key", environment="production")
        assert "sandbox" not in c.base_url
        assert "proxy-api.mnee.net" in c.base_url

    def test_default_timeout(self):
        c = MneeClient(api_key="key")
        assert c.timeout == 30.0

    def test_custom_timeout(self):
        c = MneeClient(api_key="key", timeout=60.0)
        assert c.timeout == 60.0

    def test_client_initially_none(self):
        c = MneeClient(api_key="key")
        assert c._client is None

    def test_empty_api_key_raises(self):
        with pytest.raises(MneeConfigError):
            MneeClient(api_key="")

    def test_none_api_key_raises(self):
        with pytest.raises(MneeConfigError):
            MneeClient(api_key=None)


# ──────────────────────────────────────────────
# _headers
# ──────────────────────────────────────────────
class TestHeaders:

    def test_contains_auth_token(self):
        c = MneeClient(api_key="my-secret-key")
        assert c._headers["auth_token"] == "my-secret-key"

    def test_contains_content_type(self):
        c = MneeClient(api_key="key")
        assert c._headers["Content-Type"] == "application/json"

    def test_contains_accept(self):
        c = MneeClient(api_key="key")
        assert c._headers["Accept"] == "application/json"


# ──────────────────────────────────────────────
# _get_client
# ──────────────────────────────────────────────
class TestGetClient:

    @pytest.mark.asyncio
    async def test_creates_client(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.is_closed = False
            MockClient.return_value = mock_instance

            c = MneeClient(api_key="key")
            client = await c._get_client()
            MockClient.assert_called_once()
            assert client is mock_instance

    @pytest.mark.asyncio
    async def test_caches_client(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.is_closed = False
            MockClient.return_value = mock_instance

            c = MneeClient(api_key="key")
            c1 = await c._get_client()
            c2 = await c._get_client()
            assert MockClient.call_count == 1
            assert c1 is c2

    @pytest.mark.asyncio
    async def test_recreates_if_closed(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient") as MockClient:
            new_client = MagicMock()
            new_client.is_closed = False
            MockClient.return_value = new_client

            c = MneeClient(api_key="key")
            # Pre-set a closed client
            closed_client = MagicMock()
            closed_client.is_closed = True
            c._client = closed_client

            client = await c._get_client()
            MockClient.assert_called_once()
            assert client is new_client


# ──────────────────────────────────────────────
# close
# ──────────────────────────────────────────────
class TestClose:

    @pytest.mark.asyncio
    async def test_closes_client(self):
        c = MneeClient(api_key="key")
        mock_client = AsyncMock()
        mock_client.is_closed = False
        c._client = mock_client
        await c.close()
        mock_client.aclose.assert_called_once()
        assert c._client is None

    @pytest.mark.asyncio
    async def test_no_client_noop(self):
        c = MneeClient(api_key="key")
        c._client = None
        await c.close()  # No error

    @pytest.mark.asyncio
    async def test_already_closed_noop(self):
        c = MneeClient(api_key="key")
        mock_client = MagicMock()
        mock_client.is_closed = True
        c._client = mock_client
        await c.close()  # No error


# ──────────────────────────────────────────────
# _request
# ──────────────────────────────────────────────
class TestRequest:

    @pytest.mark.asyncio
    async def test_successful_json_response(self):
        c = MneeClient(api_key="key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"data": "test"}

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request.return_value = mock_response
        c._client = mock_client

        result = await c._request("GET", "/v1/config")
        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_plain_text_response(self):
        c = MneeClient(api_key="key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = "ticket-123"

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request.return_value = mock_response
        c._client = mock_client

        result = await c._request("POST", "/v2/transfer", json_data={"rawtx": "abc"})
        assert result == "ticket-123"

    @pytest.mark.asyncio
    async def test_400_raises_api_error(self):
        c = MneeClient(api_key="key")
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "bad request"}

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request.return_value = mock_response
        c._client = mock_client

        with pytest.raises(MneeApiError) as exc_info:
            await c._request("GET", "/v1/bad")
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_500_raises_api_error(self):
        c = MneeClient(api_key="key")
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "server error"}

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request.return_value = mock_response
        c._client = mock_client

        with pytest.raises(MneeApiError) as exc_info:
            await c._request("GET", "/v1/fail")
        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_timeout_raises_network_error(self):
        c = MneeClient(api_key="key")

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request.side_effect = _httpx.TimeoutException("timeout")
        c._client = mock_client

        with pytest.raises(MneeNetworkError):
            await c._request("GET", "/v1/config")

    @pytest.mark.asyncio
    async def test_request_error_raises_network_error(self):
        c = MneeClient(api_key="key")

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request.side_effect = _httpx.RequestError("connection failed")
        c._client = mock_client

        with pytest.raises(MneeNetworkError):
            await c._request("GET", "/v1/config")

    @pytest.mark.asyncio
    async def test_passes_params_and_json(self):
        c = MneeClient(api_key="key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = []

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.request.return_value = mock_response
        c._client = mock_client

        await c._request("POST", "/v2/balance",
                         params={"page": "1"}, json_data=["addr1"])

        call_kw = mock_client.request.call_args[1]
        assert call_kw["params"] == {"page": "1"}
        assert call_kw["json"] == ["addr1"]


# ──────────────────────────────────────────────
# _parse_error
# ──────────────────────────────────────────────
class TestParseError:

    def test_json_error(self):
        c = MneeClient(api_key="key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"message": "bad", "code": 400}
        result = c._parse_error(mock_resp)
        assert result["message"] == "bad"

    def test_non_json_error(self):
        c = MneeClient(api_key="key")
        mock_resp = MagicMock()
        mock_resp.json.side_effect = Exception("not json")
        mock_resp.text = "Server Error"
        mock_resp.status_code = 500
        result = c._parse_error(mock_resp)
        assert result["message"] == "Server Error"
        assert result["status"] == 500


# ──────────────────────────────────────────────
# API methods
# ──────────────────────────────────────────────
class TestApiMethods:

    @pytest.mark.asyncio
    async def test_get_config(self):
        c = MneeClient(api_key="key")
        c._request = AsyncMock(return_value={"decimals": 5})
        result = await c.get_config()
        c._request.assert_called_once_with("GET", "/v1/config")
        assert result["decimals"] == 5

    @pytest.mark.asyncio
    async def test_get_balances(self):
        c = MneeClient(api_key="key")
        c._request = AsyncMock(return_value=[{"amt": 100}])
        result = await c.get_balances(["addr1"])
        c._request.assert_called_once_with("POST", "/v2/balance", json_data=["addr1"])

    @pytest.mark.asyncio
    async def test_get_utxos(self):
        c = MneeClient(api_key="key")
        c._request = AsyncMock(return_value=[])
        await c.get_utxos(["addr1"], page=2, size=20)
        c._request.assert_called_once_with(
            "POST", "/v2/utxos",
            params={"page": "2", "size": "20"},
            json_data=["addr1"],
        )

    @pytest.mark.asyncio
    async def test_get_transaction(self):
        c = MneeClient(api_key="key")
        c._request = AsyncMock(return_value={"txid": "abc"})
        result = await c.get_transaction("abc")
        c._request.assert_called_once_with("GET", "/v1/tx/abc")

    @pytest.mark.asyncio
    async def test_get_transactions(self):
        c = MneeClient(api_key="key")
        c._request = AsyncMock(return_value=[])
        await c.get_transactions(["addr1"], limit=50)
        call_kw = c._request.call_args[1]
        assert call_kw["params"]["limit"] == 50
        assert call_kw["json_data"] == ["addr1"]

    @pytest.mark.asyncio
    async def test_get_transactions_with_from_score(self):
        c = MneeClient(api_key="key")
        c._request = AsyncMock(return_value=[])
        await c.get_transactions(["addr1"], from_score=100)
        call_kw = c._request.call_args[1]
        assert call_kw["params"]["from"] == 100

    @pytest.mark.asyncio
    async def test_submit_transfer_string_result(self):
        c = MneeClient(api_key="key")
        c._request = AsyncMock(return_value="ticket-id-123")
        result = await c.submit_transfer("rawtx-data")
        assert result == "ticket-id-123"

    @pytest.mark.asyncio
    async def test_submit_transfer_dict_result(self):
        c = MneeClient(api_key="key")
        c._request = AsyncMock(return_value={"ticketId": "tid-456"})
        result = await c.submit_transfer("rawtx-data")
        assert result == "tid-456"

    @pytest.mark.asyncio
    async def test_get_ticket(self):
        c = MneeClient(api_key="key")
        c._request = AsyncMock(return_value={"id": "t1", "status": "confirmed"})
        result = await c.get_ticket("t1")
        c._request.assert_called_once_with("GET", "/v2/ticket", params={"ticketID": "t1"})


        