"""
Test Suite: Autonomous Pipeline Tool Handlers
===============================================
Tests for every tool function that Gemini agents can invoke.

These handlers bridge AI reasoning and real-world execution:
- fetch_competitor_price → price monitoring APIs
- detect_price_change → signal detection logic
- analyze_sentiment → VADER + Gemini hybrid
- calculate_elasticity → demand modeling
- assess_risk → multi-factor risk scoring
- calculate_optimal_price → pricing optimization
- write_price_to_chain → BNB Chain smart contract

Run: pytest backend/tests/test_autonomous_tool_handlers.py -v
"""

import pytest

from backend.services.ai_trend_analysis.autonomous_orchestrator import (
    handle_tool_call,
    _handle_fetch_competitor_price,
    _handle_detect_price_change,
    _handle_analyze_sentiment,
    _handle_calculate_elasticity,
    _handle_assess_risk,
    _handle_calculate_optimal_price,
    _handle_write_price_to_chain,
)


# ---------------------------------------------------------------------------
# handle_tool_call dispatcher
# ---------------------------------------------------------------------------

class TestToolCallDispatcher:
    """The central dispatcher routes function names to handlers."""

    @pytest.mark.asyncio
    async def test_routes_known_tool_names(self):
        result = await handle_tool_call("fetch_competitor_price", {"product_category": "electronics"})
        assert "competitor_name" in result
        assert "current_price" in result

    @pytest.mark.asyncio
    async def test_returns_error_for_unknown_tool(self):
        result = await handle_tool_call("nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_all_registered_tools_are_callable(self):
        tools = [
            ("fetch_competitor_price", {"product_category": "test"}),
            ("detect_price_change", {"current_price": 80, "last_known_price": 100, "product_id": "p1"}),
            ("analyze_sentiment", {"product_category": "test"}),
            ("calculate_elasticity", {"product_id": "p1"}),
            ("assess_risk", {"signal": {}, "sentiment_score": -0.5}),
            ("calculate_optimal_price", {"current_price": 100, "assessment": {}, "signal": {}}),
            ("write_price_to_chain", {"product_id": "p1", "new_price": 88, "confidence": 0.9}),
        ]
        for name, args in tools:
            result = await handle_tool_call(name, args)
            assert "error" not in result, f"Tool '{name}' returned error: {result}"


# ---------------------------------------------------------------------------
# fetch_competitor_price
# ---------------------------------------------------------------------------

class TestFetchCompetitorPrice:

    @pytest.mark.asyncio
    async def test_returns_required_fields(self):
        result = await _handle_fetch_competitor_price({"product_category": "electronics"})
        assert "competitor_name" in result
        assert "current_price" in result
        assert "previous_price" in result
        assert "currency" in result
        assert "source" in result

    @pytest.mark.asyncio
    async def test_returns_numeric_prices(self):
        result = await _handle_fetch_competitor_price({"product_category": "electronics"})
        assert isinstance(result["current_price"], (int, float))
        assert isinstance(result["previous_price"], (int, float))

    @pytest.mark.asyncio
    async def test_passes_category_through(self):
        result = await _handle_fetch_competitor_price({"product_category": "fashion"})
        assert result["product"] == "fashion"

    @pytest.mark.asyncio
    async def test_includes_timestamp(self):
        result = await _handle_fetch_competitor_price({"product_category": "test"})
        assert "last_updated" in result


# ---------------------------------------------------------------------------
# detect_price_change
# ---------------------------------------------------------------------------

class TestDetectPriceChange:

    @pytest.mark.asyncio
    async def test_detects_significant_drop(self):
        result = await _handle_detect_price_change({
            "current_price": 85.0,
            "last_known_price": 100.0,
            "product_id": "test-001",
        })
        assert result["change_detected"] is True
        assert result["change_pct"] == -15.0
        assert result["signal_type"] == "price_drop"

    @pytest.mark.asyncio
    async def test_detects_significant_increase(self):
        result = await _handle_detect_price_change({
            "current_price": 110.0,
            "last_known_price": 100.0,
            "product_id": "test-001",
        })
        assert result["change_detected"] is True
        assert result["change_pct"] == 10.0
        assert result["signal_type"] == "price_increase"

    @pytest.mark.asyncio
    async def test_stable_when_change_below_threshold(self):
        result = await _handle_detect_price_change({
            "current_price": 99.0,
            "last_known_price": 100.0,
            "product_id": "test-001",
        })
        assert result["change_detected"] is False
        assert result["signal_type"] == "stable"

    @pytest.mark.asyncio
    async def test_high_significance_for_large_changes(self):
        result = await _handle_detect_price_change({
            "current_price": 80.0,
            "last_known_price": 100.0,
            "product_id": "test-001",
        })
        assert result["significance"] == "high"

    @pytest.mark.asyncio
    async def test_medium_significance_for_moderate_changes(self):
        result = await _handle_detect_price_change({
            "current_price": 93.0,
            "last_known_price": 100.0,
            "product_id": "test-001",
        })
        assert result["significance"] == "medium"

    @pytest.mark.asyncio
    async def test_handles_zero_last_price_gracefully(self):
        result = await _handle_detect_price_change({
            "current_price": 50.0,
            "last_known_price": 0,
            "product_id": "test-001",
        })
        assert result["change_pct"] == 0
        assert result["change_detected"] is False


# ---------------------------------------------------------------------------
# analyze_sentiment
# ---------------------------------------------------------------------------

class TestAnalyzeSentiment:

    @pytest.mark.asyncio
    async def test_returns_sentiment_structure(self):
        result = await _handle_analyze_sentiment({"product_category": "electronics"})
        assert "sentiment_score" in result
        assert "sentiment_label" in result
        assert "mention_count" in result
        assert "platforms" in result

    @pytest.mark.asyncio
    async def test_sentiment_score_in_valid_range(self):
        result = await _handle_analyze_sentiment({"product_category": "test"})
        assert -1.0 <= result["sentiment_score"] <= 1.0

    @pytest.mark.asyncio
    async def test_platforms_breakdown_provided(self):
        result = await _handle_analyze_sentiment({"product_category": "test"})
        platforms = result["platforms"]
        assert "reddit" in platforms
        assert "twitter" in platforms

    @pytest.mark.asyncio
    async def test_respects_timeframe_parameter(self):
        result = await _handle_analyze_sentiment({
            "product_category": "test",
            "timeframe_hours": 48,
        })
        assert result["timeframe_hours"] == 48

    @pytest.mark.asyncio
    async def test_default_timeframe_is_24_hours(self):
        result = await _handle_analyze_sentiment({"product_category": "test"})
        assert result["timeframe_hours"] == 24


# ---------------------------------------------------------------------------
# calculate_elasticity
# ---------------------------------------------------------------------------

class TestCalculateElasticity:

    @pytest.mark.asyncio
    async def test_returns_elasticity_structure(self):
        result = await _handle_calculate_elasticity({"product_id": "test-001"})
        assert "elasticity_coefficient" in result
        assert "interpretation" in result
        assert "optimal_range" in result

    @pytest.mark.asyncio
    async def test_coefficient_is_negative_for_normal_goods(self):
        result = await _handle_calculate_elasticity({"product_id": "test-001"})
        assert result["elasticity_coefficient"] < 0

    @pytest.mark.asyncio
    async def test_optimal_range_has_min_max(self):
        result = await _handle_calculate_elasticity({"product_id": "test-001"})
        assert result["optimal_range"]["min"] < result["optimal_range"]["max"]


# ---------------------------------------------------------------------------
# assess_risk
# ---------------------------------------------------------------------------

class TestAssessRisk:

    @pytest.mark.asyncio
    async def test_returns_risk_structure(self):
        result = await _handle_assess_risk({"signal": {}, "sentiment_score": -0.5})
        assert "risk_level" in result
        assert "risk_factors" in result
        assert "mitigation" in result

    @pytest.mark.asyncio
    async def test_risk_factors_is_list(self):
        result = await _handle_assess_risk({"signal": {}, "sentiment_score": -0.3})
        assert isinstance(result["risk_factors"], list)
        assert len(result["risk_factors"]) > 0

    @pytest.mark.asyncio
    async def test_includes_revenue_risk_projection(self):
        result = await _handle_assess_risk({"signal": {}, "sentiment_score": -0.5})
        assert "revenue_risk_if_no_action" in result


# ---------------------------------------------------------------------------
# calculate_optimal_price
# ---------------------------------------------------------------------------

class TestCalculateOptimalPrice:

    @pytest.mark.asyncio
    async def test_decrease_direction_lowers_price(self):
        result = await _handle_calculate_optimal_price({
            "current_price": 100.0,
            "assessment": {"recommended_direction": "decrease"},
            "signal": {},
        })
        assert result["optimal_price"] < 100.0

    @pytest.mark.asyncio
    async def test_increase_direction_raises_price(self):
        result = await _handle_calculate_optimal_price({
            "current_price": 100.0,
            "assessment": {"recommended_direction": "increase"},
            "signal": {},
        })
        assert result["optimal_price"] > 100.0

    @pytest.mark.asyncio
    async def test_hold_direction_keeps_price(self):
        result = await _handle_calculate_optimal_price({
            "current_price": 100.0,
            "assessment": {"recommended_direction": "hold"},
            "signal": {},
        })
        assert result["optimal_price"] == 100.0

    @pytest.mark.asyncio
    async def test_returns_confidence_score(self):
        result = await _handle_calculate_optimal_price({
            "current_price": 100.0,
            "assessment": {"recommended_direction": "decrease"},
            "signal": {},
        })
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_returns_weighted_factors(self):
        result = await _handle_calculate_optimal_price({
            "current_price": 100.0,
            "assessment": {},
            "signal": {},
        })
        factors = result["factors_weighted"]
        assert sum(factors.values()) == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_change_pct_consistent_with_prices(self):
        result = await _handle_calculate_optimal_price({
            "current_price": 100.0,
            "assessment": {"recommended_direction": "decrease"},
            "signal": {},
        })
        expected_pct = (result["optimal_price"] - 100.0) / 100.0 * 100
        assert result["change_pct"] == pytest.approx(expected_pct, abs=0.1)


# ---------------------------------------------------------------------------
# write_price_to_chain
# ---------------------------------------------------------------------------

class TestWritePriceToChain:

    @pytest.mark.asyncio
    async def test_returns_success_with_tx_hash(self):
        result = await _handle_write_price_to_chain({
            "product_id": "test-001",
            "new_price": 87.99,
            "confidence": 0.87,
        })
        assert result["success"] is True
        assert result["tx_hash"] is not None
        assert result["tx_hash"].startswith("0x")

    @pytest.mark.asyncio
    async def test_tx_hash_is_valid_length(self):
        result = await _handle_write_price_to_chain({
            "product_id": "test-001",
            "new_price": 87.99,
            "confidence": 0.87,
        })
        # Ethereum-style tx hashes are 66 chars (0x + 64 hex)
        assert len(result["tx_hash"]) == 66

    @pytest.mark.asyncio
    async def test_returns_chain_metadata(self):
        result = await _handle_write_price_to_chain({
            "product_id": "test-001",
            "new_price": 87.99,
            "confidence": 0.87,
        })
        assert "chain" in result
        assert "block_number" in result
        assert "gas_used" in result
        assert "explorer_url" in result

    @pytest.mark.asyncio
    async def test_explorer_url_contains_tx_hash(self):
        result = await _handle_write_price_to_chain({
            "product_id": "test-001",
            "new_price": 87.99,
            "confidence": 0.87,
        })
        assert result["tx_hash"] in result["explorer_url"]

    @pytest.mark.asyncio
    async def test_returns_execution_timestamp(self):
        result = await _handle_write_price_to_chain({
            "product_id": "test-001",
            "new_price": 87.99,
            "confidence": 0.87,
        })
        assert "executed_at" in result
        assert result["executed_at"] is not None



        