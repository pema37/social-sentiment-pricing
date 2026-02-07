"""
Test Suite: Autonomous Pipeline Schemas
========================================
Validates Pydantic schemas that enforce typed agent-to-agent communication.

These schemas are the "contracts" between Scout → Analyst → Strategist.
If a schema breaks, the entire pipeline breaks. Test them first.

Run: pytest backend/tests/test_autonomous_schemas.py -v
"""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.services.ai_trend_analysis.autonomous_orchestrator import (
    AgentPhase,
    AgentStreamEvent,
    MarketAssessment,
    MarketSignal,
    PricingDecision,
)


# ---------------------------------------------------------------------------
# MarketSignal (Scout Agent Output)
# ---------------------------------------------------------------------------

class TestMarketSignal:
    """Scout Agent output schema — must be rock-solid for downstream agents."""

    def test_valid_signal_creates_successfully(self, sample_data):
        signal = MarketSignal(**sample_data.market_signal())
        assert signal.competitor_name == "TestCompetitor"
        assert signal.competitor_price == 84.99
        assert signal.price_change_pct == -15.1
        assert signal.signal_type == "price_drop"

    def test_confidence_must_be_between_0_and_1(self):
        with pytest.raises(ValidationError) as exc_info:
            MarketSignal(
                competitor_name="X",
                competitor_price=50.0,
                price_change_pct=-5.0,
                signal_type="price_drop",
                product_category="test",
                source="test",
                confidence=1.5,  # Invalid: > 1.0
            )
        assert "less than or equal to 1" in str(exc_info.value).lower() or "le" in str(exc_info.value).lower()

    def test_confidence_cannot_be_negative(self):
        with pytest.raises(ValidationError):
            MarketSignal(
                competitor_name="X",
                competitor_price=50.0,
                price_change_pct=-5.0,
                signal_type="price_drop",
                product_category="test",
                source="test",
                confidence=-0.1,
            )

    def test_timestamp_auto_generated(self):
        signal = MarketSignal(
            competitor_name="X",
            competitor_price=50.0,
            price_change_pct=0.0,
            signal_type="stable",
            product_category="test",
            source="api",
            confidence=0.5,
        )
        assert signal.timestamp is not None
        # Should be parseable as ISO format
        datetime.fromisoformat(signal.timestamp)

    def test_serializes_to_valid_json(self, sample_data):
        signal = MarketSignal(**sample_data.market_signal())
        json_str = signal.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["competitor_name"] == "TestCompetitor"
        assert isinstance(parsed["raw_data"], dict)

    def test_raw_data_defaults_to_empty_dict(self):
        signal = MarketSignal(
            competitor_name="X",
            competitor_price=50.0,
            price_change_pct=0.0,
            signal_type="stable",
            product_category="test",
            source="api",
            confidence=0.5,
        )
        assert signal.raw_data == {}

    def test_negative_price_change_indicates_drop(self, sample_data):
        signal = MarketSignal(**sample_data.market_signal({"price_change_pct": -20.0}))
        assert signal.price_change_pct < 0
        assert signal.signal_type == "price_drop"

    def test_positive_price_change_allowed(self, sample_data):
        signal = MarketSignal(
            **sample_data.market_signal({"price_change_pct": 10.0, "signal_type": "price_increase"})
        )
        assert signal.price_change_pct > 0


# ---------------------------------------------------------------------------
# MarketAssessment (Analyst Agent Output)
# ---------------------------------------------------------------------------

