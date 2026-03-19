"""
Tests for services/payment/bsv_service.py

BSVPaymentService — WhatsOnChain-based BSV payment verification.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED = [
    "httpx",
    "services.payment.base",
    "schemas.payment",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# httpx
_httpx = MagicMock()
_httpx.AsyncClient = MagicMock
_httpx.HTTPStatusError = type(
    "HTTPStatusError",
    (Exception,),
    {
        "__init__": lambda self, *a, **kw: None,
    },
)
sys.modules["httpx"] = _httpx


# base
class _FakePaymentBase:
    def _create_verification_result(self, **kwargs):
        return MagicMock(**kwargs)


_base_mod = MagicMock()
_base_mod.PaymentVerificationService = _FakePaymentBase
sys.modules["services.payment.base"] = _base_mod


# schemas.payment
class _FakeVerification:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


_schema_mod = MagicMock()
_schema_mod.TransactionVerification = _FakeVerification
sys.modules["schemas.payment"] = _schema_mod

from services.payment.bsv_service import BSVPaymentService

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

SVC_MOD = "services.payment.bsv_service"


def _make_service():
    svc = BSVPaymentService()
    svc.api_key = "test-key"
    return svc


# ──────────────────────────────────────────────
# Init / properties
# ──────────────────────────────────────────────
class TestInit:
    def test_network_name(self):
        svc = BSVPaymentService()
        assert svc.network_name == "bsv"

    def test_is_available(self):
        svc = BSVPaymentService()
        assert svc.is_available is True

    def test_client_initially_none(self):
        svc = BSVPaymentService()
        assert svc._client is None


# ──────────────────────────────────────────────
# _get_client
# ──────────────────────────────────────────────
class TestGetClient:
    @pytest.mark.asyncio
    async def test_creates_client(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient") as MockClient:
            MockClient.return_value = MagicMock()
            svc = _make_service()
            await svc._get_client()
            MockClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_caches_client(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient") as MockClient:
            MockClient.return_value = MagicMock()
            svc = _make_service()
            await svc._get_client()
            await svc._get_client()
            assert MockClient.call_count == 1

    @pytest.mark.asyncio
    async def test_includes_auth_header_when_key(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient") as MockClient:
            MockClient.return_value = MagicMock()
            svc = _make_service()
            svc.api_key = "my-key"
            await svc._get_client()
            call_kw = MockClient.call_args[1]
            assert call_kw["headers"]["Authorization"] == "Bearer my-key"


# ──────────────────────────────────────────────
# _extract_memo
# ──────────────────────────────────────────────
class TestExtractMemo:
    def test_op_return_hex(self):
        svc = _make_service()
        vout = [
            {
                "scriptPubKey": {
                    "asm": "OP_RETURN " + b"SSP-abc12345".hex(),
                }
            }
        ]
        result = svc._extract_memo(vout)
        assert result is not None
        assert "SSP" in result

    def test_op_false_op_return(self):
        svc = _make_service()
        vout = [
            {
                "scriptPubKey": {
                    "asm": "0 OP_RETURN " + b"hello".hex(),
                }
            }
        ]
        result = svc._extract_memo(vout)
        assert result is not None

    def test_op_return_field(self):
        svc = _make_service()
        vout = [
            {
                "scriptPubKey": {
                    "asm": "some other script",
                    "opReturn": "SSP-12345678",
                }
            }
        ]
        result = svc._extract_memo(vout)
        assert result == "SSP-12345678"

    def test_no_op_return(self):
        svc = _make_service()
        vout = [
            {
                "scriptPubKey": {
                    "asm": "OP_DUP OP_HASH160 abc OP_EQUALVERIFY OP_CHECKSIG",
                }
            }
        ]
        result = svc._extract_memo(vout)
        assert result is None

    def test_empty_vout(self):
        svc = _make_service()
        assert svc._extract_memo([]) is None

    def test_invalid_hex_skipped(self):
        svc = _make_service()
        vout = [
            {
                "scriptPubKey": {
                    "asm": "OP_RETURN ZZZZ",  # not valid hex
                }
            }
        ]
        result = svc._extract_memo(vout)
        assert result is None

    def test_short_decoded_skipped(self):
        svc = _make_service()
        # "ab" decodes to 1 byte — less than 3 chars
        vout = [
            {
                "scriptPubKey": {
                    "asm": "OP_RETURN 6162",  # "ab" — 2 chars, skipped
                }
            }
        ]
        result = svc._extract_memo(vout)
        assert result is None


# ──────────────────────────────────────────────
# verify_transaction
# ──────────────────────────────────────────────
class TestVerifyTransaction:
    @pytest.mark.asyncio
    async def test_not_verified_passes_through(self):
        svc = _make_service()
        failed = MagicMock(verified=False)
        svc.get_transaction_status = AsyncMock(return_value=failed)
        result = await svc.verify_transaction("txhash", 100, "addr")
        assert result is failed

    @pytest.mark.asyncio
    async def test_memo_mismatch(self):
        svc = _make_service()
        tx_result = MagicMock(
            verified=True,
            memo="SSP-wrong",
            confirmations=5,
            block_height=100,
        )
        svc.get_transaction_status = AsyncMock(return_value=tx_result)
        svc._create_verification_result = MagicMock(return_value=MagicMock(verified=False))

        result = await svc.verify_transaction("txhash", 100, "addr", expected_memo="SSP-correct")
        assert result.verified is False

    @pytest.mark.asyncio
    async def test_memo_match_case_insensitive(self):
        svc = _make_service()
        tx_result = MagicMock(
            verified=True,
            memo="SSP-ABC123",
            confirmations=5,
            block_height=100,
            timestamp=None,
        )
        svc.get_transaction_status = AsyncMock(return_value=tx_result)
        svc._create_verification_result = MagicMock(return_value=MagicMock(verified=True))

        result = await svc.verify_transaction("txhash", 100, "addr", expected_memo="ssp-abc123")
        assert result.verified is True

    @pytest.mark.asyncio
    async def test_no_memo_check_when_none(self):
        svc = _make_service()
        tx_result = MagicMock(
            verified=True,
            memo="anything",
            confirmations=5,
            block_height=100,
            timestamp=None,
        )
        svc.get_transaction_status = AsyncMock(return_value=tx_result)
        svc._create_verification_result = MagicMock(return_value=MagicMock(verified=True))

        result = await svc.verify_transaction("txhash", 100, "addr", expected_memo=None)
        assert result.verified is True

    @pytest.mark.asyncio
    async def test_exception_returns_unverified(self):
        svc = _make_service()
        svc.get_transaction_status = AsyncMock(side_effect=Exception("network"))
        svc._create_verification_result = MagicMock(return_value=MagicMock(verified=False))

        result = await svc.verify_transaction("txhash", 100, "addr")
        assert result.verified is False


# ──────────────────────────────────────────────
# get_transaction_status
# ──────────────────────────────────────────────
class TestGetTransactionStatus:
    @pytest.mark.asyncio
    async def test_404_not_found(self):
        svc = _make_service()
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        svc._get_client = AsyncMock(return_value=mock_client)
        svc._create_verification_result = MagicMock(return_value=MagicMock(verified=False))

        result = await svc.get_transaction_status("0xbad")
        assert result.verified is False

    @pytest.mark.asyncio
    async def test_confirmed_transaction(self):
        svc = _make_service()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "confirmations": 6,
            "blockheight": 800000,
            "time": 1700000000,
            "vout": [],
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        svc._get_client = AsyncMock(return_value=mock_client)
        svc._create_verification_result = MagicMock(return_value=MagicMock(verified=True))

        result = await svc.get_transaction_status("txhash")
        assert result.verified is True

    @pytest.mark.asyncio
    async def test_unconfirmed_transaction(self):
        svc = _make_service()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "confirmations": 0,
            "vout": [],
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        svc._get_client = AsyncMock(return_value=mock_client)
        svc._create_verification_result = MagicMock(return_value=MagicMock(verified=False))

        await svc.get_transaction_status("txhash")
        # verified = confirmations > 0, so False
        verify_call = svc._create_verification_result.call_args[1]
        assert verify_call["verified"] is False


# ──────────────────────────────────────────────
# close
# ──────────────────────────────────────────────
class TestClose:
    @pytest.mark.asyncio
    async def test_closes_client(self):
        svc = _make_service()
        mock_client = AsyncMock()
        svc._client = mock_client
        await svc.close()
        mock_client.aclose.assert_called_once()
        assert svc._client is None

    @pytest.mark.asyncio
    async def test_no_client_noop(self):
        svc = _make_service()
        svc._client = None
        await svc.close()
