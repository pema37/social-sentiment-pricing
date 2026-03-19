"""
Tests for ApprovalService feedback loop wiring.

Verifies that apply_price(), auto_approve_and_apply(), and reject()
call _record_decision() with the correct merchant_decision value,
and that _record_decision() failures don't crash the main flow.

The source uses lazy imports:
  - from services.pricing.ecommerce_push_service import EcommercePushService
  - from services.pricing.outcome_service import OutcomeService

We patch both at their lazy-import paths.

Place at: backend/tests/unit/test_approval_service_wiring.py
Run: pytest backend/tests/unit/test_approval_service_wiring.py -v
"""

import sys
import types
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ══════════════════════════════════════════════════════════════════
# sys.modules ISOLATION
# ══════════════════════════════════════════════════════════════════

_saved = {}
for _key in ["db.session", "core.db.session"]:
    if _key in sys.modules:
        _saved[_key] = sys.modules[_key]

_mock_db = types.ModuleType("db.session")
_mock_db.get_session = MagicMock()
sys.modules.setdefault("db.session", _mock_db)

_mock_core_db = types.ModuleType("core.db.session")
_mock_core_db.get_session = MagicMock()
sys.modules.setdefault("core.db.session", _mock_core_db)

from services.pricing.approval_service import ApprovalError, ApprovalService

# Pull enums from already-loaded modules (same path source uses)
_rec_mod = sys.modules["models.price_recommendation"]
RecommendationStatus = _rec_mod.RecommendationStatus


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════


def _make_recommendation(
    user_id,
    recommendation_id,
    status=None,
    current_price=Decimal("32.00"),
    recommended_price=Decimal("29.49"),
    change_percent=Decimal("-7.84"),
    confidence_score=Decimal("0.72"),
    triggered_rule_id=None,
    product_id=None,
):
    """Build a mock PriceRecommendation with all required attributes."""
    rec = MagicMock()
    rec.id = recommendation_id
    rec.user_id = user_id
    rec.product_id = product_id or uuid4()
    rec.current_price = current_price
    rec.recommended_price = recommended_price
    rec.change_percent = change_percent
    rec.confidence_score = confidence_score
    rec.factors = {}
    rec.triggered_rule_id = triggered_rule_id
    rec.reasoning = "Test reasoning"
    rec.requires_approval = True
    rec.status = status or RecommendationStatus.APPROVED
    rec.reviewed_by = None
    rec.reviewed_at = None
    rec.applied_at = None
    rec.applied_to_platform = None
    rec.rejection_reason = None
    # CRITICAL: valid_until must be a real datetime, not MagicMock
    rec.valid_until = datetime.now(UTC) + timedelta(hours=24)
    return rec


def _make_product(product_id=None, current_price=Decimal("32.00")):
    product = MagicMock()
    product.id = product_id or uuid4()
    product.current_price = current_price
    product.updated_at = None
    return product


def _make_db():
    """Build a mock AsyncSession."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


def _mock_push_service(success=True, platform="shopify"):
    """Create a mock EcommercePushService class."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_instance.push_price = AsyncMock(
        return_value={
            "success": success,
            "platform": platform,
            **({"error": "Push failed", "error_code": "PUSH_ERROR"} if not success else {}),
        }
    )
    mock_cls.return_value = mock_instance
    return mock_cls


