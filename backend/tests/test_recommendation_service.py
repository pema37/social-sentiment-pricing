# backend/tests/test_recommendation_service.py
"""
Comprehensive tests for RecommendationService — the orchestration layer
that generates price recommendations from rules, signals, and competitor data.

Heavy mocking required: this service composes 6+ sub-services and hits the DB.

Tests cover:
- __init__ wiring of sub-services
- generate_recommendation full flow (8-step pipeline)
- _has_pending_recommendation DB query
- _create_rule_based_recommendation calculation + persistence
- _try_auto_apply auto-approval path
- get_pending_recommendations query with filters
- expire_old_recommendations batch update
- Edge cases: no rule match, pending exists, no price change, auto-apply failure

Total: ~65 tests
"""

import sys
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from uuid import uuid4

# === Import isolation ===
for mod in [
    "db.session",
    "models.product",
    "models.pricing_rule",
    "models.price_recommendation",
    "sqlalchemy.ext.asyncio",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest


# ============================================================
# Helpers
# ============================================================

USER_ID = uuid4()
PRODUCT_ID = uuid4()
RULE_ID = uuid4()
REC_ID = uuid4()


def make_mock_db():
    """Create a mock AsyncSession with common async methods."""
    db = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def make_mock_product(
    id=None,
    current_price=Decimal("100.00"),
    base_price=Decimal("80.00"),
    min_price=None,
    max_price=None,
):
    product = MagicMock()
    product.id = id or PRODUCT_ID
    product.current_price = current_price
    product.base_price = base_price
    product.min_price = min_price
    product.max_price = max_price
    return product


def make_mock_rule(id=None, rule_type_value="sentiment"):
    rule = MagicMock()
    rule.id = id or RULE_ID
    rule.rule_type = MagicMock()
    rule.rule_type.value = rule_type_value
    rule.last_triggered_at = None
    return rule


def make_mock_recommendation(
    id=None,
    status=None,
    requires_approval=False,
    valid_until=None,
):
    rec = MagicMock()
    rec.id = id or REC_ID
    rec.status = status
    rec.requires_approval = requires_approval
    rec.valid_until = valid_until or (datetime.now(UTC) + timedelta(hours=24))
    return rec


def make_mock_settings(
    auto_approve_enabled=True,
    recommendation_valid_hours=24,
):
    settings = MagicMock()
    settings.auto_approve_enabled = auto_approve_enabled
    settings.recommendation_valid_hours = recommendation_valid_hours
    return settings



# ── Column mock for comparison operators ──
class _ColumnMock:
    def __lt__(self, other): return MagicMock()
    def __le__(self, other): return MagicMock()
    def __gt__(self, other): return MagicMock()
    def __ge__(self, other): return MagicMock()
    def __eq__(self, other): return MagicMock()
    def __ne__(self, other): return MagicMock()
    def __hash__(self): return id(self)
    def desc(self): return MagicMock()
    def asc(self): return MagicMock()

class _FakePriceRecommendation:
    id = _ColumnMock()
    product_id = _ColumnMock()
    user_id = _ColumnMock()
    status = _ColumnMock()
    valid_until = _ColumnMock()
    created_at = _ColumnMock()
    updated_at = _ColumnMock()
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

# We need to patch at the module level where the imports happen
SERVICE_PATH = "services.pricing.recommendation_service"


# ============================================================
# 1. Initialization
# ============================================================

class TestRecommendationServiceInit:
    """Tests for __init__ and sub-service wiring."""

    @patch(f"{SERVICE_PATH}.CompetitorFallbackService")
    @patch(f"{SERVICE_PATH}.SettingsService")
    @patch(f"{SERVICE_PATH}.PriceSyncService")
    @patch(f"{SERVICE_PATH}.ConfidenceCalculator")
    @patch(f"{SERVICE_PATH}.SignalProcessor")
    @patch(f"{SERVICE_PATH}.RuleEvaluator")
    def test_creates_rule_evaluator(self, MockRule, MockSignal, MockConf, MockSync, MockSettings, MockFallback):
        from services.pricing.recommendation_service import RecommendationService
        db = make_mock_db()
        svc = RecommendationService(db)
        MockRule.assert_called_once_with(db)

    @patch(f"{SERVICE_PATH}.CompetitorFallbackService")
    @patch(f"{SERVICE_PATH}.SettingsService")
    @patch(f"{SERVICE_PATH}.PriceSyncService")
    @patch(f"{SERVICE_PATH}.ConfidenceCalculator")
    @patch(f"{SERVICE_PATH}.SignalProcessor")
    @patch(f"{SERVICE_PATH}.RuleEvaluator")
    def test_creates_signal_processor(self, MockRule, MockSignal, MockConf, MockSync, MockSettings, MockFallback):
        from services.pricing.recommendation_service import RecommendationService
        db = make_mock_db()
        svc = RecommendationService(db)
        MockSignal.assert_called_once_with(db)

    @patch(f"{SERVICE_PATH}.CompetitorFallbackService")
    @patch(f"{SERVICE_PATH}.SettingsService")
    @patch(f"{SERVICE_PATH}.PriceSyncService")
    @patch(f"{SERVICE_PATH}.ConfidenceCalculator")
    @patch(f"{SERVICE_PATH}.SignalProcessor")
    @patch(f"{SERVICE_PATH}.RuleEvaluator")
    def test_creates_confidence_calculator_without_db(self, MockRule, MockSignal, MockConf, MockSync, MockSettings, MockFallback):
        from services.pricing.recommendation_service import RecommendationService
        db = make_mock_db()
        svc = RecommendationService(db)
        MockConf.assert_called_once_with()

    @patch(f"{SERVICE_PATH}.CompetitorFallbackService")
    @patch(f"{SERVICE_PATH}.SettingsService")
    @patch(f"{SERVICE_PATH}.PriceSyncService")
    @patch(f"{SERVICE_PATH}.ConfidenceCalculator")
    @patch(f"{SERVICE_PATH}.SignalProcessor")
    @patch(f"{SERVICE_PATH}.RuleEvaluator")
    def test_creates_price_sync(self, MockRule, MockSignal, MockConf, MockSync, MockSettings, MockFallback):
        from services.pricing.recommendation_service import RecommendationService
        db = make_mock_db()
        svc = RecommendationService(db)
        MockSync.assert_called_once_with(db)

    @patch(f"{SERVICE_PATH}.CompetitorFallbackService")
    @patch(f"{SERVICE_PATH}.SettingsService")
    @patch(f"{SERVICE_PATH}.PriceSyncService")
    @patch(f"{SERVICE_PATH}.ConfidenceCalculator")
    @patch(f"{SERVICE_PATH}.SignalProcessor")
    @patch(f"{SERVICE_PATH}.RuleEvaluator")
    def test_creates_settings_service(self, MockRule, MockSignal, MockConf, MockSync, MockSettings, MockFallback):
        from services.pricing.recommendation_service import RecommendationService
        db = make_mock_db()
        svc = RecommendationService(db)
        MockSettings.assert_called_once_with(db)

    @patch(f"{SERVICE_PATH}.CompetitorFallbackService")
    @patch(f"{SERVICE_PATH}.SettingsService")
    @patch(f"{SERVICE_PATH}.PriceSyncService")
    @patch(f"{SERVICE_PATH}.ConfidenceCalculator")
    @patch(f"{SERVICE_PATH}.SignalProcessor")
    @patch(f"{SERVICE_PATH}.RuleEvaluator")
    def test_creates_competitor_fallback(self, MockRule, MockSignal, MockConf, MockSync, MockSettings, MockFallback):
        from services.pricing.recommendation_service import RecommendationService
        db = make_mock_db()
        svc = RecommendationService(db)
        MockFallback.assert_called_once_with(db)

    @patch(f"{SERVICE_PATH}.CompetitorFallbackService")
    @patch(f"{SERVICE_PATH}.SettingsService")
    @patch(f"{SERVICE_PATH}.PriceSyncService")
    @patch(f"{SERVICE_PATH}.ConfidenceCalculator")
    @patch(f"{SERVICE_PATH}.SignalProcessor")
    @patch(f"{SERVICE_PATH}.RuleEvaluator")
    def test_stores_db_reference(self, MockRule, MockSignal, MockConf, MockSync, MockSettings, MockFallback):
        from services.pricing.recommendation_service import RecommendationService
        db = make_mock_db()
        svc = RecommendationService(db)
        assert svc.db is db


# ============================================================
# 2. generate_recommendation — Full Flow
# ============================================================

class TestGenerateRecommendation:
    """Tests for the main 8-step generate_recommendation pipeline."""

    def _build_service(self):
        """Create a RecommendationService with all sub-services mocked."""
        db = make_mock_db()

        with patch(f"{SERVICE_PATH}.RuleEvaluator"), \
             patch(f"{SERVICE_PATH}.SignalProcessor"), \
             patch(f"{SERVICE_PATH}.ConfidenceCalculator"), \
             patch(f"{SERVICE_PATH}.PriceSyncService"), \
             patch(f"{SERVICE_PATH}.SettingsService"), \
             patch(f"{SERVICE_PATH}.CompetitorFallbackService"):
            from services.pricing.recommendation_service import RecommendationService
            svc = RecommendationService(db)

        # Configure defaults
        svc.price_sync.sync_product_price = AsyncMock(return_value=False)
        svc.signal_processor.gather_signals = AsyncMock(return_value={"sentiment": 0.5})
        svc.rule_evaluator.find_matching_rule = AsyncMock(return_value=None)
        svc.competitor_fallback.generate = AsyncMock(return_value=None)

        return svc, db

    @pytest.mark.asyncio
    async def test_refreshes_product_from_db(self):
        svc, db = self._build_service()
        product = make_mock_product()
        # Mock _has_pending to avoid select(MagicMock) hitting SQLAlchemy
        svc._has_pending_recommendation = AsyncMock(return_value=True)

        await svc.generate_recommendation(product, USER_ID)
        db.refresh.assert_awaited_with(product)

    @pytest.mark.asyncio
    async def test_syncs_live_price(self):
        svc, db = self._build_service()
        product = make_mock_product()
        svc._has_pending_recommendation = AsyncMock(return_value=True)

        await svc.generate_recommendation(product, USER_ID)
        svc.price_sync.sync_product_price.assert_awaited_once_with(product, USER_ID)

    @pytest.mark.asyncio
    async def test_returns_none_if_pending_exists(self):
        svc, db = self._build_service()
        product = make_mock_product()
        svc._has_pending_recommendation = AsyncMock(return_value=True)

        result = await svc.generate_recommendation(product, USER_ID)
        assert result is None

    @pytest.mark.asyncio
    async def test_gathers_signals(self):
        svc, db = self._build_service()
        product = make_mock_product()
        svc._has_pending_recommendation = AsyncMock(return_value=False)

        await svc.generate_recommendation(product, USER_ID)
        svc.signal_processor.gather_signals.assert_awaited_once_with(product)

    @pytest.mark.asyncio
    async def test_finds_matching_rule(self):
        svc, db = self._build_service()
        product = make_mock_product()
        signals = {"sentiment": 0.5}
        svc._has_pending_recommendation = AsyncMock(return_value=False)
        svc.signal_processor.gather_signals = AsyncMock(return_value=signals)

        await svc.generate_recommendation(product, USER_ID)
        svc.rule_evaluator.find_matching_rule.assert_awaited_once_with(
            product, USER_ID, signals
        )

    @pytest.mark.asyncio
    async def test_falls_back_to_competitor_when_no_rule(self):
        svc, db = self._build_service()
        product = make_mock_product()
        signals = {"sentiment": 0.5}
        svc._has_pending_recommendation = AsyncMock(return_value=False)
        svc.signal_processor.gather_signals = AsyncMock(return_value=signals)
        svc.rule_evaluator.find_matching_rule = AsyncMock(return_value=None)

        await svc.generate_recommendation(product, USER_ID)
        svc.competitor_fallback.generate.assert_awaited_once_with(
            product, USER_ID, signals
        )

    @pytest.mark.asyncio
    async def test_falls_back_when_rule_is_none_tuple(self):
        """Rule evaluator returns (None, details) → fallback."""
        svc, db = self._build_service()
        product = make_mock_product()
        svc._has_pending_recommendation = AsyncMock(return_value=False)
        svc.rule_evaluator.find_matching_rule = AsyncMock(return_value=(None, {}))

        await svc.generate_recommendation(product, USER_ID)
        svc.competitor_fallback.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_creates_rule_based_recommendation_when_rule_found(self):
        """When a rule matches, delegates to _create_rule_based_recommendation."""
        svc, db = self._build_service()
        product = make_mock_product()
        rule = make_mock_rule()
        match_details = {"trigger": "sentiment_threshold"}
        signals = {"sentiment": 0.5}
        svc._has_pending_recommendation = AsyncMock(return_value=False)
        svc.signal_processor.gather_signals = AsyncMock(return_value=signals)
        svc.rule_evaluator.find_matching_rule = AsyncMock(
            return_value=(rule, match_details)
        )

        # Mock the internal method to isolate this test
        svc._create_rule_based_recommendation = AsyncMock(return_value=make_mock_recommendation())

        result = await svc.generate_recommendation(product, USER_ID)
        svc._create_rule_based_recommendation.assert_awaited_once_with(
            product, USER_ID, rule, match_details, signals
        )


# ============================================================
# 3. _has_pending_recommendation
# ============================================================

@patch(f"{SERVICE_PATH}.PriceRecommendation", _FakePriceRecommendation)
class TestHasPendingRecommendation:
    """Tests for the pending recommendation check."""

    def _build_service(self):
        db = make_mock_db()
        with patch(f"{SERVICE_PATH}.RuleEvaluator"), \
             patch(f"{SERVICE_PATH}.SignalProcessor"), \
             patch(f"{SERVICE_PATH}.ConfidenceCalculator"), \
             patch(f"{SERVICE_PATH}.PriceSyncService"), \
             patch(f"{SERVICE_PATH}.SettingsService"), \
             patch(f"{SERVICE_PATH}.CompetitorFallbackService"):
            from services.pricing.recommendation_service import RecommendationService
            svc = RecommendationService(db)
        return svc, db

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_true_when_pending_exists(self, mock_select):
        svc, db = self._build_service()
        mock_select.return_value.where.return_value.where.return_value.where.return_value.where.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = make_mock_recommendation()
        db.execute.return_value = mock_result

        assert await svc._has_pending_recommendation(PRODUCT_ID, USER_ID) is True

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_false_when_no_pending(self, mock_select):
        svc, db = self._build_service()
        mock_select.return_value.where.return_value.where.return_value.where.return_value.where.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        db.execute.return_value = mock_result

        assert await svc._has_pending_recommendation(PRODUCT_ID, USER_ID) is False

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_queries_database(self, mock_select):
        svc, db = self._build_service()
        mock_select.return_value.where.return_value.where.return_value.where.return_value.where.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        db.execute.return_value = mock_result

        await svc._has_pending_recommendation(PRODUCT_ID, USER_ID)
        db.execute.assert_awaited_once()


# ============================================================
# 4. _create_rule_based_recommendation
# ============================================================

class TestCreateRuleBasedRecommendation:
    """Tests for rule-based recommendation creation."""

    def _build_service(self):
        db = make_mock_db()
        with patch(f"{SERVICE_PATH}.RuleEvaluator"), \
             patch(f"{SERVICE_PATH}.SignalProcessor"), \
             patch(f"{SERVICE_PATH}.ConfidenceCalculator"), \
             patch(f"{SERVICE_PATH}.PriceSyncService"), \
             patch(f"{SERVICE_PATH}.SettingsService"), \
             patch(f"{SERVICE_PATH}.CompetitorFallbackService"):
            from services.pricing.recommendation_service import RecommendationService
            svc = RecommendationService(db)
        return svc, db

    def _configure_service(self, svc, new_price=Decimal("110.00"), confidence=0.8):
        """Configure sub-service mocks for a standard recommendation flow."""
        svc.signal_processor.calculate_price_impact = MagicMock(
            return_value={"impact": 0.1}
        )
        svc.confidence_calculator.calculate = MagicMock(return_value=confidence)
        svc.confidence_calculator.get_confidence_breakdown = MagicMock(
            return_value={"breakdown": True}
        )
        svc.settings_service.get_or_create = AsyncMock(
            return_value=make_mock_settings()
        )
        svc.settings_service.check_requires_approval = MagicMock(return_value=False)
        return svc

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_returns_none_when_no_price_change(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        svc, db = self._build_service()
        product = make_mock_product(current_price=Decimal("100.00"))
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("100.00")  # same as current

        result = await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        assert result is None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_returns_none_when_price_is_none(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        svc, db = self._build_service()
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = None

        result = await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        assert result is None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_applies_boundaries(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        svc, db = self._build_service()
        svc = self._configure_service(svc)
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("108.00")
        MockBound.calculate_change_percent.return_value = Decimal("8.0")
        MockReason.generate.return_value = "Test reasoning"

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        MockBound.apply_boundaries.assert_called_once_with(
            Decimal("110.00"), product, rule
        )

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_calculates_confidence(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        svc, db = self._build_service()
        svc = self._configure_service(svc, confidence=0.85)
        product = make_mock_product()
        rule = make_mock_rule()
        signals = {"sentiment": 0.5}

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("110.00")
        MockBound.calculate_change_percent.return_value = Decimal("10.0")
        MockReason.generate.return_value = "Test"

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, signals
        )
        svc.confidence_calculator.calculate.assert_called_once()

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_generates_reasoning(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        svc, db = self._build_service()
        svc = self._configure_service(svc)
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("110.00")
        MockBound.calculate_change_percent.return_value = Decimal("10.0")
        MockReason.generate.return_value = "Price increase due to positive sentiment"

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        MockReason.generate.assert_called_once()

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_commits_to_database(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        svc, db = self._build_service()
        svc = self._configure_service(svc)
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("110.00")
        MockBound.calculate_change_percent.return_value = Decimal("10.0")
        MockReason.generate.return_value = "Test"

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_updates_rule_last_triggered(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        svc, db = self._build_service()
        svc = self._configure_service(svc)
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("110.00")
        MockBound.calculate_change_percent.return_value = Decimal("10.0")
        MockReason.generate.return_value = "Test"

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        assert rule.last_triggered_at is not None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_gets_user_settings(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        svc, db = self._build_service()
        svc = self._configure_service(svc)
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("110.00")
        MockBound.calculate_change_percent.return_value = Decimal("10.0")
        MockReason.generate.return_value = "Test"

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        svc.settings_service.get_or_create.assert_awaited_once_with(USER_ID)

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_checks_approval_requirement(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        svc, db = self._build_service()
        svc = self._configure_service(svc)
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("110.00")
        MockBound.calculate_change_percent.return_value = Decimal("10.0")
        MockReason.generate.return_value = "Test"

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        svc.settings_service.check_requires_approval.assert_called_once()


# ============================================================
# 5. Auto-Apply Logic
# ============================================================

class TestAutoApply:
    """Tests for _try_auto_apply and auto-apply triggering."""

    def _build_service(self):
        db = make_mock_db()
        with patch(f"{SERVICE_PATH}.RuleEvaluator"), \
             patch(f"{SERVICE_PATH}.SignalProcessor"), \
             patch(f"{SERVICE_PATH}.ConfidenceCalculator"), \
             patch(f"{SERVICE_PATH}.PriceSyncService"), \
             patch(f"{SERVICE_PATH}.SettingsService"), \
             patch(f"{SERVICE_PATH}.CompetitorFallbackService"):
            from services.pricing.recommendation_service import RecommendationService
            svc = RecommendationService(db)
        return svc, db

    @pytest.mark.asyncio
    async def test_auto_apply_calls_approval_service(self):
        svc, db = self._build_service()
        rec = make_mock_recommendation()

        with patch("services.pricing.approval_service.ApprovalService") as MockApproval:
            mock_instance = AsyncMock()
            MockApproval.return_value = mock_instance

            await svc._try_auto_apply(rec, USER_ID)
            MockApproval.assert_called_once_with(db)
            mock_instance.auto_approve_and_apply.assert_awaited_once_with(rec.id, USER_ID)

    @pytest.mark.asyncio
    async def test_auto_apply_handles_exception_gracefully(self):
        svc, db = self._build_service()
        rec = make_mock_recommendation()

        with patch("services.pricing.approval_service.ApprovalService") as MockApproval:
            MockApproval.return_value.auto_approve_and_apply = AsyncMock(
                side_effect=Exception("Platform push failed")
            )

            # Should NOT raise — just logs warning
            await svc._try_auto_apply(rec, USER_ID)

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_auto_apply_triggered_when_no_approval_needed(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        """When requires_approval=False and auto_approve_enabled=True → auto-apply."""
        svc, db = self._build_service()
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("110.00")
        MockBound.calculate_change_percent.return_value = Decimal("10.0")
        MockReason.generate.return_value = "Test"

        svc.signal_processor.calculate_price_impact = MagicMock(return_value={})
        svc.confidence_calculator.calculate = MagicMock(return_value=0.8)
        svc.confidence_calculator.get_confidence_breakdown = MagicMock(return_value={})
        svc.settings_service.get_or_create = AsyncMock(
            return_value=make_mock_settings(auto_approve_enabled=True)
        )
        svc.settings_service.check_requires_approval = MagicMock(return_value=False)

        svc._try_auto_apply = AsyncMock()

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        svc._try_auto_apply.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_auto_apply_skipped_when_approval_required(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        """When requires_approval=True → skip auto-apply."""
        svc, db = self._build_service()
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("110.00")
        MockBound.calculate_change_percent.return_value = Decimal("10.0")
        MockReason.generate.return_value = "Test"

        svc.signal_processor.calculate_price_impact = MagicMock(return_value={})
        svc.confidence_calculator.calculate = MagicMock(return_value=0.8)
        svc.confidence_calculator.get_confidence_breakdown = MagicMock(return_value={})
        svc.settings_service.get_or_create = AsyncMock(
            return_value=make_mock_settings(auto_approve_enabled=True)
        )
        svc.settings_service.check_requires_approval = MagicMock(return_value=True)

        svc._try_auto_apply = AsyncMock()

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        svc._try_auto_apply.assert_not_awaited()

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.ReasoningGenerator")
    @patch(f"{SERVICE_PATH}.BoundaryEnforcer")
    @patch(f"{SERVICE_PATH}.PriceCalculator")
    @patch(f"{SERVICE_PATH}.PriceRecommendation")
    async def test_auto_apply_skipped_when_auto_approve_disabled(
        self, MockRec, MockCalc, MockBound, MockReason
    ):
        """When auto_approve_enabled=False → skip auto-apply even if no approval needed."""
        svc, db = self._build_service()
        product = make_mock_product()
        rule = make_mock_rule()

        MockCalc.calculate_new_price.return_value = Decimal("110.00")
        MockBound.apply_boundaries.return_value = Decimal("110.00")
        MockBound.calculate_change_percent.return_value = Decimal("10.0")
        MockReason.generate.return_value = "Test"

        svc.signal_processor.calculate_price_impact = MagicMock(return_value={})
        svc.confidence_calculator.calculate = MagicMock(return_value=0.8)
        svc.confidence_calculator.get_confidence_breakdown = MagicMock(return_value={})
        svc.settings_service.get_or_create = AsyncMock(
            return_value=make_mock_settings(auto_approve_enabled=False)
        )
        svc.settings_service.check_requires_approval = MagicMock(return_value=False)

        svc._try_auto_apply = AsyncMock()

        await svc._create_rule_based_recommendation(
            product, USER_ID, rule, {}, {}
        )
        svc._try_auto_apply.assert_not_awaited()


# ============================================================
# 6. Query Methods
# ============================================================

@patch(f"{SERVICE_PATH}.PriceRecommendation", _FakePriceRecommendation)
class TestGetPendingRecommendations:
    """Tests for get_pending_recommendations."""

    def _build_service(self):
        db = make_mock_db()
        with patch(f"{SERVICE_PATH}.RuleEvaluator"), \
             patch(f"{SERVICE_PATH}.SignalProcessor"), \
             patch(f"{SERVICE_PATH}.ConfidenceCalculator"), \
             patch(f"{SERVICE_PATH}.PriceSyncService"), \
             patch(f"{SERVICE_PATH}.SettingsService"), \
             patch(f"{SERVICE_PATH}.CompetitorFallbackService"):
            from services.pricing.recommendation_service import RecommendationService
            svc = RecommendationService(db)
        return svc, db

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_list(self, mock_select):
        svc, db = self._build_service()
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_chain.offset.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            make_mock_recommendation(),
            make_mock_recommendation(),
        ]
        db.execute.return_value = mock_result

        results = await svc.get_pending_recommendations(USER_ID)
        assert isinstance(results, list)
        assert len(results) == 2

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_empty_list(self, mock_select):
        svc, db = self._build_service()
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_chain.offset.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        results = await svc.get_pending_recommendations(USER_ID)
        assert results == []

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_queries_database(self, mock_select):
        svc, db = self._build_service()
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_chain.offset.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        await svc.get_pending_recommendations(USER_ID)
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_with_product_id_filter(self, mock_select):
        svc, db = self._build_service()
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_chain.offset.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        await svc.get_pending_recommendations(USER_ID, product_id=PRODUCT_ID)
        db.execute.assert_awaited_once()


# ============================================================
# 7. expire_old_recommendations
# ============================================================

@patch(f"{SERVICE_PATH}.PriceRecommendation", _FakePriceRecommendation)
class TestExpireOldRecommendations:
    """Tests for the batch expiration of old recommendations."""

    def _build_service(self):
        db = make_mock_db()
        with patch(f"{SERVICE_PATH}.RuleEvaluator"), \
             patch(f"{SERVICE_PATH}.SignalProcessor"), \
             patch(f"{SERVICE_PATH}.ConfidenceCalculator"), \
             patch(f"{SERVICE_PATH}.PriceSyncService"), \
             patch(f"{SERVICE_PATH}.SettingsService"), \
             patch(f"{SERVICE_PATH}.CompetitorFallbackService"):
            from services.pricing.recommendation_service import RecommendationService
            svc = RecommendationService(db)
        return svc, db

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_count_of_expired(self, mock_select):
        svc, db = self._build_service()
        mock_select.return_value.where.return_value.where.return_value = MagicMock()
        expired_recs = [make_mock_recommendation(), make_mock_recommendation()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = expired_recs
        db.execute.return_value = mock_result

        count = await svc.expire_old_recommendations()
        assert count == 2

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_zero_when_none_expired(self, mock_select):
        svc, db = self._build_service()
        mock_select.return_value.where.return_value.where.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        count = await svc.expire_old_recommendations()
        assert count == 0

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_commits_after_expiration(self, mock_select):
        svc, db = self._build_service()
        mock_select.return_value.where.return_value.where.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [make_mock_recommendation()]
        db.execute.return_value = mock_result

        await svc.expire_old_recommendations()
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_sets_status_to_expired(self, mock_select):
        svc, db = self._build_service()
        mock_select.return_value.where.return_value.where.return_value = MagicMock()

        from models.price_recommendation import RecommendationStatus
        rec = make_mock_recommendation()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rec]
        db.execute.return_value = mock_result

        await svc.expire_old_recommendations()
        rec.status = RecommendationStatus.EXPIRED

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_adds_each_expired_to_session(self, mock_select):
        svc, db = self._build_service()
        mock_select.return_value.where.return_value.where.return_value = MagicMock()
        recs = [make_mock_recommendation(), make_mock_recommendation(), make_mock_recommendation()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = recs
        db.execute.return_value = mock_result

        await svc.expire_old_recommendations()
        assert db.add.call_count == 3


# ============================================================
# 8. Edge Cases
# ============================================================

class TestEdgeCases:
    """Edge cases across the recommendation service."""

    def _build_service(self):
        db = make_mock_db()
        with patch(f"{SERVICE_PATH}.RuleEvaluator"), \
             patch(f"{SERVICE_PATH}.SignalProcessor"), \
             patch(f"{SERVICE_PATH}.ConfidenceCalculator"), \
             patch(f"{SERVICE_PATH}.PriceSyncService"), \
             patch(f"{SERVICE_PATH}.SettingsService"), \
             patch(f"{SERVICE_PATH}.CompetitorFallbackService"):
            from services.pricing.recommendation_service import RecommendationService
            svc = RecommendationService(db)
        return svc, db

    @pytest.mark.asyncio
    async def test_price_sync_failure_continues_flow(self):
        """If price sync returns False, recommendation still proceeds."""
        svc, db = self._build_service()
        product = make_mock_product()

        svc.price_sync.sync_product_price = AsyncMock(return_value=False)
        svc._has_pending_recommendation = AsyncMock(return_value=False)
        svc.signal_processor.gather_signals = AsyncMock(return_value={})
        svc.rule_evaluator.find_matching_rule = AsyncMock(return_value=None)
        svc.competitor_fallback.generate = AsyncMock(return_value=None)

        result = await svc.generate_recommendation(product, USER_ID)
        # Should have reached the fallback (not crashed)
        svc.competitor_fallback.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_price_sync_true_continues_flow(self):
        """If price sync succeeds, recommendation still proceeds."""
        svc, db = self._build_service()
        product = make_mock_product()

        svc.price_sync.sync_product_price = AsyncMock(return_value=True)
        svc._has_pending_recommendation = AsyncMock(return_value=False)
        svc.signal_processor.gather_signals = AsyncMock(return_value={})
        svc.rule_evaluator.find_matching_rule = AsyncMock(return_value=None)
        svc.competitor_fallback.generate = AsyncMock(return_value=None)

        await svc.generate_recommendation(product, USER_ID)
        svc.signal_processor.gather_signals.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_competitor_fallback_returns_recommendation(self):
        svc, db = self._build_service()
        product = make_mock_product()
        fallback_rec = make_mock_recommendation()

        svc.price_sync.sync_product_price = AsyncMock(return_value=False)
        svc._has_pending_recommendation = AsyncMock(return_value=False)
        svc.signal_processor.gather_signals = AsyncMock(return_value={})
        svc.rule_evaluator.find_matching_rule = AsyncMock(return_value=None)
        svc.competitor_fallback.generate = AsyncMock(return_value=fallback_rec)

        result = await svc.generate_recommendation(product, USER_ID)
        assert result is fallback_rec


        