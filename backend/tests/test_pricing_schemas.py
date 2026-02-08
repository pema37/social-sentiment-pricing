"""
Test Suite: backend/schemas/pricing.py
Covers: PricingRuleCreate/Update/Response, PriceRecommendationResponse,
        RecommendationApprove/Reject, PricingSettingsUpdate/Response,
        MockSignals, RuleTestRequest/Response, SimulationRequest/Response,
        OutcomeRecordRequest/Response, RulePerformanceResponse, AccuracyStatsResponse.

Place this file at: backend/tests/test_pricing_schemas.py
Run with: pytest backend/tests/test_pricing_schemas.py -v
"""

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from models.pricing_rule import RuleType, RuleAction
from models.price_recommendation import RecommendationStatus
from models.recommendation_outcome import OutcomeLabel

from schemas.pricing import (
    PricingRuleCreate,
    PricingRuleUpdate,
    PricingRuleResponse,
    PriceRecommendationResponse,
    RecommendationApprove,
    RecommendationReject,
    RecommendationListParams,
    PricingSettingsUpdate,
    PricingSettingsResponse,
    MockSignals,
    RuleTestRequest,
    RuleTestResponse,
    SimulationRequest,
    SimulationResponse,
    OutcomeRecordRequest,
    OutcomeResponse,
    RulePerformanceResponse,
    AccuracyStatsResponse,
)


# =====================================================================
# PricingRuleCreate
# =====================================================================

class TestPricingRuleCreate:

    def test_valid_minimal(self):
        r = PricingRuleCreate(
            name="Sentiment Drop",
            rule_type=RuleType.SENTIMENT_THRESHOLD,
            action=RuleAction.DECREASE_PERCENT,
            action_value=Decimal("5.0"),
        )
        assert r.name == "Sentiment Drop"
        assert r.rule_type == RuleType.SENTIMENT_THRESHOLD
        assert r.action == RuleAction.DECREASE_PERCENT
        assert r.action_value == Decimal("5.0")
        assert r.product_id is None
        assert r.applies_to_all_products is False
        assert r.priority == 0
        assert r.max_change_percent == Decimal("15.0")
        assert r.cooldown_hours == 24

    def test_valid_with_scoping(self):
        r = PricingRuleCreate(
            name="Global Rule",
            rule_type=RuleType.VOLUME_SURGE,
            action=RuleAction.INCREASE_PERCENT,
            action_value=Decimal("10.0"),
            applies_to_all_products=True,
        )
        assert r.applies_to_all_products is True

    def test_valid_with_product_list(self):
        ids = [str(uuid.uuid4()), str(uuid.uuid4())]
        r = PricingRuleCreate(
            name="Multi-Product",
            rule_type=RuleType.COMPETITOR_RELATIVE,
            action=RuleAction.MATCH_COMPETITOR,
            action_value=Decimal("0"),
            applies_to_products=ids,
        )
        assert r.applies_to_products == ids

    def test_valid_with_categories(self):
        r = PricingRuleCreate(
            name="Electronics Rule",
            rule_type=RuleType.SENTIMENT_THRESHOLD,
            action=RuleAction.DECREASE_PERCENT,
            action_value=Decimal("3.0"),
            applies_to_categories=["Electronics", "Audio"],
        )
        assert r.applies_to_categories == ["Electronics", "Audio"]

    def test_valid_competitor_rule(self):
        r = PricingRuleCreate(
            name="Undercut Amazon",
            rule_type=RuleType.COMPETITOR_RELATIVE,
            action=RuleAction.UNDERCUT_COMPETITOR,
            action_value=Decimal("2.0"),
            competitor_id=uuid.uuid4(),
            competitor_margin_percent=Decimal("5.0"),
            price_position="below",
        )
        assert r.price_position == "below"

    def test_valid_time_based_rule(self):
        r = PricingRuleCreate(
            name="Weekend Discount",
            rule_type=RuleType.TIME_BASED,
            action=RuleAction.DECREASE_PERCENT,
            action_value=Decimal("10.0"),
            time_days="sat,sun",
            time_start="09:00",
            time_end="21:00",
        )
        assert r.time_days == "sat,sun"

    def test_valid_viral_rule(self):
        r = PricingRuleCreate(
            name="Viral Surge",
            rule_type=RuleType.VIRAL_DETECTION,
            action=RuleAction.INCREASE_PERCENT,
            action_value=Decimal("8.0"),
            viral_threshold_reach=10000,
            viral_threshold_engagement=500,
            viral_sentiment_min=Decimal("0.3"),
        )
        assert r.viral_threshold_reach == 10000

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            PricingRuleCreate(
                rule_type=RuleType.SENTIMENT_THRESHOLD,
                action=RuleAction.DECREASE_PERCENT,
                action_value=Decimal("5.0"),
            )

    def test_missing_rule_type_raises(self):
        with pytest.raises(ValidationError):
            PricingRuleCreate(
                name="Test",
                action=RuleAction.DECREASE_PERCENT,
                action_value=Decimal("5.0"),
            )

    def test_missing_action_raises(self):
        with pytest.raises(ValidationError):
            PricingRuleCreate(
                name="Test",
                rule_type=RuleType.SENTIMENT_THRESHOLD,
                action_value=Decimal("5.0"),
            )

    def test_missing_action_value_raises(self):
        with pytest.raises(ValidationError):
            PricingRuleCreate(
                name="Test",
                rule_type=RuleType.SENTIMENT_THRESHOLD,
                action=RuleAction.DECREASE_PERCENT,
            )

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            PricingRuleCreate(
                name="x" * 101,
                rule_type=RuleType.SENTIMENT_THRESHOLD,
                action=RuleAction.DECREASE_PERCENT,
                action_value=Decimal("5.0"),
            )

    def test_invalid_rule_type_raises(self):
        with pytest.raises(ValidationError):
            PricingRuleCreate(
                name="Test",
                rule_type="not_a_type",
                action=RuleAction.DECREASE_PERCENT,
                action_value=Decimal("5.0"),
            )

    def test_invalid_action_raises(self):
        with pytest.raises(ValidationError):
            PricingRuleCreate(
                name="Test",
                rule_type=RuleType.SENTIMENT_THRESHOLD,
                action="not_an_action",
                action_value=Decimal("5.0"),
            )

    def test_all_rule_types_accepted(self):
        for rt in RuleType:
            r = PricingRuleCreate(
                name=f"Test {rt.value}",
                rule_type=rt,
                action=RuleAction.INCREASE_PERCENT,
                action_value=Decimal("1.0"),
            )
            assert r.rule_type == rt

    def test_all_actions_accepted(self):
        for action in RuleAction:
            r = PricingRuleCreate(
                name=f"Test {action.value}",
                rule_type=RuleType.SENTIMENT_THRESHOLD,
                action=action,
                action_value=Decimal("1.0"),
            )
            assert r.action == action


