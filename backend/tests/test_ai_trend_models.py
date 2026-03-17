# backend/tests/test_ai_trend_models.py
"""
Tests for ai_trend_analysis/models.py — enums, dataclasses,
and TrendAnalysisResult.to_dict() serialization.

Total: ~25 tests
"""

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

for mod in ["db.session"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from services.ai_trend_analysis.schemas import (
    AIInsight,
    ConfidenceLevel,
    OpportunityType,
    PricingOpportunity,
    RiskAlert,
    RiskLevel,
    TrendAnalysisResult,
    TrendCategory,
    TrendDirection,
    TrendPrediction,
    TrendSignal,
)

# ============================================================
# 1. Enums
# ============================================================


class TestTrendDirection:
    def test_values(self):
        assert TrendDirection.RISING == "rising"
        assert TrendDirection.FALLING == "falling"
        assert TrendDirection.STABLE == "stable"
        assert TrendDirection.VOLATILE == "volatile"

    def test_is_str_enum(self):
        assert isinstance(TrendDirection.RISING, str)


class TestTrendCategory:
    def test_values(self):
        assert TrendCategory.VIRAL_POSITIVE == "viral_positive"
        assert TrendCategory.COMPETITOR_LAUNCH == "competitor_launch"
        assert TrendCategory.ORGANIC_GROWTH == "organic_growth"
        assert len(TrendCategory) == 8


class TestOpportunityType:
    def test_values(self):
        assert OpportunityType.PRICE_INCREASE == "price_increase"
        assert OpportunityType.HOLD == "hold"
        assert len(OpportunityType) == 5


class TestRiskLevel:
    def test_values(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.CRITICAL == "critical"
        assert len(RiskLevel) == 4


class TestConfidenceLevel:
    def test_values(self):
        assert ConfidenceLevel.LOW == "low"
        assert ConfidenceLevel.VERY_HIGH == "very_high"
        assert len(ConfidenceLevel) == 4


# ============================================================
# 2. Dataclasses
# ============================================================


class TestTrendSignal:
    def test_creation(self):
        now = datetime.now(UTC)
        s = TrendSignal(
            signal_type="volume_spike",
            value=2.5,
            timestamp=now,
            source="sentiment",
            description="Double volume",
        )
        assert s.signal_type == "volume_spike"
        assert s.value == 2.5
        assert s.source == "sentiment"


class TestTrendPrediction:
    def test_defaults(self):
        p = TrendPrediction(
            direction=TrendDirection.RISING,
            category=TrendCategory.VIRAL_POSITIVE,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=80,
            predicted_change=15.0,
            timeframe_days=7,
            reasoning="test",
        )
        assert p.supporting_signals == []
        assert isinstance(p.created_at, datetime)


class TestPricingOpportunity:
    def test_creation(self):
        o = PricingOpportunity(
            opportunity_type=OpportunityType.PRICE_INCREASE,
            product_id="p1",
            product_name="Widget",
            current_price=Decimal("50"),
            suggested_price=Decimal("55"),
            expected_impact="+10%",
            confidence=ConfidenceLevel.HIGH,
            confidence_score=75,
            reasoning="demand",
            valid_until=datetime.now(UTC),
        )
        assert o.triggers == []
        assert o.product_name == "Widget"


class TestRiskAlert:
    def test_creation(self):
        now = datetime.now(UTC)
        r = RiskAlert(
            risk_level=RiskLevel.HIGH,
            risk_type="price_war",
            title="Alert",
            description="desc",
            affected_products=["p1"],
            recommended_actions=["act"],
            detected_at=now,
        )
        assert r.expires_at is None
        assert r.risk_level == RiskLevel.HIGH


class TestAIInsight:
    def test_creation(self):
        i = AIInsight(
            title="Insight",
            summary="sum",
            detailed_analysis="detail",
            key_factors=["f1"],
            data_points_analyzed=100,
            generated_at=datetime.now(UTC),
            model_used="gemini-2.0",
        )
        assert i.model_used == "gemini-2.0"


# ============================================================
# 3. TrendAnalysisResult + to_dict
# ============================================================


class TestTrendAnalysisResult:
    @pytest.fixture
    def sample_result(self):
        now = datetime.now(UTC)
        signal = TrendSignal("vol", 1.5, now, "sentiment", "spike")
        prediction = TrendPrediction(
            direction=TrendDirection.RISING,
            category=TrendCategory.VIRAL_POSITIVE,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=80,
            predicted_change=10.0,
            timeframe_days=7,
            reasoning="test",
            supporting_signals=[signal],
        )
        opportunity = PricingOpportunity(
            opportunity_type=OpportunityType.PRICE_INCREASE,
            product_id="p1",
            product_name="Widget",
            current_price=Decimal("50"),
            suggested_price=Decimal("55"),
            expected_impact="+10%",
            confidence=ConfidenceLevel.HIGH,
            confidence_score=75,
            reasoning="demand",
            valid_until=now + timedelta(days=7),
            triggers=["viral"],
        )
        risk = RiskAlert(
            risk_level=RiskLevel.MEDIUM,
            risk_type="competitor",
            title="Risk",
            description="desc",
            affected_products=["p1"],
            recommended_actions=["watch"],
            detected_at=now,
            expires_at=now + timedelta(hours=24),
        )
        insight = AIInsight(
            title="Insight",
            summary="sum",
            detailed_analysis="detail",
            key_factors=["f1"],
            data_points_analyzed=100,
            generated_at=now,
            model_used="gemini-2.0",
        )
        return TrendAnalysisResult(
            user_id="u1",
            analysis_id="a1",
            generated_at=now,
            market_sentiment=TrendDirection.RISING,
            market_sentiment_score=75.0,
            predictions=[prediction],
            opportunities=[opportunity],
            risks=[risk],
            insights=[insight],
            executive_summary="Summary",
            recommended_actions=["Act 1"],
            products_analyzed=5,
            mentions_analyzed=1000,
            time_range_days=30,
        )

    def test_to_dict_top_level_keys(self, sample_result):
        d = sample_result.to_dict()
        assert d["user_id"] == "u1"
        assert d["analysis_id"] == "a1"
        assert d["market_sentiment"] == "rising"
        assert d["market_sentiment_score"] == 75.0
        assert d["products_analyzed"] == 5
        assert d["time_range_days"] == 30

    def test_to_dict_predictions(self, sample_result):
        d = sample_result.to_dict()
        preds = d["predictions"]
        assert len(preds) == 1
        assert preds[0]["direction"] == "rising"
        assert preds[0]["category"] == "viral_positive"
        assert preds[0]["confidence"] == "high"
        assert len(preds[0]["supporting_signals"]) == 1

    def test_to_dict_opportunities(self, sample_result):
        d = sample_result.to_dict()
        opps = d["opportunities"]
        assert len(opps) == 1
        assert opps[0]["current_price"] == "50"
        assert opps[0]["suggested_price"] == "55"
        assert opps[0]["triggers"] == ["viral"]

    def test_to_dict_risks(self, sample_result):
        d = sample_result.to_dict()
        risks = d["risks"]
        assert len(risks) == 1
        assert risks[0]["risk_level"] == "medium"
        assert risks[0]["expires_at"] is not None

    def test_to_dict_risk_no_expiry(self, sample_result):
        sample_result.risks[0].expires_at = None
        d = sample_result.to_dict()
        assert d["risks"][0]["expires_at"] is None

    def test_to_dict_insights(self, sample_result):
        d = sample_result.to_dict()
        ins = d["insights"]
        assert len(ins) == 1
        assert ins[0]["model_used"] == "gemini-2.0"
        assert ins[0]["data_points_analyzed"] == 100

    def test_to_dict_empty_lists(self):
        now = datetime.now(UTC)
        r = TrendAnalysisResult(
            user_id="u1",
            analysis_id="a1",
            generated_at=now,
            market_sentiment=TrendDirection.STABLE,
            market_sentiment_score=0,
            predictions=[],
            opportunities=[],
            risks=[],
            insights=[],
            executive_summary="",
            recommended_actions=[],
            products_analyzed=0,
            mentions_analyzed=0,
            time_range_days=7,
        )
        d = r.to_dict()
        assert d["predictions"] == []
        assert d["opportunities"] == []
        assert d["risks"] == []
        assert d["insights"] == []
