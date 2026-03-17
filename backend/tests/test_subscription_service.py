"""
Tests for services/payment/subscription_service.py

SubscriptionService — plans, subscription queries, payment creation,
blockchain verification, subscription activation.
"""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ── Import isolation ──────────────────────────────────────────────
_MOCKED = [
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlmodel",
    "models.user",
    "models.subscription",
    "models.payment",
    "services.payment.base",
    "schemas.payment",
]

_originals = {m: sys.modules.get(m) for m in _MOCKED}
for _m in _MOCKED:
    sys.modules[_m] = MagicMock()

# Force fresh import of service under test
sys.modules.pop("services.payment.subscription_service", None)


# PlanInfo — simple stand-in
class _FakePlanInfo:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeSubscriptionInfo:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakePaymentRequest:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakePaymentInfo:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeConfirmResponse:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeVerification:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


_schema_mod = sys.modules["schemas.payment"]
_schema_mod.PlanInfo = _FakePlanInfo
_schema_mod.SubscriptionInfo = _FakeSubscriptionInfo
_schema_mod.PaymentRequest = _FakePaymentRequest
_schema_mod.PaymentInfo = _FakePaymentInfo
_schema_mod.ConfirmPaymentResponse = _FakeConfirmResponse
_schema_mod.TransactionVerification = _FakeVerification

# models.subscription
_sub_mod = sys.modules["models.subscription"]
_sub_mod.Subscription = MagicMock
_sub_mod.TIER_LIMITS_STR = {
    "free": {"products": 5},
    "starter": {"products": 50},
    "professional": {"products": 500},
    "enterprise": {"products": -1},
}

# models.payment
_pay_mod = sys.modules["models.payment"]
_pay_mod.Payment = MagicMock

# services.payment.base
_base_mod = sys.modules["services.payment.base"]
_base_mod.PaymentServiceFactory = MagicMock()

from services.payment.subscription_service import (
    PLANS,
    VALID_TIERS,
    SubscriptionService,
)

# Restore
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m

SVC_MOD = "services.payment.subscription_service"


# ── Helpers ───────────────────────────────────────────────────────


def _make_service():
    session = AsyncMock()
    svc = SubscriptionService(session=session)
    return svc


def _make_user(user_id=None):
    user = MagicMock()
    user.id = user_id or uuid4()
    user.email = "test@example.com"
    return user


# ──────────────────────────────────────────────
# PLANS / VALID_TIERS
# ──────────────────────────────────────────────
class TestPlanConstants:
    def test_four_plans(self):
        assert len(PLANS) == 4

    def test_plan_tiers(self):
        tiers = [p.tier for p in PLANS]
        assert tiers == ["free", "starter", "professional", "enterprise"]

    def test_free_plan_zero_price(self):
        free = PLANS[0]
        assert free.price_monthly == 0
        assert free.price_yearly == 0

    def test_enterprise_unlimited(self):
        ent = PLANS[3]
        assert ent.product_limit == -1

    def test_valid_tiers(self):
        assert VALID_TIERS == ["free", "starter", "professional", "enterprise"]

    def test_each_plan_has_features(self):
        for plan in PLANS:
            assert isinstance(plan.features, list)
            assert len(plan.features) > 0


# ──────────────────────────────────────────────
# __init__
# ──────────────────────────────────────────────
class TestInit:
    def test_stores_session(self):
        svc = _make_service()
        assert svc.session is not None

    def test_recipient_address(self):
        svc = _make_service()
        assert svc.recipient_address is not None


# ──────────────────────────────────────────────
# get_all_plans / get_plan / get_product_limit
# ──────────────────────────────────────────────
class TestPlanQueries:
    def test_get_all_plans(self):
        svc = _make_service()
        plans = svc.get_all_plans()
        assert len(plans) == 4

    def test_get_plan_exists(self):
        svc = _make_service()
        plan = svc.get_plan("starter")
        assert plan is not None
        assert plan.tier == "starter"

    def test_get_plan_not_found(self):
        svc = _make_service()
        assert svc.get_plan("nonexistent") is None

    def test_get_product_limit_free(self):
        svc = _make_service()
        assert svc.get_product_limit("free") == 5

    def test_get_product_limit_starter(self):
        svc = _make_service()
        assert svc.get_product_limit("starter") == 50

    def test_get_product_limit_professional(self):
        svc = _make_service()
        assert svc.get_product_limit("professional") == 500

    def test_get_product_limit_enterprise(self):
        svc = _make_service()
        assert svc.get_product_limit("enterprise") == -1

    def test_get_product_limit_unknown_defaults_free(self):
        svc = _make_service()
        assert svc.get_product_limit("unknown") == 5


# ──────────────────────────────────────────────
# _get_recipient_for_network
# ──────────────────────────────────────────────
class TestGetRecipientForNetwork:
    def test_bsv_returns_bsv_address(self):
        svc = _make_service()
        svc.recipient_address = "$pema12@handcash.io"
        result = svc._get_recipient_for_network("bsv")
        assert result == "$pema12@handcash.io"

    def test_ethereum_returns_eth_address(self):
        svc = _make_service()
        svc.eth_recipient = "0xdeadbeef"
        result = svc._get_recipient_for_network("ethereum")
        assert result == "0xdeadbeef"

    def test_ethereum_no_address_raises(self):
        svc = _make_service()
        svc.eth_recipient = ""
        with pytest.raises(ValueError, match="Ethereum"):
            svc._get_recipient_for_network("ethereum")


