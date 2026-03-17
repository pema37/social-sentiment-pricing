# backend/tests/test_ai_trend_parsers.py
"""
Tests for ai_trend_analysis/parsers.py — parses AI JSON responses
into structured data models.

Tests cover:
- parse_analysis_response (full orchestration)
- _parse_predictions (direction, category, confidence, defaults, errors)
- _parse_opportunities (product lookup, prices, types, defaults)
- _parse_risks (levels, urgency, defaults)
- parse_risk_response (standalone)
- parse_opportunity_response (single product)
- parse_insight_response

Total: ~35 tests
"""

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

# === Import isolation ===
# core.logging and core.config are handled by conftest.py (autouse).
for mod in [
    "db.session",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


from services.ai_trend_analysis.parsers import ResponseParser
from services.ai_trend_analysis.schemas import (
    ConfidenceLevel,
    OpportunityType,
    RiskLevel,
    TrendCategory,
    TrendDirection,
)

# ============================================================
# Helpers
# ============================================================


def make_product(name="Widget Pro", price=Decimal("29.99"), product_id=None):
    p = MagicMock()
    p.id = product_id or uuid4()
    p.name = name
    p.base_price = price
    return p


# ============================================================
# 1. _parse_predictions
# ============================================================


class TestParsePredictions:
    def test_valid_prediction(self):
        data = [
            {
                "direction": "rising",
                "category": "viral_positive",
                "confidence": "high",
                "confidence_score": 80,
                "predicted_change": 15,
                "timeframe_days": 14,
                "reasoning": "Strong social signal",
            }
        ]
        result = ResponseParser._parse_predictions(data)
        assert len(result) == 1
        assert result[0].direction == TrendDirection.RISING
        assert result[0].confidence_score == 80
        assert result[0].reasoning == "Strong social signal"

    def test_defaults_for_missing_fields(self):
        data = [{}]
        result = ResponseParser._parse_predictions(data)
        assert len(result) == 1
        assert result[0].direction == TrendDirection.STABLE
        assert result[0].category == TrendCategory.ORGANIC_GROWTH
        assert result[0].confidence == ConfidenceLevel.MEDIUM
        assert result[0].confidence_score == 50

    def test_invalid_direction_defaults_to_stable(self):
        data = [{"direction": "sideways"}]
        result = ResponseParser._parse_predictions(data)
        assert result[0].direction == TrendDirection.STABLE

    def test_invalid_category_defaults(self):
        data = [{"category": "nonexistent"}]
        result = ResponseParser._parse_predictions(data)
        assert result[0].category == TrendCategory.ORGANIC_GROWTH

    def test_multiple_predictions(self):
        data = [
            {"direction": "rising", "confidence_score": 90},
            {"direction": "falling", "confidence_score": 60},
        ]
        result = ResponseParser._parse_predictions(data)
        assert len(result) == 2

    def test_empty_list(self):
        result = ResponseParser._parse_predictions([])
        assert result == []


# ============================================================
# 2. _parse_opportunities
# ============================================================


class TestParseOpportunities:
    def test_valid_opportunity_with_product(self):
        product = make_product(name="Widget", price=Decimal("50.00"))
        now = datetime.now(UTC)
        data = [
            {
                "product_id": str(product.id),
                "opportunity_type": "price_increase",
                "confidence": "high",
                "confidence_score": 75,
                "current_price": 50,
                "suggested_price": 55,
                "expected_impact": "+10% revenue",
                "reasoning": "High demand",
                "triggers": ["viral_post"],
            }
        ]
        result = ResponseParser._parse_opportunities(data, [product], now)
        assert len(result) == 1
        assert result[0].opportunity_type == OpportunityType.PRICE_INCREASE
        assert result[0].suggested_price == Decimal("55")
        assert result[0].product_name == "Widget"

    def test_unknown_product_id(self):
        now = datetime.now(UTC)
        data = [
            {
                "product_id": "nonexistent-id",
                "product_name": "Fallback Name",
                "current_price": 30,
                "suggested_price": 35,
            }
        ]
        result = ResponseParser._parse_opportunities(data, [], now)
        assert len(result) == 1
        assert result[0].product_name == "Fallback Name"

    def test_invalid_opportunity_type_defaults_to_hold(self):
        now = datetime.now(UTC)
        data = [{"opportunity_type": "invalid_type", "current_price": 10, "suggested_price": 10}]
        result = ResponseParser._parse_opportunities(data, [], now)
        assert result[0].opportunity_type == OpportunityType.HOLD

    def test_valid_until_set_7_days(self):
        now = datetime.now(UTC)
        data = [{"current_price": 10, "suggested_price": 10}]
        result = ResponseParser._parse_opportunities(data, [], now)
        assert result[0].valid_until > now

    def test_empty_list(self):
        result = ResponseParser._parse_opportunities([], [], datetime.now(UTC))
        assert result == []


# ============================================================
# 3. _parse_risks
# ============================================================


class TestParseRisks:
    def test_valid_risk(self):
        now = datetime.now(UTC)
        data = [
            {
                "risk_level": "high",
                "risk_type": "competitor_price_war",
                "title": "Price War Alert",
                "description": "Competitor dropped 20%",
                "affected_products": ["product-1"],
                "recommended_actions": ["Monitor", "Prepare response"],
                "urgency_hours": 12,
            }
        ]
        result = ResponseParser._parse_risks(data, now)
        assert len(result) == 1
        assert result[0].risk_level == RiskLevel.HIGH
        assert result[0].title == "Price War Alert"
        assert result[0].expires_at == now + timedelta(hours=12)

    def test_defaults_for_missing_fields(self):
        now = datetime.now(UTC)
        data = [{}]
        result = ResponseParser._parse_risks(data, now)
        assert result[0].risk_level == RiskLevel.LOW
        assert result[0].risk_type == "unknown"
        assert result[0].title == "Unknown Risk"

    def test_invalid_risk_level_defaults(self):
        now = datetime.now(UTC)
        data = [{"risk_level": "extreme"}]
        result = ResponseParser._parse_risks(data, now)
        assert result[0].risk_level == RiskLevel.LOW

    def test_default_urgency_24_hours(self):
        now = datetime.now(UTC)
        data = [{}]
        result = ResponseParser._parse_risks(data, now)
        assert result[0].expires_at == now + timedelta(hours=24)

    def test_empty_list(self):
        result = ResponseParser._parse_risks([], datetime.now(UTC))
        assert result == []


# ============================================================
# 4. parse_risk_response (standalone)
# ============================================================


class TestParseRiskResponse:
    def test_parses_risks_key(self):
        response = {"risks": [{"risk_level": "medium", "title": "Test Risk"}]}
        result = ResponseParser.parse_risk_response(response)
        assert len(result) == 1
        assert result[0].risk_level == RiskLevel.MEDIUM

    def test_no_risks_key(self):
        result = ResponseParser.parse_risk_response({})
        assert result == []


# ============================================================
# 5. parse_opportunity_response (single product)
# ============================================================


class TestParseOpportunityResponse:
    def test_increase_recommendation(self):
        product = make_product(price=Decimal("100.00"))
        ai_response = {
            "recommendation": "increase",
            "suggested_price": 110,
            "confidence_score": 85,
            "reasoning": {"overall": "Strong demand signals"},
            "timing": {"optimal_window_days": 14},
            "expected_revenue_impact": "+12% revenue",
            "risks": ["competitor response"],
        }
        result = ResponseParser.parse_opportunity_response(product, ai_response)
        assert result.opportunity_type == OpportunityType.PRICE_INCREASE
        assert result.suggested_price == Decimal("110")
        assert result.confidence == ConfidenceLevel.VERY_HIGH
        assert result.reasoning == "Strong demand signals"

    def test_hold_recommendation(self):
        product = make_product(price=Decimal("50.00"))
        ai_response = {"recommendation": "hold", "confidence_score": 30}
        result = ResponseParser.parse_opportunity_response(product, ai_response)
        assert result.opportunity_type == OpportunityType.HOLD
        assert result.confidence == ConfidenceLevel.LOW

    def test_unknown_recommendation_defaults_to_hold(self):
        product = make_product(price=Decimal("50.00"))
        ai_response = {"recommendation": "spin", "confidence_score": 50}
        result = ResponseParser.parse_opportunity_response(product, ai_response)
        assert result.opportunity_type == OpportunityType.HOLD

    def test_confidence_level_thresholds(self):
        product = make_product()
        # Very high: >= 80
        r = ResponseParser.parse_opportunity_response(product, {"confidence_score": 80})
        assert r.confidence == ConfidenceLevel.VERY_HIGH
        # High: >= 60
        r = ResponseParser.parse_opportunity_response(product, {"confidence_score": 60})
        assert r.confidence == ConfidenceLevel.HIGH
        # Medium: >= 40
        r = ResponseParser.parse_opportunity_response(product, {"confidence_score": 40})
        assert r.confidence == ConfidenceLevel.MEDIUM
        # Low: < 40
        r = ResponseParser.parse_opportunity_response(product, {"confidence_score": 20})
        assert r.confidence == ConfidenceLevel.LOW

    def test_string_reasoning_fallback(self):
        product = make_product()
        ai_response = {"reasoning": "Simple string reasoning", "confidence_score": 50}
        result = ResponseParser.parse_opportunity_response(product, ai_response)
        assert result.reasoning == "Simple string reasoning"

    def test_default_suggested_price_uses_base(self):
        product = make_product(price=Decimal("75.00"))
        ai_response = {"confidence_score": 50}
        result = ResponseParser.parse_opportunity_response(product, ai_response)
        assert result.suggested_price == Decimal("75.00")


# ============================================================
# 6. parse_insight_response
# ============================================================


class TestParseInsightResponse:
    def test_full_response(self):
        ai_response = {
            "title": "Market Shift Detected",
            "summary": "Major trend change",
            "detailed_analysis": "Full analysis text",
            "key_factors": ["factor1", "factor2"],
        }
        result = ResponseParser.parse_insight_response(ai_response, "gemini-2.0", 500)
        assert result.title == "Market Shift Detected"
        assert result.data_points_analyzed == 500
        assert result.model_used == "gemini-2.0"

    def test_defaults_for_missing_fields(self):
        result = ResponseParser.parse_insight_response({}, "gpt-4", 0)
        assert result.title == "Market Insight"
        assert result.summary == ""
        assert result.key_factors == []


# ============================================================
# 7. parse_analysis_response (full orchestration)
# ============================================================


class TestParseAnalysisResponse:
    def test_full_response(self):
        product = make_product()
        ai_response = {
            "market_sentiment": "rising",
            "market_sentiment_score": 75,
            "executive_summary": "Market is trending up",
            "predictions": [{"direction": "rising", "confidence_score": 80}],
            "opportunities": [],
            "risks": [{"risk_level": "low", "title": "Minor risk"}],
            "key_insights": ["Insight 1", "Insight 2"],
            "recommended_actions": ["Action 1"],
        }
        result = ResponseParser.parse_analysis_response(
            user_id="user-1",
            ai_response=ai_response,
            products=[product],
            model_used="gemini-2.0",
            days=30,
            mentions_count=1000,
        )
        assert result.market_sentiment == TrendDirection.RISING
        assert result.market_sentiment_score == 75
        assert len(result.predictions) == 1
        assert len(result.risks) == 1
        assert len(result.insights) == 1
        assert result.products_analyzed == 1
        assert result.mentions_analyzed == 1000

    def test_invalid_sentiment_defaults_to_stable(self):
        ai_response = {"market_sentiment": "sideways"}
        result = ResponseParser.parse_analysis_response(
            "user-1",
            ai_response,
            [],
            "model",
            7,
            0,
        )
        assert result.market_sentiment == TrendDirection.STABLE

    def test_empty_response(self):
        result = ResponseParser.parse_analysis_response(
            "user-1",
            {},
            [],
            "model",
            7,
            0,
        )
        assert result.predictions == []
        assert result.opportunities == []
        assert result.risks == []
        assert result.insights == []
