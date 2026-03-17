"""Tests for services/ai_trend_analysis/schemas.py"""

from datetime import UTC, datetime
from decimal import Decimal

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

# ════════════════════════════════════════
# ENUMS
# ════════════════════════════════════════


class TestTrendDirection:
    def test_values(self):
        assert TrendDirection.RISING == "rising"
        assert TrendDirection.FALLING == "falling"
        assert TrendDirection.STABLE == "stable"
        assert TrendDirection.VOLATILE == "volatile"

    def test_from_string(self):
        assert TrendDirection("rising") == TrendDirection.RISING

    def test_all_members(self):
        assert len(TrendDirection) == 4


class TestTrendCategory:
    def test_values(self):
        assert TrendCategory.VIRAL_POSITIVE == "viral_positive"
        assert TrendCategory.COMPETITOR_LAUNCH == "competitor_launch"
        assert TrendCategory.MARKET_SHIFT == "market_shift"

    def test_all_members(self):
        assert len(TrendCategory) == 8


class TestOpportunityType:
    def test_values(self):
        assert OpportunityType.PRICE_INCREASE == "price_increase"
        assert OpportunityType.PROMOTIONAL == "promotional"
        assert OpportunityType.PREMIUM_POSITIONING == "premium_positioning"

    def test_all_members(self):
        assert len(OpportunityType) == 5


