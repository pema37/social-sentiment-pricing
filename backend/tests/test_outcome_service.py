# backend/tests/test_outcome_service.py
"""
Tests for OutcomeService — records and analyzes recommendation outcomes.

Total: ~24 tests
"""

import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# === Minimal isolation — only mock db.session ===
if "db.session" not in sys.modules:
    sys.modules["db.session"] = MagicMock()

import pytest

# Import real enums — these work fine
from models.recommendation_outcome import OutcomeLabel
from models.price_recommendation import RecommendationStatus

SERVICE_PATH = "services.pricing.outcome_service"

# We need a fake class that stores kwargs as attributes
# AND has class-level column mocks for SQLAlchemy query building
class _FakeOutcome:
    # Class-level attributes for SQLAlchemy query building
    recommendation_id = MagicMock()
    user_id = MagicMock()
    product_id = MagicMock()
    rule_id = MagicMock()
    rule_type = MagicMock()
    outcome_label = MagicMock()
    # created_at needs comparison operators for >= cutoff queries
    created_at = MagicMock()
    try:
        created_at.__ge__ = MagicMock(return_value=MagicMock())
        created_at.__le__ = MagicMock(return_value=MagicMock())
        created_at.__gt__ = MagicMock(return_value=MagicMock())
        created_at.__lt__ = MagicMock(return_value=MagicMock())
        created_at.desc = MagicMock(return_value=MagicMock())
    except (AttributeError, TypeError):
        pass  # Real SQLAlchemy model — operators already work

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

# Patch RecommendationOutcome at the SERVICE level so the service
# constructs _FakeOutcome instead of the real SQLModel class
_outcome_patch = patch(f"{SERVICE_PATH}.RecommendationOutcome", _FakeOutcome)
_outcome_patch.start()

from services.pricing.outcome_service import OutcomeService

# ============================================================
# Helpers
# ============================================================

USER_ID = uuid4()
REC_ID = uuid4()
PRODUCT_ID = uuid4()
RULE_ID = uuid4()


def make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=None)
    return db


def make_recommendation(
    status=None,
    user_id=None,
    product_id=None,
    current_price=Decimal("100.00"),
    recommended_price=Decimal("110.00"),
    change_percent=Decimal("10.00"),
    confidence_score=Decimal("0.85"),
    triggered_rule_id=None,
    applied_at=None,
):
    rec = MagicMock()
    rec.id = REC_ID
    rec.user_id = user_id or USER_ID
    rec.product_id = product_id or PRODUCT_ID
    rec.status = status if status is not None else RecommendationStatus.APPLIED
    rec.current_price = current_price
    rec.recommended_price = recommended_price
    rec.change_percent = change_percent
    rec.confidence_score = confidence_score
    rec.triggered_rule_id = triggered_rule_id
    rec.applied_at = applied_at or datetime(2026, 1, 1, 12, 0)
    return rec


# ============================================================
# 1. Initialization & Constants
# ============================================================

class TestOutcomeServiceInit:

    def test_stores_db(self):
        db = make_mock_db()
        svc = OutcomeService(db)
        assert svc.db is db

    def test_thresholds(self):
        assert OutcomeService.POSITIVE_THRESHOLD == Decimal("0.02")
        assert OutcomeService.NEGATIVE_THRESHOLD == Decimal("-0.02")
        assert OutcomeService.MIN_DATA_THRESHOLD == 3


# ============================================================
# 2. _calculate_outcome
# ============================================================

