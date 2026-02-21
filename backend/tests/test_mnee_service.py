"""
Tests for services/payment/mnee_service.py

MneeService — high-level MNEE payment service.
Address validation, balance, transactions, amount utilities, factory.
"""

import sys
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED = [
    "services.payment.mnee_client",
    "services.payment.exceptions",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}


# exceptions
class MneeValidationError(Exception):
    def __init__(self, message="", field=None):
        super().__init__(message)
        self.field = field

class MneeConfigError(Exception):
    def __init__(self, message="", missing_key=None):
        super().__init__(message)
        self.missing_key = missing_key

_exc_mod = MagicMock()
_exc_mod.MneeValidationError = MneeValidationError
_exc_mod.MneeConfigError = MneeConfigError
sys.modules["services.payment.exceptions"] = _exc_mod

# mnee_client
_client_mod = MagicMock()

class FakeMneeEnvironment:
    SANDBOX = MagicMock()
    SANDBOX.value = "sandbox"
    PRODUCTION = MagicMock()
    PRODUCTION.value = "production"

_client_mod.MneeEnvironment = FakeMneeEnvironment
_client_mod.MneeClient = MagicMock
sys.modules["services.payment.mnee_client"] = _client_mod

from services.payment.mnee_service import (
    MneeService,
    get_mnee_service,
    close_mnee_service,
)

# Force-patch exception classes into loaded module so raise works
import services.payment.mnee_service as _svc_mod
_svc_mod.MneeValidationError = MneeValidationError
_svc_mod.MneeConfigError = MneeConfigError

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

SVC_MOD = "services.payment.mnee_service"


# ── Helpers ───────────────────────────────────────────────────────

def _make_service():
    client = MagicMock()
    client.environment = MagicMock()
    client.environment.value = "sandbox"
    client.close = AsyncMock()
    client.get_config = AsyncMock(return_value={"decimals": 5, "fees": [{"fee": 1000}]})
    client.get_balances = AsyncMock(return_value=[
        {"address": "1ValidAddr", "amt": 3422000, "precised": 34.22}
    ])
    client.get_transaction = AsyncMock(return_value={"txid": "abc"})
    client.get_transactions = AsyncMock(return_value=[])
    client.get_ticket = AsyncMock(return_value={
        "id": "t1", "status": "confirmed", "tx_id": "abc",
        "errors": None, "createdAt": "2025-01-01", "updatedAt": "2025-01-02",
    })
    svc = MneeService(client=client)
    return svc


# Valid BSV address (starts with 1, 25-34 chars, base58)
VALID_ADDR = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
SHORT_ADDR = "1A1zP1eP5QGefi2DMPTL"  # too short


# ──────────────────────────────────────────────
# __init__ and properties
# ──────────────────────────────────────────────
class TestInit:

    def test_stores_client(self):
        client = MagicMock()
        svc = MneeService(client=client)
        assert svc._client is client

    def test_config_initially_none(self):
        svc = _make_service()
        assert svc._config is None

    def test_decimals_constant(self):
        assert MneeService.DECIMALS == 5

    def test_environment_property(self):
        svc = _make_service()
        assert svc.environment == "sandbox"


# ──────────────────────────────────────────────
# close
# ──────────────────────────────────────────────
class TestClose:

    @pytest.mark.asyncio
    async def test_closes_client(self):
        svc = _make_service()
        await svc.close()
        svc._client.close.assert_called_once()


# ──────────────────────────────────────────────
# get_config / get_fee_structure
# ──────────────────────────────────────────────
class TestConfig:

    @pytest.mark.asyncio
    async def test_get_config(self):
        svc = _make_service()
        config = await svc.get_config()
        assert config["decimals"] == 5

    @pytest.mark.asyncio
    async def test_get_config_caches(self):
        svc = _make_service()
        await svc.get_config()
        await svc.get_config()
        assert svc._client.get_config.call_count == 1

    @pytest.mark.asyncio
    async def test_get_fee_structure(self):
        svc = _make_service()
        fees = await svc.get_fee_structure()
        assert isinstance(fees, list)
        assert fees[0]["fee"] == 1000