class TestRiskLevel:
    def test_values(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.CRITICAL == "critical"

    def test_all_members(self):
        assert len(RiskLevel) == 4


class TestConfidenceLevel:
    def test_values(self):
        assert ConfidenceLevel.VERY_HIGH == "very_high"

    def test_all_members(self):
        assert len(ConfidenceLevel) == 4


# ════════════════════════════════════════
# DATACLASSES
# ════════════════════════════════════════

NOW = datetime.now(UTC)


class TestTrendSignal:
    def test_creation(self):
        signal = TrendSignal(
            signal_type="sentiment_spike",
            value=0.85,
            timestamp=NOW,
            source="sentiment",
            description="Strong positive sentiment detected",
        )
        assert signal.signal_type == "sentiment_spike"
        assert signal.value == 0.85
        assert signal.source == "sentiment"


class TestTrendPrediction:
    def test_creation_with_defaults(self):
        pred = TrendPrediction(
            direction=TrendDirection.RISING,
            category=TrendCategory.ORGANIC_GROWTH,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=85.0,
            predicted_change=12.5,
            timeframe_days=7,
            reasoning="Strong upward trend",
        )
        assert pred.direction == TrendDirection.RISING
        assert pred.supporting_signals == []
        assert pred.created_at is not None

    def test_creation_with_signals(self):
        signal = TrendSignal("spike", 0.9, NOW, "volume", "Volume spike")
        pred = TrendPrediction(
            direction=TrendDirection.RISING,
            category=TrendCategory.VIRAL_POSITIVE,
            confidence=ConfidenceLevel.VERY_HIGH,
            confidence_score=95.0,
            predicted_change=20.0,
            timeframe_days=3,
            reasoning="Viral growth",
            supporting_signals=[signal],
        )
        assert len(pred.supporting_signals) == 1


class TestPricingOpportunity:
    def test_creation(self):
        opp = PricingOpportunity(
            opportunity_type=OpportunityType.PRICE_INCREASE,
            product_id="prod-1",
            product_name="Test Product",
            current_price=Decimal("29.99"),
            suggested_price=Decimal("34.99"),
            expected_impact="+12% revenue",
            confidence=ConfidenceLevel.HIGH,
            confidence_score=88.0,
            reasoning="Positive sentiment supports increase",
            valid_until=NOW,
        )
        assert opp.current_price == Decimal("29.99")
        assert opp.suggested_price == Decimal("34.99")
        assert opp.triggers == []


class TestRiskAlert:
    def test_creation(self):
        risk = RiskAlert(
            risk_level=RiskLevel.HIGH,
            risk_type="competitor_undercut",
            title="Competitor Price Drop",
            description="Major competitor dropped prices 15%",
            affected_products=["prod-1", "prod-2"],
            recommended_actions=["Review pricing", "Monitor sales"],
            detected_at=NOW,
        )
        assert risk.risk_level == RiskLevel.HIGH
        assert len(risk.affected_products) == 2
        assert risk.expires_at is None

    def test_with_expiry(self):
        risk = RiskAlert(
            risk_level=RiskLevel.MEDIUM,
            risk_type="seasonal",
            title="Seasonal Risk",
            description="Holiday season ending",
            affected_products=["prod-1"],
            recommended_actions=["Reduce inventory"],
            detected_at=NOW,
            expires_at=NOW,
        )
        assert risk.expires_at is not None


class TestAIInsight:
    def test_creation(self):
        insight = AIInsight(
            title="Market Shift Detected",
            summary="Consumer preferences changing",
            detailed_analysis="Long form analysis here",
            key_factors=["social media", "competitor moves"],
            data_points_analyzed=1500,
            generated_at=NOW,
            model_used="gemini",
        )
        assert insight.data_points_analyzed == 1500
        assert insight.model_used == "gemini"


# ════════════════════════════════════════
# TrendAnalysisResult + to_dict()
# ════════════════════════════════════════


class TestTrendAnalysisResult:
    @pytest.fixture
    def full_result(self):
        signal = TrendSignal("spike", 0.9, NOW, "sentiment", "Spike detected")
        prediction = TrendPrediction(
            direction=TrendDirection.RISING,
            category=TrendCategory.ORGANIC_GROWTH,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=85.0,
            predicted_change=10.0,
            timeframe_days=7,
            reasoning="Upward trend",
            supporting_signals=[signal],
        )
        opportunity = PricingOpportunity(
            opportunity_type=OpportunityType.PRICE_INCREASE,
            product_id="prod-1",
            product_name="Widget",
            current_price=Decimal("19.99"),
            suggested_price=Decimal("22.99"),
            expected_impact="+15% revenue",
            confidence=ConfidenceLevel.HIGH,
            confidence_score=82.0,
            reasoning="Sentiment supports increase",
            valid_until=NOW,
            triggers=["sentiment_above_0.8"],
        )
        risk = RiskAlert(
            risk_level=RiskLevel.MEDIUM,
            risk_type="competitor_launch",
            title="New Competitor",
            description="New entrant detected",
            affected_products=["prod-1"],
            recommended_actions=["Monitor pricing"],
            detected_at=NOW,
        )
        insight = AIInsight(
            title="Growth Opportunity",
            summary="Market expanding",
            detailed_analysis="Detailed text",
            key_factors=["demand", "sentiment"],
            data_points_analyzed=500,
            generated_at=NOW,
            model_used="openai",
        )
        return TrendAnalysisResult(
            user_id="user-1",
            analysis_id="analysis-1",
            generated_at=NOW,
            market_sentiment=TrendDirection.RISING,
            market_sentiment_score=72.5,
            predictions=[prediction],
            opportunities=[opportunity],
            risks=[risk],
            insights=[insight],
            executive_summary="Market is trending up",
            recommended_actions=["Increase prices", "Expand inventory"],
            products_analyzed=10,
            mentions_analyzed=250,
            time_range_days=30,
        )

    def test_creation(self, full_result):
        assert full_result.user_id == "user-1"
        assert full_result.market_sentiment == TrendDirection.RISING
        assert len(full_result.predictions) == 1
        assert len(full_result.opportunities) == 1
        assert len(full_result.risks) == 1
        assert len(full_result.insights) == 1

    def test_to_dict_top_level(self, full_result):
        d = full_result.to_dict()
        assert d["user_id"] == "user-1"
        assert d["analysis_id"] == "analysis-1"
        assert d["market_sentiment"] == "rising"
        assert d["market_sentiment_score"] == 72.5
        assert d["executive_summary"] == "Market is trending up"
        assert d["products_analyzed"] == 10
        assert d["mentions_analyzed"] == 250
        assert d["time_range_days"] == 30

    def test_to_dict_predictions(self, full_result):
        d = full_result.to_dict()
        pred = d["predictions"][0]
        assert pred["direction"] == "rising"
        assert pred["category"] == "organic_growth"
        assert pred["confidence"] == "high"
        assert pred["confidence_score"] == 85.0
        assert len(pred["supporting_signals"]) == 1
        assert pred["supporting_signals"][0]["source"] == "sentiment"

    def test_to_dict_opportunities(self, full_result):
        d = full_result.to_dict()
        opp = d["opportunities"][0]
        assert opp["opportunity_type"] == "price_increase"
        assert opp["current_price"] == "19.99"
        assert opp["suggested_price"] == "22.99"
        assert opp["triggers"] == ["sentiment_above_0.8"]

    def test_to_dict_risks(self, full_result):
        d = full_result.to_dict()
        risk = d["risks"][0]
        assert risk["risk_level"] == "medium"
        assert risk["risk_type"] == "competitor_launch"
        assert risk["expires_at"] is None

    def test_to_dict_insights(self, full_result):
        d = full_result.to_dict()
        insight = d["insights"][0]
        assert insight["title"] == "Growth Opportunity"
        assert insight["model_used"] == "openai"
        assert insight["data_points_analyzed"] == 500

    def test_to_dict_datetimes_are_iso(self, full_result):
        d = full_result.to_dict()
        assert "T" in d["generated_at"]
        assert "T" in d["predictions"][0]["supporting_signals"][0]["timestamp"]
        assert "T" in d["opportunities"][0]["valid_until"]
        assert "T" in d["risks"][0]["detected_at"]
        assert "T" in d["insights"][0]["generated_at"]