class TestMarketAssessment:
    """Analyst Agent output — feeds directly into Strategist decisions."""

    def test_valid_assessment_creates_successfully(self, sample_data):
        assessment = MarketAssessment(**sample_data.market_assessment())
        assert assessment.sentiment_score == -0.42
        assert assessment.sentiment_label == "bearish"
        assert assessment.recommended_direction == "decrease"

    def test_sentiment_score_bounded_negative_1_to_1(self):
        with pytest.raises(ValidationError):
            MarketAssessment(
                sentiment_score=-1.5,  # Invalid: < -1.0
                sentiment_label="bearish",
                demand_elasticity=-1.0,
                risk_level="high",
                opportunity_score=0.5,
                market_context="test",
                recommended_direction="decrease",
                max_safe_change_pct=10.0,
            )

    def test_sentiment_score_upper_bound(self):
        with pytest.raises(ValidationError):
            MarketAssessment(
                sentiment_score=1.5,  # Invalid: > 1.0
                sentiment_label="bullish",
                demand_elasticity=-1.0,
                risk_level="low",
                opportunity_score=0.5,
                market_context="test",
                recommended_direction="increase",
                max_safe_change_pct=5.0,
            )

    def test_opportunity_score_bounded_0_to_1(self):
        with pytest.raises(ValidationError):
            MarketAssessment(
                sentiment_score=0.0,
                sentiment_label="neutral",
                demand_elasticity=-1.0,
                risk_level="low",
                opportunity_score=2.0,  # Invalid
                market_context="test",
                recommended_direction="hold",
                max_safe_change_pct=0.0,
            )

    def test_risk_factors_default_to_empty_list(self):
        assessment = MarketAssessment(
            sentiment_score=0.0,
            sentiment_label="neutral",
            demand_elasticity=-1.0,
            risk_level="low",
            opportunity_score=0.5,
            market_context="test",
            recommended_direction="hold",
            max_safe_change_pct=0.0,
        )
        assert assessment.risk_factors == []

    def test_direction_values_accepted(self, sample_data):
        for direction in ["increase", "decrease", "hold"]:
            assessment = MarketAssessment(
                **sample_data.market_assessment({"recommended_direction": direction})
            )
            assert assessment.recommended_direction == direction

    def test_serialization_roundtrip(self, sample_data):
        """Schema must survive JSON serialization for agent-to-agent handoff."""
        original = MarketAssessment(**sample_data.market_assessment())
        json_str = original.model_dump_json()
        restored = MarketAssessment.model_validate_json(json_str)
        assert original.sentiment_score == restored.sentiment_score
        assert original.risk_factors == restored.risk_factors
        assert original.recommended_direction == restored.recommended_direction


# ---------------------------------------------------------------------------
# PricingDecision (Strategist Agent Output)
# ---------------------------------------------------------------------------

class TestPricingDecision:
    """Strategist output — the final autonomous action."""

    def test_valid_decision_creates_successfully(self, sample_data):
        decision = PricingDecision(**sample_data.pricing_decision())
        assert decision.recommended_price == 87.99
        assert decision.action == "execute"
        assert decision.tx_hash is not None

    def test_confidence_score_bounded(self):
        with pytest.raises(ValidationError):
            PricingDecision(
                recommended_price=87.99,
                current_price=99.99,
                change_pct=-12.0,
                confidence_score=1.5,  # Invalid
                reasoning="test",
                action="execute",
                risk_acknowledgment="test",
                expected_revenue_impact="test",
            )

    def test_tx_hash_optional_for_hold_actions(self):
        decision = PricingDecision(
            recommended_price=99.99,
            current_price=99.99,
            change_pct=0.0,
            confidence_score=0.5,
            reasoning="Insufficient confidence to act",
            action="hold",
            risk_acknowledgment="Low confidence",
            expected_revenue_impact="No change",
            tx_hash=None,
            executed_at=None,
        )
        assert decision.action == "hold"
        assert decision.tx_hash is None

    def test_executed_at_optional(self, sample_data):
        data = sample_data.pricing_decision({"executed_at": None})
        decision = PricingDecision(**data)
        assert decision.executed_at is None

    def test_negative_change_pct_for_price_drops(self, sample_data):
        decision = PricingDecision(**sample_data.pricing_decision())
        assert decision.change_pct < 0
        assert decision.recommended_price < decision.current_price


# ---------------------------------------------------------------------------
# AgentStreamEvent (SSE Wire Format)
# ---------------------------------------------------------------------------

class TestAgentStreamEvent:
    """SSE event schema — must serialize correctly for EventSource clients."""

    def test_creates_with_auto_timestamp(self):
        event = AgentStreamEvent(
            agent="scout",
            phase="starting",
            content="Scanning...",
        )
        assert event.timestamp is not None
        assert event.is_complete is False

    def test_json_serialization_for_sse(self):
        event = AgentStreamEvent(
            agent="strategist",
            phase="complete",
            content='{"price": 87.99}',
            is_complete=True,
        )
        json_str = event.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["agent"] == "strategist"
        assert parsed["is_complete"] is True

    def test_optional_data_field(self):
        event = AgentStreamEvent(
            agent="execution",
            phase="complete",
            content="Done",
            data={"tx_hash": "0xabc123"},
        )
        assert event.data["tx_hash"] == "0xabc123"


# ---------------------------------------------------------------------------
# AgentPhase Enum
# ---------------------------------------------------------------------------

class TestAgentPhase:
    """Enum for pipeline phase tracking."""

    def test_all_phases_defined(self):
        assert AgentPhase.SCOUT == "scout"
        assert AgentPhase.ANALYST == "analyst"
        assert AgentPhase.STRATEGIST == "strategist"
        assert AgentPhase.EXECUTION == "execution"

    def test_string_comparison(self):
        assert AgentPhase.SCOUT == "scout"
        assert AgentPhase.STRATEGIST != "analyst"



        