# ──────────────────────────────────────────────
# validate_bsv_address (static)
# ──────────────────────────────────────────────
class TestValidateBsvAddress:

    def test_valid_p2pkh(self):
        assert MneeService.validate_bsv_address(VALID_ADDR) is True

    def test_valid_p2sh(self):
        addr = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        assert MneeService.validate_bsv_address(addr) is True

    def test_empty_string(self):
        assert MneeService.validate_bsv_address("") is False

    def test_none(self):
        assert MneeService.validate_bsv_address(None) is False

    def test_not_string(self):
        assert MneeService.validate_bsv_address(12345) is False

    def test_ethereum_address_rejected(self):
        assert MneeService.validate_bsv_address("0xdead1234567890abcdef1234567890abcdef1234") is False

    def test_wrong_prefix(self):
        assert MneeService.validate_bsv_address("5ValidButWrongPrefix12345678") is False

    def test_too_short(self):
        assert MneeService.validate_bsv_address("1short") is False

    def test_too_long(self):
        assert MneeService.validate_bsv_address("1" + "A" * 34) is False

    def test_invalid_base58_chars(self):
        # 'O', 'I', 'l', '0' are not in base58
        addr = "1A1zP1eP5QGefi2DMPTfTL5SLmv7OivfNa"  # 'O' instead of 'D'
        # O is invalid in base58
        assert MneeService.validate_bsv_address(addr) is False

    def test_exactly_25_chars(self):
        addr = "1" + "A" * 24
        assert MneeService.validate_bsv_address(addr) is True

    def test_exactly_34_chars(self):
        addr = "1" + "A" * 33
        assert MneeService.validate_bsv_address(addr) is True

    def test_24_chars_too_short(self):
        addr = "1" + "A" * 23
        assert MneeService.validate_bsv_address(addr) is False


# ──────────────────────────────────────────────
# require_valid_address
# ──────────────────────────────────────────────
class TestRequireValidAddress:

    def test_valid_returns_stripped(self):
        svc = _make_service()
        result = svc.require_valid_address(f"  {VALID_ADDR}  ")
        assert result == VALID_ADDR

    def test_empty_raises(self):
        svc = _make_service()
        with pytest.raises(MneeValidationError):
            svc.require_valid_address("")

    def test_none_raises(self):
        svc = _make_service()
        with pytest.raises(MneeValidationError):
            svc.require_valid_address(None)

    def test_ethereum_raises_specific_message(self):
        svc = _make_service()
        with pytest.raises(MneeValidationError, match="Ethereum"):
            svc.require_valid_address("0xdead1234567890abcdef1234567890abcdef1234")

    def test_invalid_bsv_raises(self):
        svc = _make_service()
        with pytest.raises(MneeValidationError, match="Invalid BSV"):
            svc.require_valid_address("invalid")

    def test_custom_field_name(self):
        svc = _make_service()
        with pytest.raises(MneeValidationError) as exc_info:
            svc.require_valid_address("", field_name="wallet")
        assert exc_info.value.field == "wallet"


# ──────────────────────────────────────────────
# Balance operations
# ──────────────────────────────────────────────
class TestBalance:

    @pytest.mark.asyncio
    async def test_get_balance(self):
        svc = _make_service()
        result = await svc.get_balance(VALID_ADDR)
        assert result["address"] == VALID_ADDR
        assert result["balance"] == "34.22"
        assert result["balance_raw"] == 3422000

    @pytest.mark.asyncio
    async def test_get_balance_empty(self):
        svc = _make_service()
        svc._client.get_balances.return_value = []
        result = await svc.get_balance(VALID_ADDR)
        assert result["balance"] == "0.00"
        assert result["balance_raw"] == 0

    @pytest.mark.asyncio
    async def test_get_balances_multiple(self):
        addr2 = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
        svc = _make_service()
        svc._client.get_balances.return_value = [
            {"address": VALID_ADDR, "amt": 100, "precised": 0.001},
            {"address": addr2, "amt": 200, "precised": 0.002},
        ]
        result = await svc.get_balances([VALID_ADDR, addr2])
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_balance_validates_address(self):
        svc = _make_service()
        with pytest.raises(MneeValidationError):
            await svc.get_balance("invalid")