# =====================================================================
# PricingRuleUpdate
# =====================================================================

class TestPricingRuleUpdate:

    def test_empty_update(self):
        u = PricingRuleUpdate()
        assert u.name is None
        assert u.action is None
        assert u.is_active is None

    def test_partial_update(self):
        u = PricingRuleUpdate(name="New Name", is_active=False)
        assert u.name == "New Name"
        assert u.is_active is False
        assert u.action is None

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            PricingRuleUpdate(name="x" * 101)

    def test_update_scoping(self):
        u = PricingRuleUpdate(
            applies_to_all_products=True,
            applies_to_categories=["Electronics"],
        )
        assert u.applies_to_all_products is True
        assert u.applies_to_categories == ["Electronics"]

    def test_update_action(self):
        u = PricingRuleUpdate(
            action=RuleAction.SET_ABSOLUTE,
            action_value=Decimal("49.99"),
        )
        assert u.action == RuleAction.SET_ABSOLUTE


# =====================================================================
# PricingRuleResponse
# =====================================================================

class TestPricingRuleResponse:

    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "product_id": None,
            "applies_to_all_products": True,
            "applies_to_products": None,
            "applies_to_categories": None,
            "name": "Sentiment Rule",
            "description": "Drop price on negative sentiment",
            "rule_type": RuleType.SENTIMENT_THRESHOLD,
            "is_active": True,
            "priority": 1,
            "sentiment_threshold": Decimal("-0.3"),
            "sentiment_direction": "below",
            "competitor_id": None,
            "competitor_margin_percent": None,
            "price_position": None,
            "time_days": None,
            "time_start": None,
            "time_end": None,
            "volume_threshold": None,
            "volume_window_hours": None,
            "viral_threshold_reach": None,
            "viral_threshold_engagement": None,
            "viral_sentiment_min": None,
            "action": RuleAction.DECREASE_PERCENT,
            "action_value": Decimal("5.0"),
            "min_price": Decimal("50.00"),
            "max_price": Decimal("150.00"),
            "max_change_percent": Decimal("15.0"),
            "cooldown_hours": 24,
            "last_triggered_at": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }

    def test_valid(self, valid_data):
        r = PricingRuleResponse(**valid_data)
        assert r.name == "Sentiment Rule"
        assert r.rule_type == RuleType.SENTIMENT_THRESHOLD

    def test_missing_id_raises(self, valid_data):
        del valid_data["id"]
        with pytest.raises(ValidationError):
            PricingRuleResponse(**valid_data)

    def test_missing_action_raises(self, valid_data):
        del valid_data["action"]
        with pytest.raises(ValidationError):
            PricingRuleResponse(**valid_data)