# ──────────────────────────────────────────────
# create_subscription_payment
# ──────────────────────────────────────────────
class TestCreateSubscriptionPayment:
    @pytest.mark.asyncio
    async def test_invalid_tier_raises(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Invalid tier"):
            await svc.create_subscription_payment(_make_user(), "invalid_tier")

    @pytest.mark.asyncio
    async def test_free_tier_raises(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Free tier"):
            await svc.create_subscription_payment(_make_user(), "free")

    @pytest.mark.asyncio
    async def test_invalid_network_raises(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Invalid network"):
            await svc.create_subscription_payment(_make_user(), "starter", network="bitcoin")

    @pytest.mark.asyncio
    async def test_returns_tuple(self):
        svc = _make_service()
        svc.eth_recipient = "0xaddr"

        with patch(f"{SVC_MOD}.Payment") as MockPayment:
            mock_payment = MagicMock()
            mock_payment.id = uuid4()
            MockPayment.return_value = mock_payment

            with patch(f"{SVC_MOD}.PaymentRequest") as MockReq:
                MockReq.return_value = MagicMock()
                result = await svc.create_subscription_payment(_make_user(), "starter", network="ethereum")

        assert isinstance(result, tuple)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_yearly_uses_yearly_price(self):
        svc = _make_service()
        svc.recipient_address = "addr"

        with patch(f"{SVC_MOD}.Payment") as MockPayment:
            mock_payment = MagicMock()
            mock_payment.id = uuid4()
            MockPayment.return_value = mock_payment

            with patch(f"{SVC_MOD}.PaymentRequest") as MockReq:
                MockReq.return_value = MagicMock()
                _, payment = await svc.create_subscription_payment(_make_user(), "starter", billing_cycle="yearly")

        # starter yearly = 290 (stored as float by Pydantic)
        pay_call = MockPayment.call_args[1]
        assert float(pay_call["amount"]) == 290.0

    @pytest.mark.asyncio
    async def test_monthly_uses_monthly_price(self):
        svc = _make_service()
        svc.recipient_address = "addr"

        with patch(f"{SVC_MOD}.Payment") as MockPayment:
            mock_payment = MagicMock()
            mock_payment.id = uuid4()
            MockPayment.return_value = mock_payment

            with patch(f"{SVC_MOD}.PaymentRequest") as MockReq:
                MockReq.return_value = MagicMock()
                await svc.create_subscription_payment(_make_user(), "starter", billing_cycle="monthly")

        # starter monthly = 29 (stored as float by Pydantic)
        pay_call = MockPayment.call_args[1]
        assert float(pay_call["amount"]) == 29.0


# ──────────────────────────────────────────────
# confirm_payment
# ──────────────────────────────────────────────
class TestConfirmPayment:
    @pytest.mark.asyncio
    async def test_payment_not_found(self):
        svc = _make_service()
        svc._get_user_payment = AsyncMock(return_value=None)

        result = await svc.confirm_payment(uuid4(), _make_user(), "0xhash")
        assert result.success is False
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_already_confirmed(self):
        svc = _make_service()
        payment = MagicMock(status="confirmed", id=uuid4())
        svc._get_user_payment = AsyncMock(return_value=payment)

        result = await svc.confirm_payment(uuid4(), _make_user(), "0xhash")
        assert result.success is False
        assert "already confirmed" in result.message.lower()

    @pytest.mark.asyncio
    async def test_invalid_status(self):
        svc = _make_service()
        payment = MagicMock(status="cancelled", id=uuid4())
        svc._get_user_payment = AsyncMock(return_value=payment)

        result = await svc.confirm_payment(uuid4(), _make_user(), "0xhash")
        assert result.success is False


# ──────────────────────────────────────────────
# _get_payment_metadata
# ──────────────────────────────────────────────
class TestGetPaymentMetadata:
    def test_from_get_metadata(self):
        svc = _make_service()
        payment = MagicMock()
        payment.get_metadata.return_value = {"tier": "starter"}
        result = svc._get_payment_metadata(payment)
        assert result["tier"] == "starter"

    def test_from_metadata_json(self):
        svc = _make_service()
        payment = MagicMock(spec=["metadata_json"])
        payment.metadata_json = json.dumps({"tier": "professional"})
        result = svc._get_payment_metadata(payment)
        assert result["tier"] == "professional"

    def test_invalid_json_returns_empty(self):
        svc = _make_service()
        payment = MagicMock(spec=["metadata_json"])
        payment.metadata_json = "not-json"
        result = svc._get_payment_metadata(payment)
        assert result == {}

    def test_no_metadata_returns_empty(self):
        svc = _make_service()
        payment = MagicMock(spec=["metadata_json"])
        payment.metadata_json = None
        result = svc._get_payment_metadata(payment)
        assert result == {}

    def test_get_metadata_returns_none_falls_to_json(self):
        svc = _make_service()
        payment = MagicMock()
        payment.get_metadata.return_value = None
        payment.metadata_json = json.dumps({"billing_cycle": "yearly"})
        result = svc._get_payment_metadata(payment)
        assert result["billing_cycle"] == "yearly"
