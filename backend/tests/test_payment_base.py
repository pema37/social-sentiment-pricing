"""
Tests for services/payment/base.py

PaymentVerificationService — ABC for blockchain payment verification.
PaymentServiceFactory — registry/factory for network services.
"""

import sys
from abc import ABCMeta
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED = ["schemas.payment"]
_originals = {m: sys.modules.get(m) for m in _MOCKED}


class _FakeTransactionVerification:
    """Mimics schemas.payment.TransactionVerification."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


_schema_mod = MagicMock()
_schema_mod.TransactionVerification = _FakeTransactionVerification
sys.modules["schemas.payment"] = _schema_mod

from services.payment.base import PaymentVerificationService, PaymentServiceFactory

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m


# ── Concrete stub for testing ────────────────────────────────────

class _StubPaymentService(PaymentVerificationService):
    """Minimal concrete implementation for testing."""

    def __init__(self, name="test_net", available=True):
        self._name = name
        self._available = available

    @property
    def network_name(self) -> str:
        return self._name

    @property
    def is_available(self) -> bool:
        return self._available

    async def verify_transaction(self, transaction_hash, expected_amount,
                                  expected_recipient, expected_memo=None):
        return self._create_verification_result(
            verified=True, transaction_hash=transaction_hash,
        )

    async def get_transaction_status(self, transaction_hash):
        return self._create_verification_result(
            verified=False, transaction_hash=transaction_hash,
        )


# ──────────────────────────────────────────────
# PaymentVerificationService — ABC enforcement
# ──────────────────────────────────────────────
class TestABCEnforcement:

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            PaymentVerificationService()

    def test_must_implement_network_name(self):
        class Bad(PaymentVerificationService):
            @property
            def is_available(self): return True
            async def verify_transaction(self, *a, **kw): pass
            async def get_transaction_status(self, *a, **kw): pass

        with pytest.raises(TypeError):
            Bad()

    def test_must_implement_is_available(self):
        class Bad(PaymentVerificationService):
            @property
            def network_name(self): return "x"
            async def verify_transaction(self, *a, **kw): pass
            async def get_transaction_status(self, *a, **kw): pass

        with pytest.raises(TypeError):
            Bad()

    def test_must_implement_verify_transaction(self):
        class Bad(PaymentVerificationService):
            @property
            def network_name(self): return "x"
            @property
            def is_available(self): return True
            async def get_transaction_status(self, *a, **kw): pass

        with pytest.raises(TypeError):
            Bad()

    def test_must_implement_get_transaction_status(self):
        class Bad(PaymentVerificationService):
            @property
            def network_name(self): return "x"
            @property
            def is_available(self): return True
            async def verify_transaction(self, *a, **kw): pass

        with pytest.raises(TypeError):
            Bad()

    def test_concrete_stub_instantiates(self):
        svc = _StubPaymentService()
        assert svc is not None

    def test_is_abstract(self):
        assert isinstance(PaymentVerificationService, ABCMeta)


# ──────────────────────────────────────────────
# Concrete properties
# ──────────────────────────────────────────────
class TestConcreteProperties:

    def test_network_name(self):
        svc = _StubPaymentService(name="bsv")
        assert svc.network_name == "bsv"

    def test_is_available_true(self):
        svc = _StubPaymentService(available=True)
        assert svc.is_available is True

    def test_is_available_false(self):
        svc = _StubPaymentService(available=False)
        assert svc.is_available is False


# ──────────────────────────────────────────────
# _create_verification_result
# ──────────────────────────────────────────────
class TestCreateVerificationResult:

    def test_returns_transaction_verification(self):
        svc = _StubPaymentService(name="ethereum")
        result = svc._create_verification_result(
            verified=True, transaction_hash="0xabc",
        )
        assert isinstance(result, _FakeTransactionVerification)

    def test_sets_verified(self):
        svc = _StubPaymentService()
        result = svc._create_verification_result(
            verified=True, transaction_hash="tx1",
        )
        assert result.verified is True

    def test_sets_verified_false(self):
        svc = _StubPaymentService()
        result = svc._create_verification_result(
            verified=False, transaction_hash="tx1",
        )
        assert result.verified is False

    def test_sets_transaction_hash(self):
        svc = _StubPaymentService()
        result = svc._create_verification_result(
            verified=True, transaction_hash="0xdeadbeef",
        )
        assert result.transaction_hash == "0xdeadbeef"

    def test_sets_network_from_property(self):
        svc = _StubPaymentService(name="bsv")
        result = svc._create_verification_result(
            verified=True, transaction_hash="tx1",
        )
        assert result.network == "bsv"

    def test_sets_error(self):
        svc = _StubPaymentService()
        result = svc._create_verification_result(
            verified=False, transaction_hash="tx1", error="not found",
        )
        assert result.error == "not found"

    def test_error_none_by_default(self):
        svc = _StubPaymentService()
        result = svc._create_verification_result(
            verified=True, transaction_hash="tx1",
        )
        assert result.error is None

    def test_passes_kwargs(self):
        svc = _StubPaymentService()
        result = svc._create_verification_result(
            verified=True, transaction_hash="tx1",
            amount=1000, confirmations=6,
        )
        assert result.amount == 1000
        assert result.confirmations == 6


# ──────────────────────────────────────────────
# verify_transaction / get_transaction_status via stub
# ──────────────────────────────────────────────
class TestStubMethods:

    @pytest.mark.asyncio
    async def test_verify_transaction(self):
        svc = _StubPaymentService(name="bsv")
        result = await svc.verify_transaction("tx1", 1000, "addr1")
        assert result.verified is True
        assert result.transaction_hash == "tx1"

    @pytest.mark.asyncio
    async def test_get_transaction_status(self):
        svc = _StubPaymentService(name="eth")
        result = await svc.get_transaction_status("tx2")
        assert result.verified is False
        assert result.transaction_hash == "tx2"


# ──────────────────────────────────────────────
# PaymentServiceFactory
# ──────────────────────────────────────────────
class TestPaymentServiceFactory:

    def setup_method(self):
        """Clear registry before each test."""
        PaymentServiceFactory._services = {}

    def test_register_and_get(self):
        svc = _StubPaymentService(name="bsv")
        PaymentServiceFactory.register("bsv", svc)
        assert PaymentServiceFactory.get_service("bsv") is svc

    def test_get_unknown_returns_none(self):
        assert PaymentServiceFactory.get_service("unknown") is None

    def test_case_insensitive_register(self):
        svc = _StubPaymentService(name="eth")
        PaymentServiceFactory.register("Ethereum", svc)
        assert PaymentServiceFactory.get_service("ethereum") is svc

    def test_case_insensitive_get(self):
        svc = _StubPaymentService(name="bsv")
        PaymentServiceFactory.register("bsv", svc)
        assert PaymentServiceFactory.get_service("BSV") is svc

    def test_get_available_networks(self):
        PaymentServiceFactory.register("bsv", _StubPaymentService(available=True))
        PaymentServiceFactory.register("eth", _StubPaymentService(available=False))
        available = PaymentServiceFactory.get_available_networks()
        assert "bsv" in available
        assert "eth" not in available

    def test_get_available_networks_empty(self):
        assert PaymentServiceFactory.get_available_networks() == []

    def test_is_network_supported_true(self):
        PaymentServiceFactory.register("bsv", _StubPaymentService(available=True))
        assert PaymentServiceFactory.is_network_supported("bsv") is True

    def test_is_network_supported_false_unavailable(self):
        PaymentServiceFactory.register("bsv", _StubPaymentService(available=False))
        assert PaymentServiceFactory.is_network_supported("bsv") is False

    def test_is_network_supported_false_unknown(self):
        assert PaymentServiceFactory.is_network_supported("unknown") is False

    def test_overwrite_registration(self):
        svc1 = _StubPaymentService(name="v1")
        svc2 = _StubPaymentService(name="v2")
        PaymentServiceFactory.register("bsv", svc1)
        PaymentServiceFactory.register("bsv", svc2)
        assert PaymentServiceFactory.get_service("bsv") is svc2

    def test_multiple_networks(self):
        bsv = _StubPaymentService(name="bsv")
        eth = _StubPaymentService(name="eth")
        PaymentServiceFactory.register("bsv", bsv)
        PaymentServiceFactory.register("ethereum", eth)
        assert PaymentServiceFactory.get_service("bsv") is bsv
        assert PaymentServiceFactory.get_service("ethereum") is eth

        