# =====================================================================
# PriceRecommendationResponse
# =====================================================================

class TestPriceRecommendationResponse:

    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "product_id": uuid.uuid4(),
            "triggered_rule_id": uuid.uuid4(),
            "current_price": Decimal("99.99"),
            "recommended_price": Decimal("89.99"),
            "change_percent": Decimal("-10.01"),
            "confidence_score": Decimal("0.85"),
            "reasoning": "Competitor price drop detected",
            "factors": {"sentiment": 0.6, "competitor": -0.15},
            "status": RecommendationStatus.PENDING,
            "requires_approval": True,
            "valid_until": datetime.now(timezone.utc) + timedelta(hours=24),
            "reviewed_by": None,
            "reviewed_at": None,
            "rejection_reason": None,
            "applied_at": None,
            "applied_to_platform": None,
            "created_at": datetime.now(timezone.utc),
        }

    def test_valid(self, valid_data):
        r = PriceRecommendationResponse(**valid_data)
        assert r.status == RecommendationStatus.PENDING
        assert r.confidence_score == Decimal("0.85")

    def test_defaults(self):
        """Test that default values work for numeric fields with defaults."""
        r = PriceRecommendationResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            triggered_rule_id=None,
            status=RecommendationStatus.PENDING,
            requires_approval=True,
            valid_until=datetime.now(timezone.utc),
            reviewed_by=None,
            reviewed_at=None,
            rejection_reason=None,
            applied_at=None,
            applied_to_platform=None,
            created_at=datetime.now(timezone.utc),
        )
        assert r.current_price == Decimal("0")
        assert r.recommended_price == Decimal("0")
        assert r.reasoning == ""
        assert r.factors == {}
        assert r.triggered_rule_id is None
        assert r.reviewed_by is None

    def test_all_statuses(self):
        for status in RecommendationStatus:
            r = PriceRecommendationResponse(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                triggered_rule_id=None,
                status=status,
                requires_approval=True,
                valid_until=datetime.now(timezone.utc),
                reviewed_by=None,
                reviewed_at=None,
                rejection_reason=None,
                applied_at=None,
                applied_to_platform=None,
                created_at=datetime.now(timezone.utc),
            )
            assert r.status == status


# =====================================================================
# RecommendationApprove / Reject / ListParams
# =====================================================================

class TestRecommendationApproveReject:

    def test_approve_empty(self):
        a = RecommendationApprove()
        assert a is not None

    def test_reject_without_reason(self):
        r = RecommendationReject()
        assert r.reason is None

    def test_reject_with_reason(self):
        r = RecommendationReject(reason="Price too aggressive")
        assert r.reason == "Price too aggressive"

    def test_reject_reason_max_length(self):
        with pytest.raises(ValidationError):
            RecommendationReject(reason="x" * 501)


class TestRecommendationListParams:

    def test_defaults(self):
        p = RecommendationListParams()
        assert p.status is None
        assert p.product_id is None
        assert p.limit == 20
        assert p.offset == 0

    def test_with_filter(self):
        p = RecommendationListParams(
            status=RecommendationStatus.PENDING,
            product_id=uuid.uuid4(),
            limit=50,
            offset=10,
        )
        assert p.status == RecommendationStatus.PENDING
        assert p.limit == 50

    def test_limit_max(self):
        with pytest.raises(ValidationError):
            RecommendationListParams(limit=101)


# =====================================================================
# PricingSettingsUpdate / Response
# =====================================================================

class TestPricingSettingsUpdate:

    def test_empty_update(self):
        u = PricingSettingsUpdate()
        assert u.auto_approve_enabled is None

    def test_partial_update(self):
        u = PricingSettingsUpdate(
            auto_approve_enabled=True,
            auto_approve_max_increase=Decimal("10.0"),
            notify_on_auto_apply=True,
        )
        assert u.auto_approve_enabled is True
        assert u.auto_approve_max_increase == Decimal("10.0")