class TestCalculateOutcome:

    def setup_method(self):
        self.svc = OutcomeService(make_mock_db())

    def test_positive_outcome(self):
        score, label = self.svc._calculate_outcome(
            Decimal("1000"), Decimal("1200"), 50, 55, Decimal("5"),
        )
        assert score > Decimal("0")
        assert label == OutcomeLabel.POSITIVE

    def test_negative_outcome(self):
        score, label = self.svc._calculate_outcome(
            Decimal("1000"), Decimal("800"), 50, 40, Decimal("5"),
        )
        assert score < Decimal("0")
        assert label == OutcomeLabel.NEGATIVE

    def test_neutral_outcome(self):
        score, label = self.svc._calculate_outcome(
            Decimal("1000"), Decimal("1005"), 50, 50, Decimal("5"),
        )
        assert label == OutcomeLabel.NEUTRAL

    def test_inconclusive_low_data(self):
        score, label = self.svc._calculate_outcome(
            Decimal("50"), Decimal("60"), 2, 2, Decimal("5"),
        )
        assert label == OutcomeLabel.INCONCLUSIVE
        assert score == Decimal("0")

    def test_score_clamped_to_range(self):
        score, _ = self.svc._calculate_outcome(
            Decimal("100"), Decimal("1000"), 10, 100, Decimal("5"),
        )
        assert Decimal("-1") <= score <= Decimal("1")

    def test_zero_revenue_before(self):
        score, _ = self.svc._calculate_outcome(
            Decimal("0"), Decimal("500"), 0, 10, Decimal("5"),
        )
        assert score > Decimal("0")

    def test_zero_both(self):
        score, label = self.svc._calculate_outcome(
            Decimal("0"), Decimal("0"), 0, 0, Decimal("5"),
        )
        assert label == OutcomeLabel.INCONCLUSIVE

    def test_revenue_weighted_more_than_units(self):
        score, _ = self.svc._calculate_outcome(
            Decimal("1000"), Decimal("1200"), 100, 90, Decimal("10"),
        )
        assert score > Decimal("0")


# ============================================================
# 3. record_outcome
# ============================================================

class TestRecordOutcome:

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_recommendation_not_found(self, mock_select):
        db = make_mock_db()
        db.get.return_value = None
        svc = OutcomeService(db)

        with pytest.raises(ValueError, match="Recommendation not found"):
            await svc.record_outcome(
                REC_ID, USER_ID, 10, 50, Decimal("1000"), 12, 55, Decimal("1100"),
            )

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_wrong_user_rejected(self, mock_select):
        db = make_mock_db()
        rec = make_recommendation(user_id=uuid4())
        db.get.return_value = rec
        svc = OutcomeService(db)

        with pytest.raises(ValueError, match="Recommendation not found"):
            await svc.record_outcome(
                REC_ID, USER_ID, 10, 50, Decimal("1000"), 12, 55, Decimal("1100"),
            )

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_not_applied_rejected(self, mock_select):
        db = make_mock_db()
        rec = make_recommendation(status=RecommendationStatus.PENDING)
        db.get.return_value = rec
        svc = OutcomeService(db)

        with pytest.raises(ValueError, match="not applied"):
            await svc.record_outcome(
                REC_ID, USER_ID, 10, 50, Decimal("1000"), 12, 55, Decimal("1100"),
            )

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_duplicate_outcome_rejected(self, mock_select):
        db = make_mock_db()
        rec = make_recommendation()
        db.get.return_value = rec

        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = MagicMock()
        db.execute.return_value = mock_result
        svc = OutcomeService(db)

        with pytest.raises(ValueError, match="already recorded"):
            await svc.record_outcome(
                REC_ID, USER_ID, 10, 50, Decimal("1000"), 12, 55, Decimal("1100"),
            )

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_successful_record(self, mock_select):
        db = make_mock_db()
        rec = make_recommendation()
        db.get.side_effect = [rec, None]

        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        db.execute.return_value = mock_result

        svc = OutcomeService(db)
        outcome = await svc.record_outcome(
            REC_ID, USER_ID, 10, 50, Decimal("1000"), 12, 55, Decimal("1100"),
        )

        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert outcome.revenue_change == Decimal("100")

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_revenue_change_percent_calculated(self, mock_select):
        db = make_mock_db()
        rec = make_recommendation()
        db.get.side_effect = [rec, None]

        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        db.execute.return_value = mock_result

        svc = OutcomeService(db)
        outcome = await svc.record_outcome(
            REC_ID, USER_ID, 10, 50, Decimal("1000"), 12, 55, Decimal("1100"),
        )
        assert outcome.revenue_change_percent == Decimal("10.00")