# ──────────────────────────────────────────────
# Transaction operations
# ──────────────────────────────────────────────
class TestTransactions:

    @pytest.mark.asyncio
    async def test_get_transaction(self):
        svc = _make_service()
        result = await svc.get_transaction("txid-123")
        svc._client.get_transaction.assert_called_once_with("txid-123")

    @pytest.mark.asyncio
    async def test_get_transaction_empty_raises(self):
        svc = _make_service()
        with pytest.raises(MneeValidationError):
            await svc.get_transaction("")

    @pytest.mark.asyncio
    async def test_get_transaction_history(self):
        svc = _make_service()
        await svc.get_transaction_history(VALID_ADDR, limit=20)
        svc._client.get_transactions.assert_called_once_with([VALID_ADDR], limit=20)

    @pytest.mark.asyncio
    async def test_check_transfer_status(self):
        svc = _make_service()
        result = await svc.check_transfer_status("ticket-1")
        assert result["id"] == "t1"
        assert result["status"] == "confirmed"
        assert result["txid"] == "abc"

    @pytest.mark.asyncio
    async def test_check_transfer_status_empty_raises(self):
        svc = _make_service()
        with pytest.raises(MneeValidationError):
            await svc.check_transfer_status("")


# ──────────────────────────────────────────────
# Amount utilities
# ──────────────────────────────────────────────
class TestAmountUtilities:

    def test_format_amount_normal(self):
        assert MneeService.format_amount(3422000) == "34.22"

    def test_format_amount_zero(self):
        assert MneeService.format_amount(0) == "0.00"

    def test_format_amount_small(self):
        assert MneeService.format_amount(100) == "0.00"

    def test_format_amount_large(self):
        assert MneeService.format_amount(10000000) == "100.00"

    def test_to_raw_amount(self):
        assert MneeService.to_raw_amount("34.22") == 3422000

    def test_to_raw_amount_integer(self):
        assert MneeService.to_raw_amount("100") == 10000000

    def test_to_raw_amount_zero(self):
        assert MneeService.to_raw_amount("0") == 0

    def test_validate_amount_valid(self):
        result = MneeService.validate_amount("34.22")
        assert result == Decimal("34.22")

    def test_validate_amount_zero_raises(self):
        with pytest.raises(MneeValidationError):
            MneeService.validate_amount("0")

    def test_validate_amount_negative_raises(self):
        with pytest.raises(MneeValidationError):
            MneeService.validate_amount("-5")

    def test_validate_amount_invalid_string_raises(self):
        with pytest.raises(MneeValidationError):
            MneeService.validate_amount("not-a-number")


# ──────────────────────────────────────────────
# get_mnee_service / close_mnee_service
# ──────────────────────────────────────────────
class TestFactory:

    def setup_method(self):
        import services.payment.mnee_service as mod
        mod._service_instance = None

    def test_get_mnee_service_no_api_key_raises(self):
        with patch(f"{SVC_MOD}.MneeClient") as MockClient:
            # No settings module, no api_key arg
            with patch.dict("sys.modules", {"core.config": None}):
                with pytest.raises(MneeConfigError):
                    get_mnee_service()

    def test_get_mnee_service_with_key(self):
        with patch(f"{SVC_MOD}.MneeClient") as MockClient:
            mock_client = MagicMock()
            MockClient.return_value = mock_client
            with patch.dict("sys.modules", {"core.config": None}):
                svc = get_mnee_service(api_key="test-key", environment="sandbox")
            assert isinstance(svc, MneeService)
            MockClient.assert_called_once_with(api_key="test-key", environment="sandbox")

    def test_get_mnee_service_singleton(self):
        with patch(f"{SVC_MOD}.MneeClient") as MockClient:
            MockClient.return_value = MagicMock()
            with patch.dict("sys.modules", {"core.config": None}):
                s1 = get_mnee_service(api_key="key")
                s2 = get_mnee_service(api_key="key")
            assert s1 is s2

    @pytest.mark.asyncio
    async def test_close_mnee_service(self):
        import services.payment.mnee_service as mod
        mock_svc = MagicMock()
        mock_svc.close = AsyncMock()
        mod._service_instance = mock_svc
        await close_mnee_service()
        mock_svc.close.assert_called_once()
        assert mod._service_instance is None

    @pytest.mark.asyncio
    async def test_close_mnee_service_noop(self):
        import services.payment.mnee_service as mod
        mod._service_instance = None
        await close_mnee_service()  # No error



        