class TestPricingSettingsResponse:

    @pytest.fixture
    def valid_data(self):
        return {
            "id": uuid.uuid4(),
            "user_id": uuid.uuid4(),
            "auto_approve_enabled": False,
            "auto_approve_max_increase": Decimal("5.0"),
            "auto_approve_max_decrease": Decimal("10.0"),
            "auto_approve_min_confidence": Decimal("0.8"),
            "min_margin_percent": Decimal("20.0"),
            "max_auto_changes_per_day": 3,
            "global_cooldown_hours": 6,
            "blackout_hours_start": None,
            "blackout_hours_end": None,
            "require_approval_above_price": None,
            "recommendation_valid_hours": 24,
            "notify_on_auto_apply": True,
            "notify_on_pending": True,
            "notification_email": "test@example.com",
            "notification_slack_webhook": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }

    def test_valid(self, valid_data):
        r = PricingSettingsResponse(**valid_data)
        assert r.auto_approve_enabled is False
        assert r.min_margin_percent == Decimal("20.0")

    def test_missing_required_raises(self, valid_data):
        del valid_data["auto_approve_enabled"]
        with pytest.raises(ValidationError):
            PricingSettingsResponse(**valid_data)


# =====================================================================
# MockSignals / RuleTest
# =====================================================================

class TestMockSignals:

    def test_empty(self):
        m = MockSignals()
        assert m.sentiment_score is None
        assert m.competitor_prices is None

    def test_with_values(self):
        m = MockSignals(
            sentiment_score=Decimal("-0.5"),
            mention_count_24h=100,
            viral_detected=True,
            competitor_prices={"amazon": Decimal("74.99")},
        )
        assert m.sentiment_score == Decimal("-0.5")
        assert m.viral_detected is True


class TestRuleTestRequest:

    def test_empty(self):
        r = RuleTestRequest()
        assert r.mock_signals is None

    def test_with_signals(self):
        r = RuleTestRequest(
            mock_signals=MockSignals(sentiment_score=Decimal("0.8"))
        )
        assert r.mock_signals.sentiment_score == Decimal("0.8")


class TestRuleTestResponse:

    def test_valid(self):
        r = RuleTestResponse(
            rule_id=uuid.uuid4(),
            rule_name="Test Rule",
            would_trigger=True,
            signals_used={"sentiment": -0.5},
            calculated_price=Decimal("85.00"),
            change_percent=Decimal("-15.0"),
            reason="Sentiment below threshold",
        )
        assert r.would_trigger is True

    def test_no_trigger(self):
        r = RuleTestResponse(
            rule_id=uuid.uuid4(),
            rule_name="Test Rule",
            would_trigger=False,
            signals_used={"sentiment": 0.2},
        )
        assert r.would_trigger is False
        assert r.calculated_price is None


# =====================================================================
# Simulation
# =====================================================================

class TestSimulationRequest:

    def test_valid(self):
        r = SimulationRequest(product_id=uuid.uuid4())
        assert r.mock_signals is None

    def test_with_signals(self):
        r = SimulationRequest(
            product_id=uuid.uuid4(),
            mock_signals=MockSignals(sentiment_score=Decimal("0.5")),
        )
        assert r.mock_signals is not None


class TestSimulationResponse:

    def test_valid(self):
        r = SimulationResponse(
            product_id=uuid.uuid4(),
            product_name="Headphones",
            current_price=Decimal("99.99"),
            rules_evaluated=5,
            rules_triggered=1,
            triggered_rules=[],
            best_recommendation=None,
        )
        assert r.rules_evaluated == 5
        assert r.best_recommendation is None


# =====================================================================
# OutcomeRecordRequest
# =====================================================================

class TestOutcomeRecordRequest:

    def test_valid(self):
        r = OutcomeRecordRequest(
            sales_count_before=10,
            units_sold_before=10,
            revenue_before=Decimal("999.90"),
            sales_count_after=15,
            units_sold_after=15,
            revenue_after=Decimal("1349.85"),
        )
        assert r.measurement_window_hours == 48

    def test_custom_window(self):
        r = OutcomeRecordRequest(
            sales_count_before=0,
            units_sold_before=0,
            revenue_before=Decimal("0"),
            sales_count_after=5,
            units_sold_after=5,
            revenue_after=Decimal("500"),
            measurement_window_hours=72,
        )
        assert r.measurement_window_hours == 72

    def test_negative_sales_raises(self):
        with pytest.raises(ValidationError):
            OutcomeRecordRequest(
                sales_count_before=-1,
                units_sold_before=0,
                revenue_before=Decimal("0"),
                sales_count_after=0,
                units_sold_after=0,
                revenue_after=Decimal("0"),
            )

    def test_negative_revenue_raises(self):
        with pytest.raises(ValidationError):
            OutcomeRecordRequest(
                sales_count_before=0,
                units_sold_before=0,
                revenue_before=Decimal("-100"),
                sales_count_after=0,
                units_sold_after=0,
                revenue_after=Decimal("0"),
            )

    def test_window_min(self):
        with pytest.raises(ValidationError):
            OutcomeRecordRequest(
                sales_count_before=0,
                units_sold_before=0,
                revenue_before=Decimal("0"),
                sales_count_after=0,
                units_sold_after=0,
                revenue_after=Decimal("0"),
                measurement_window_hours=0,
            )

    def test_window_max(self):
        with pytest.raises(ValidationError):
            OutcomeRecordRequest(
                sales_count_before=0,
                units_sold_before=0,
                revenue_before=Decimal("0"),
                sales_count_after=0,
                units_sold_after=0,
                revenue_after=Decimal("0"),
                measurement_window_hours=169,
            )


