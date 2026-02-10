"""
Tests for services/payment/eth_service.py

EthereumPaymentService — Etherscan-based MNEE ERC-20 verification.
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from datetime import datetime

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

from services.payment.eth_service import (
    EthereumPaymentService,
    MNEE_CONTRACT_ADDRESS,
    ETHERSCAN_API_URL,
)

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

SVC_MOD = "services.payment.eth_service"


# ── Helpers ───────────────────────────────────────────────────────

def _make_service():
    svc = EthereumPaymentService()
    svc.api_key = "test-key"
    return svc


# ──────────────────────────────────────────────
# Init / properties
# ──────────────────────────────────────────────
class TestInit:

    def test_network_name(self):
        svc = EthereumPaymentService()
        assert svc.network_name == "ethereum"

    def test_is_available_true(self):
        svc = EthereumPaymentService()
        assert svc.is_available is True

    def test_client_initially_none(self):
        svc = EthereumPaymentService()
        assert svc._client is None

    def test_mnee_contract_lowercase(self):
        svc = EthereumPaymentService()
        assert svc.mnee_contract == MNEE_CONTRACT_ADDRESS.lower()


# ──────────────────────────────────────────────
# _get_client
# ──────────────────────────────────────────────
class TestGetClient:

    @pytest.mark.asyncio
    async def test_creates_client(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value = mock_instance
            svc = _make_service()
            client = await svc._get_client()
            assert client is mock_instance

    @pytest.mark.asyncio
    async def test_caches_client(self):
        with patch(f"{SVC_MOD}.httpx.AsyncClient") as MockClient:
            MockClient.return_value = MagicMock()
            svc = _make_service()
            await svc._get_client()
            await svc._get_client()
            assert MockClient.call_count == 1


# ──────────────────────────────────────────────
# _parse_transfer_logs
# ──────────────────────────────────────────────
class TestParseTransferLogs:

    TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

    def test_valid_mnee_transfer(self):
        svc = _make_service()
        from_addr = "0x" + "a" * 40
        to_addr = "0x" + "b" * 40
        logs = [{
            "address": MNEE_CONTRACT_ADDRESS.lower(),
            "topics": [
                self.TRANSFER_TOPIC,
                "0x" + "0" * 24 + "a" * 40,
                "0x" + "0" * 24 + "b" * 40,
            ],
            "data": hex(2900000),
        }]
        result = svc._parse_transfer_logs(logs)
        assert result is not None
        assert result["from"] == from_addr
        assert result["to"] == to_addr
        assert result["amount_raw"] == 2900000

    def test_wrong_contract(self):
        svc = _make_service()
        logs = [{
            "address": "0x0000000000000000000000000000000000000000",
            "topics": [self.TRANSFER_TOPIC, "0x" + "0" * 64, "0x" + "0" * 64],
            "data": "0x100",
        }]
        assert svc._parse_transfer_logs(logs) is None

    def test_wrong_topic(self):
        svc = _make_service()
        logs = [{
            "address": MNEE_CONTRACT_ADDRESS.lower(),
            "topics": ["0xdeadbeef", "0x" + "0" * 64, "0x" + "0" * 64],
            "data": "0x100",
        }]
        assert svc._parse_transfer_logs(logs) is None

    def test_too_few_topics(self):
        svc = _make_service()
        logs = [{
            "address": MNEE_CONTRACT_ADDRESS.lower(),
            "topics": [self.TRANSFER_TOPIC],
            "data": "0x100",
        }]
        assert svc._parse_transfer_logs(logs) is None

    def test_empty_logs(self):
        svc = _make_service()
        assert svc._parse_transfer_logs([]) is None

    def test_multiple_logs_finds_mnee(self):
        svc = _make_service()
        logs = [
            {  # Not MNEE
                "address": "0x0000000000000000000000000000000000000000",
                "topics": [self.TRANSFER_TOPIC, "0x" + "0" * 64, "0x" + "0" * 64],
                "data": "0x100",
            },
            {  # MNEE
                "address": MNEE_CONTRACT_ADDRESS.lower(),
                "topics": [
                    self.TRANSFER_TOPIC,
                    "0x" + "0" * 24 + "c" * 40,
                    "0x" + "0" * 24 + "d" * 40,
                ],
                "data": hex(5000000),
            },
        ]
        result = svc._parse_transfer_logs(logs)
        assert result is not None
        assert result["amount_raw"] == 5000000


# ──────────────────────────────────────────────
# verify_transaction
# ──────────────────────────────────────────────
class TestVerifyTransaction:

    @pytest.mark.asyncio
    async def test_not_verified_passes_through(self):
        svc = _make_service()
        failed_result = MagicMock(verified=False)
        svc.get_transaction_status = AsyncMock(return_value=failed_result)

        result = await svc.verify_transaction("0xabc", 2900000, "0xrecip")
        assert result is failed_result

    @pytest.mark.asyncio
    async def test_recipient_mismatch(self):
        svc = _make_service()
        tx_result = MagicMock(
            verified=True, to_address="0xwrong", from_address="0xsender",
            amount_raw=2900000,
        )
        svc.get_transaction_status = AsyncMock(return_value=tx_result)
        svc._create_verification_result = MagicMock(
            return_value=MagicMock(verified=False)
        )

        result = await svc.verify_transaction("0xabc", 2900000, "0xexpected")
        assert result.verified is False

    @pytest.mark.asyncio
    async def test_amount_mismatch(self):
        svc = _make_service()
        tx_result = MagicMock(
            verified=True, to_address="0xrecip", from_address="0xsender",
            amount_raw=1000000,  # Way off from 2900000
        )
        svc.get_transaction_status = AsyncMock(return_value=tx_result)
        svc._create_verification_result = MagicMock(
            return_value=MagicMock(verified=False)
        )

        result = await svc.verify_transaction("0xabc", 2900000, "0xrecip")
        assert result.verified is False

    @pytest.mark.asyncio
    async def test_amount_within_tolerance(self):
        svc = _make_service()
        expected = 2900000
        actual = 2900000 + 100  # within 1%
        tx_result = MagicMock(
            verified=True, to_address="0xrecip", from_address="0xsender",
            amount_raw=actual, amount="29.00", confirmations=10,
            block_height=100, timestamp=None,
        )
        svc.get_transaction_status = AsyncMock(return_value=tx_result)
        svc._create_verification_result = MagicMock(
            return_value=MagicMock(verified=True)
        )

        result = await svc.verify_transaction("0xabc", expected, "0xrecip")
        assert result.verified is True

    @pytest.mark.asyncio
    async def test_exception_returns_unverified(self):
        svc = _make_service()
        svc.get_transaction_status = AsyncMock(side_effect=Exception("network"))
        svc._create_verification_result = MagicMock(
            return_value=MagicMock(verified=False)
        )

        result = await svc.verify_transaction("0xabc", 100, "0xrecip")
        assert result.verified is False


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
        await svc.close()  # No error



        