# ============================================================
# 4. get_outcomes
# ============================================================

class TestGetOutcomes:

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_list(self, mock_select):
        db = make_mock_db()
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_chain.offset.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
        db.execute.return_value = mock_result

        svc = OutcomeService(db)
        result = await svc.get_outcomes(USER_ID)
        assert len(result) == 2

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_empty_results(self, mock_select):
        db = make_mock_db()
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_chain.offset.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        svc = OutcomeService(db)
        result = await svc.get_outcomes(USER_ID)
        assert result == []


# ============================================================
# 5. get_rule_performance
# ============================================================

class TestGetRulePerformance:

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_rule_not_found(self, mock_select):
        db = make_mock_db()
        db.get.return_value = None
        svc = OutcomeService(db)

        with pytest.raises(ValueError, match="Rule not found"):
            await svc.get_rule_performance(RULE_ID, USER_ID)

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_wrong_user_rule(self, mock_select):
        db = make_mock_db()
        rule = MagicMock()
        rule.user_id = uuid4()
        db.get.return_value = rule
        svc = OutcomeService(db)

        with pytest.raises(ValueError, match="Rule not found"):
            await svc.get_rule_performance(RULE_ID, USER_ID)

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_no_outcomes(self, mock_select):
        db = make_mock_db()
        rule = MagicMock()
        rule.user_id = USER_ID
        rule.name = "Test Rule"
        rule.rule_type = MagicMock()
        rule.rule_type.value = "sentiment"
        db.get.return_value = rule

        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        svc = OutcomeService(db)
        result = await svc.get_rule_performance(RULE_ID, USER_ID)
        assert result["total_outcomes"] == 0
        assert result["success_rate"] == Decimal("0")

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_with_outcomes(self, mock_select):
        db = make_mock_db()
        rule = MagicMock()
        rule.user_id = USER_ID
        rule.name = "Sentiment Rule"
        rule.rule_type = MagicMock()
        rule.rule_type.value = "sentiment"
        db.get.return_value = rule

        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        o1 = MagicMock()
        o1.outcome_label = OutcomeLabel.POSITIVE
        o1.outcome_score = Decimal("0.5")
        o1.revenue_change_percent = Decimal("10.00")
        o1.revenue_change = Decimal("100")
        o1.original_confidence = Decimal("0.85")

        o2 = MagicMock()
        o2.outcome_label = OutcomeLabel.NEGATIVE
        o2.outcome_score = Decimal("-0.3")
        o2.revenue_change_percent = Decimal("-5.00")
        o2.revenue_change = Decimal("-50")
        o2.original_confidence = Decimal("0.70")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [o1, o2]
        db.execute.return_value = mock_result

        svc = OutcomeService(db)
        result = await svc.get_rule_performance(RULE_ID, USER_ID)
        assert result["total_outcomes"] == 2
        assert result["positive_outcomes"] == 1
        assert result["negative_outcomes"] == 1


# ============================================================
# 6. get_historical_accuracy_for_rule_type
# ============================================================

class TestGetHistoricalAccuracy:

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_not_enough_data(self, mock_select):
        db = make_mock_db()
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [MagicMock(), MagicMock()]
        db.execute.return_value = mock_result

        svc = OutcomeService(db)
        result = await svc.get_historical_accuracy_for_rule_type(USER_ID, "sentiment")
        assert result == Decimal("0.5")

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_calculates_rate(self, mock_select):
        db = make_mock_db()
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        outcomes = []
        for i in range(10):
            o = MagicMock()
            o.outcome_label = OutcomeLabel.POSITIVE if i < 7 else OutcomeLabel.NEGATIVE
            outcomes.append(o)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = outcomes
        db.execute.return_value = mock_result

        svc = OutcomeService(db)
        result = await svc.get_historical_accuracy_for_rule_type(USER_ID, "sentiment")
        assert result == Decimal("0.70")

        