# =====================================================================
# OutcomeResponse
# =====================================================================

class TestOutcomeResponse:

    def test_valid(self):
        r = OutcomeResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            recommendation_id=uuid.uuid4(),
            product_id=uuid.uuid4(),
            rule_id=None,
            rule_type=None,
            price_before=Decimal("99.99"),
            price_after=Decimal("89.99"),
            price_change_percent=Decimal("-10.01"),
            sales_count_before=10,
            units_sold_before=10,
            revenue_before=Decimal("999.90"),
            sales_count_after=15,
            units_sold_after=15,
            revenue_after=Decimal("1349.85"),
            revenue_change=Decimal("349.95"),
            revenue_change_percent=Decimal("35.0"),
            units_change=5,
            units_change_percent=Decimal("50.0"),
            outcome_score=Decimal("0.85"),
            outcome_label=OutcomeLabel.POSITIVE,
            original_confidence=Decimal("0.8"),
            price_applied_at=datetime.now(timezone.utc),
            measurement_window_hours=48,
            measured_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        assert r.outcome_label == OutcomeLabel.POSITIVE

    def test_all_outcome_labels(self):
        for label in OutcomeLabel:
            r = OutcomeResponse(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                recommendation_id=uuid.uuid4(),
                product_id=uuid.uuid4(),
                rule_id=None,
                rule_type=None,
                price_before=Decimal("100"),
                price_after=Decimal("90"),
                price_change_percent=Decimal("-10"),
                sales_count_before=0,
                units_sold_before=0,
                revenue_before=Decimal("0"),
                sales_count_after=0,
                units_sold_after=0,
                revenue_after=Decimal("0"),
                revenue_change=Decimal("0"),
                revenue_change_percent=None,
                units_change=0,
                units_change_percent=None,
                outcome_score=Decimal("0"),
                outcome_label=label,
                original_confidence=Decimal("0.5"),
                price_applied_at=datetime.now(timezone.utc),
                measurement_window_hours=48,
                measured_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
            )
            assert r.outcome_label == label


# =====================================================================
# RulePerformanceResponse / AccuracyStatsResponse
# =====================================================================

class TestRulePerformanceResponse:

    def test_valid(self):
        r = RulePerformanceResponse(
            rule_id=uuid.uuid4(),
            rule_name="Sentiment Rule",
            rule_type="sentiment_threshold",
            total_outcomes=20,
            positive_outcomes=15,
            negative_outcomes=3,
            neutral_outcomes=2,
            success_rate=Decimal("0.75"),
            avg_outcome_score=Decimal("0.65"),
            avg_revenue_change_percent=Decimal("12.5"),
            total_revenue_impact=Decimal("5000.00"),
            avg_confidence=Decimal("0.82"),
            confidence_accuracy_correlation=Decimal("0.7"),
        )
        assert r.success_rate == Decimal("0.75")


class TestAccuracyStatsResponse:

    def test_valid(self):
        r = AccuracyStatsResponse(
            period_days=30,
            total_outcomes=50,
            positive_count=30,
            negative_count=10,
            neutral_count=5,
            inconclusive_count=5,
            overall_success_rate=Decimal("0.60"),
            avg_outcome_score=Decimal("0.55"),
            total_revenue_impact=Decimal("15000.00"),
            avg_revenue_change_percent=Decimal("8.5"),
            by_rule_type={"sentiment_threshold": {"count": 20, "success_rate": 0.7}},
            top_performing_rules=[],
            worst_performing_rules=[],
        )
        assert r.period_days == 30
        assert r.positive_count == 30


        