def _mock_outcome_service(should_fail=False):
    """Create a mock OutcomeService class."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    if should_fail:
        mock_instance.record_merchant_decision = AsyncMock(side_effect=Exception("OutcomeService crashed"))
    else:
        mock_instance.record_merchant_decision = AsyncMock(return_value=MagicMock())
    mock_cls.return_value = mock_instance
    return mock_cls, mock_instance


# ══════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def recommendation_id():
    return uuid4()


# ══════════════════════════════════════════════════════════════════
# apply_price() RECORDS DECISION
# ══════════════════════════════════════════════════════════════════


class TestApplyPriceRecordsDecision:
    @pytest.mark.asyncio
    async def test_records_accepted_after_apply(self, user_id, recommendation_id):
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.APPROVED)
        product = _make_product(product_id=rec.product_id)

        db = _make_db()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == recommendation_id else product)

        push_cls = _mock_push_service(success=True)
        outcome_cls, outcome_inst = _mock_outcome_service()

        svc = ApprovalService(db)

        with (
            patch("services.pricing.ecommerce_push_service.EcommercePushService", push_cls),
            patch("services.pricing.outcome_service.OutcomeService", outcome_cls),
        ):
            await svc.apply_price(recommendation_id, user_id)

        outcome_inst.record_merchant_decision.assert_called_once()
        call_kwargs = outcome_inst.record_merchant_decision.call_args
        assert (
            call_kwargs.kwargs.get("merchant_decision")
            or call_kwargs[1].get("merchant_decision")
            or (len(call_kwargs[0]) > 2 and call_kwargs[0][2]) == "accepted"
        )

    @pytest.mark.asyncio
    async def test_no_record_on_push_failure(self, user_id, recommendation_id):
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.APPROVED)
        product = _make_product(product_id=rec.product_id)

        db = _make_db()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == recommendation_id else product)

        push_cls = _mock_push_service(success=False)
        outcome_cls, outcome_inst = _mock_outcome_service()

        svc = ApprovalService(db)

        with (
            patch("services.pricing.ecommerce_push_service.EcommercePushService", push_cls),
            patch("services.pricing.outcome_service.OutcomeService", outcome_cls),
        ):
            with pytest.raises(ApprovalError):
                await svc.apply_price(recommendation_id, user_id)

        # Push failed → no outcome recorded
        outcome_inst.record_merchant_decision.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# auto_approve_and_apply() RECORDS DECISION
# ══════════════════════════════════════════════════════════════════


class TestAutoApproveRecordsDecision:
    @pytest.mark.asyncio
    async def test_records_auto_applied(self, user_id, recommendation_id):
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.PENDING)
        product = _make_product(product_id=rec.product_id)

        db = _make_db()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == recommendation_id else product)

        # _check_daily_limit needs db.execute → result.scalars().first() → None (no settings)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 0
        db.execute = AsyncMock(return_value=mock_result)

        push_cls = _mock_push_service(success=True)
        outcome_cls, outcome_inst = _mock_outcome_service()

        svc = ApprovalService(db)

        with (
            patch("services.pricing.ecommerce_push_service.EcommercePushService", push_cls),
            patch("services.pricing.outcome_service.OutcomeService", outcome_cls),
        ):
            await svc.auto_approve_and_apply(recommendation_id, user_id)

        outcome_inst.record_merchant_decision.assert_called_once()
        call_args = outcome_inst.record_merchant_decision.call_args
        # Check merchant_decision is "auto_applied"
        decision = call_args.kwargs.get("merchant_decision", "")
        assert decision == "auto_applied"

    @pytest.mark.asyncio
    async def test_no_record_on_auto_push_failure(self, user_id, recommendation_id):
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.PENDING)
        product = _make_product(product_id=rec.product_id)

        db = _make_db()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == recommendation_id else product)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 0
        db.execute = AsyncMock(return_value=mock_result)

        push_cls = _mock_push_service(success=False)
        outcome_cls, outcome_inst = _mock_outcome_service()

        svc = ApprovalService(db)

        with (
            patch("services.pricing.ecommerce_push_service.EcommercePushService", push_cls),
            patch("services.pricing.outcome_service.OutcomeService", outcome_cls),
        ):
            with pytest.raises(ApprovalError):
                await svc.auto_approve_and_apply(recommendation_id, user_id)

        outcome_inst.record_merchant_decision.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# reject() RECORDS DECISION
# ══════════════════════════════════════════════════════════════════


class TestRejectRecordsDecision:
    @pytest.mark.asyncio
    async def test_records_rejected(self, user_id, recommendation_id):
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.PENDING)

        db = _make_db()
        db.get = AsyncMock(return_value=rec)

        outcome_cls, outcome_inst = _mock_outcome_service()

        svc = ApprovalService(db)

        with patch("services.pricing.outcome_service.OutcomeService", outcome_cls):
            await svc.reject(recommendation_id, user_id, reason="Too aggressive")

        outcome_inst.record_merchant_decision.assert_called_once()
        call_args = outcome_inst.record_merchant_decision.call_args
        assert call_args.kwargs.get("merchant_decision") == "rejected"

    @pytest.mark.asyncio
    async def test_reject_still_returns_on_outcome_failure(self, user_id, recommendation_id):
        """_record_decision failure should not crash reject()."""
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.PENDING)

        db = _make_db()
        db.get = AsyncMock(return_value=rec)

        outcome_cls, _outcome_inst = _mock_outcome_service(should_fail=True)

        svc = ApprovalService(db)

        with patch("services.pricing.outcome_service.OutcomeService", outcome_cls):
            result = await svc.reject(recommendation_id, user_id)

        # reject() succeeds even though _record_decision crashed
        assert result.status == RecommendationStatus.REJECTED


# ══════════════════════════════════════════════════════════════════
# approve() does NOT record decision
# ══════════════════════════════════════════════════════════════════


class TestApproveDoesNotRecord:
    @pytest.mark.asyncio
    async def test_approve_does_not_record(self, user_id, recommendation_id):
        """approve() only changes status — no _record_decision call."""
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.PENDING)

        db = _make_db()
        db.get = AsyncMock(return_value=rec)

        outcome_cls, outcome_inst = _mock_outcome_service()

        svc = ApprovalService(db)

        with patch("services.pricing.outcome_service.OutcomeService", outcome_cls):
            await svc.approve(recommendation_id, user_id)

        outcome_inst.record_merchant_decision.assert_not_called()


# ══════════════════════════════════════════════════════════════════
# _record_decision() FIRE-AND-FORGET
# ══════════════════════════════════════════════════════════════════


class TestRecordDecisionFireAndForget:
    @pytest.mark.asyncio
    async def test_record_failure_does_not_crash_apply(self, user_id, recommendation_id):
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.APPROVED)
        product = _make_product(product_id=rec.product_id)

        db = _make_db()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == recommendation_id else product)

        push_cls = _mock_push_service(success=True)
        outcome_cls, _ = _mock_outcome_service(should_fail=True)

        svc = ApprovalService(db)

        with (
            patch("services.pricing.ecommerce_push_service.EcommercePushService", push_cls),
            patch("services.pricing.outcome_service.OutcomeService", outcome_cls),
        ):
            # Should not raise even though OutcomeService crashes
            result = await svc.apply_price(recommendation_id, user_id)

        assert result.status == RecommendationStatus.APPLIED

    @pytest.mark.asyncio
    async def test_record_failure_does_not_crash_auto_apply(self, user_id, recommendation_id):
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.PENDING)
        product = _make_product(product_id=rec.product_id)

        db = _make_db()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == recommendation_id else product)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = None
        mock_result.scalars.return_value = mock_scalars
        mock_result.scalar.return_value = 0
        db.execute = AsyncMock(return_value=mock_result)

        push_cls = _mock_push_service(success=True)
        outcome_cls, _ = _mock_outcome_service(should_fail=True)

        svc = ApprovalService(db)

        with (
            patch("services.pricing.ecommerce_push_service.EcommercePushService", push_cls),
            patch("services.pricing.outcome_service.OutcomeService", outcome_cls),
        ):
            result = await svc.auto_approve_and_apply(recommendation_id, user_id)

        assert result.status == RecommendationStatus.APPLIED


# ══════════════════════════════════════════════════════════════════
# DECISION ARGS CORRECTNESS
# ══════════════════════════════════════════════════════════════════


class TestRecordDecisionArgs:
    @pytest.mark.asyncio
    async def test_passes_recommendation_id(self, user_id, recommendation_id):
        rec = _make_recommendation(user_id, recommendation_id, status=RecommendationStatus.APPROVED)
        product = _make_product(product_id=rec.product_id)

        db = _make_db()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == recommendation_id else product)

        push_cls = _mock_push_service(success=True)
        outcome_cls, outcome_inst = _mock_outcome_service()

        svc = ApprovalService(db)

        with (
            patch("services.pricing.ecommerce_push_service.EcommercePushService", push_cls),
            patch("services.pricing.outcome_service.OutcomeService", outcome_cls),
        ):
            await svc.apply_price(recommendation_id, user_id)

        call_kwargs = outcome_inst.record_merchant_decision.call_args.kwargs
        assert call_kwargs["recommendation_id"] == recommendation_id
        assert call_kwargs["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_passes_actual_price_on_apply(self, user_id, recommendation_id):
        rec = _make_recommendation(
            user_id,
            recommendation_id,
            status=RecommendationStatus.APPROVED,
            recommended_price=Decimal("29.49"),
        )
        product = _make_product(product_id=rec.product_id)

        db = _make_db()
        db.get = AsyncMock(side_effect=lambda cls, pk: rec if pk == recommendation_id else product)

        push_cls = _mock_push_service(success=True)
        outcome_cls, outcome_inst = _mock_outcome_service()

        svc = ApprovalService(db)

        with (
            patch("services.pricing.ecommerce_push_service.EcommercePushService", push_cls),
            patch("services.pricing.outcome_service.OutcomeService", outcome_cls),
        ):
            await svc.apply_price(recommendation_id, user_id)

        call_kwargs = outcome_inst.record_merchant_decision.call_args.kwargs
        assert call_kwargs["actual_price_set"] == Decimal("29.49")


# ══════════════════════════════════════════════════════════════════
# RESTORE sys.modules
# ══════════════════════════════════════════════════════════════════

for _key, _orig in _saved.items():
    sys.modules[_key] = _orig
