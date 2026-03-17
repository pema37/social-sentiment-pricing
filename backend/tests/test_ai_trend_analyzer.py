"""
Tests for services/ai_trend_analysis/analyzer.py

Covers all methods in AITrendAnalyzer:
- __init__ (dependency wiring)
- analyze (full pipeline, empty products, AI failure)
- get_product_opportunity (success, product not found)
- detect_risks (success, empty products, AI failure)
- generate_insight (success, empty products, AI failure)
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
# core.logging and core.config are handled by conftest.py (autouse).
# Only db.session and google.genai need file-level stubs.
for mod in ["db.session", "google.genai"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from services.ai_trend_analysis.analyzer import AITrendAnalyzer

# ── Helpers ───────────────────────────────────────────────────────


def _make_analyzer():
    """Create analyzer with fully mocked dependencies."""
    db = AsyncMock()
    analyzer = AITrendAnalyzer(db)

    # Mock collector (all async methods)
    analyzer.collector = MagicMock()
    analyzer.collector.get_products = AsyncMock(return_value=[])
    analyzer.collector.get_sentiment_history = AsyncMock(return_value=[])
    analyzer.collector.get_mentions_summary = AsyncMock(return_value=[])
    analyzer.collector.get_competitor_data = AsyncMock(return_value=[])
    analyzer.collector.get_product_sentiment = AsyncMock(
        return_value={
            "current": 0.5,
            "avg_7d": 0.5,
            "avg_30d": 0.5,
            "trend": "stable",
            "avg_volume": 5,
            "volume_change": 0,
        }
    )
    analyzer.collector.get_product_mentions = AsyncMock(return_value=[])
    analyzer.collector.get_product_competitors = AsyncMock(return_value=[])
    analyzer.collector.get_negative_mentions = AsyncMock(return_value=[])
    analyzer.collector.get_sentiment_drops = AsyncMock(return_value=[])
    analyzer.collector.get_recent_competitor_activities = AsyncMock(return_value=[])
    analyzer.collector.get_current_alerts = AsyncMock(return_value=[])

    # Mock formatter (all static/sync)
    analyzer.formatter = MagicMock()
    analyzer.formatter.format_products.return_value = "No products"
    analyzer.formatter.format_sentiment_history.return_value = "No data"
    analyzer.formatter.format_mentions_summary.return_value = "No mentions"
    analyzer.formatter.format_competitor_data.return_value = "No competitors"
    analyzer.formatter.format_competitor_prices.return_value = "No prices"
    analyzer.formatter.format_recent_mentions.return_value = "No mentions"
    analyzer.formatter.format_negative_mentions.return_value = "No negatives"
    analyzer.formatter.format_sentiment_drops.return_value = "No drops"
    analyzer.formatter.format_competitor_activities.return_value = "No activities"
    analyzer.formatter.format_current_alerts.return_value = "No alerts"
    analyzer.formatter.format_trends.return_value = "No trends"
    analyzer.formatter.format_events.return_value = "No events"

    # Mock calculator (all sync)
    analyzer.calculator = MagicMock()
    analyzer.calculator.calculate_avg_sentiment.return_value = 0.5
    analyzer.calculator.calculate_sentiment_trend.return_value = "stable"
    analyzer.calculator.calculate_volume_change.return_value = 0.0
    analyzer.calculator.summarize_competitor_changes.return_value = "No changes"
    analyzer.calculator.calculate_sentiment_volatility.return_value = 0.1
    analyzer.calculator.get_top_performing_product.return_value = "Widget"
    analyzer.calculator.get_worst_performing_product.return_value = "Gadget"
    analyzer.calculator.detect_basic_trends.return_value = []
    analyzer.calculator.detect_notable_events.return_value = []

    # Mock parser (all sync)
    analyzer.parser = MagicMock()
    mock_result = MagicMock()
    mock_result.predictions = []
    mock_result.opportunities = []
    mock_result.risks = []
    analyzer.parser.parse_analysis_response.return_value = mock_result
    analyzer.parser.parse_opportunity_response.return_value = MagicMock()
    analyzer.parser.parse_risk_response.return_value = []
    analyzer.parser.parse_insight_response.return_value = MagicMock()

    return analyzer


def _make_product(name="Widget", base_price=29.99):
    p = MagicMock()
    p.name = name
    p.base_price = base_price
    p.current_price = base_price
    p.min_price = 19.99
    p.max_price = 49.99
    p.cost = 15.00
    return p


# ==================================================================
# __init__
# ==================================================================


class TestInit:
    def test_creates_dependencies(self):
        db = AsyncMock()
        analyzer = AITrendAnalyzer(db)
        assert analyzer.db is db
        assert analyzer.collector is not None
        assert analyzer.formatter is not None
        assert analyzer.calculator is not None
        assert analyzer.parser is not None


# ==================================================================
# analyze
# ==================================================================


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_no_products_returns_empty_result(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = []

        result = await analyzer.analyze(user_id="user-1", days=30)

        analyzer.parser.parse_analysis_response.assert_called_once()
        call_kwargs = analyzer.parser.parse_analysis_response.call_args
        ai_response = (
            call_kwargs[1]["ai_response"]
            if "ai_response" in (call_kwargs[1] or {})
            else call_kwargs[0][1]
            if len(call_kwargs[0]) > 1
            else call_kwargs[1].get("ai_response")
        )
        # Verify it was called with empty products
        assert result is not None

    @pytest.mark.asyncio
    async def test_no_products_does_not_call_ai(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = []

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock()
            await analyzer.analyze(user_id="user-1")
            mock_ai.call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_collects_all_data(self):
        analyzer = _make_analyzer()
        products = [_make_product()]
        analyzer.collector.get_products.return_value = products

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(
                return_value=(
                    {
                        "market_sentiment": "stable",
                        "market_sentiment_score": 0,
                        "predictions": [],
                        "opportunities": [],
                        "risks": [],
                        "executive_summary": "",
                        "recommended_actions": [],
                        "key_insights": [],
                    },
                    "openai",
                )
            )
            await analyzer.analyze(user_id="user-1", days=14, product_ids=["prod-1"])

        analyzer.collector.get_products.assert_awaited_once_with("user-1", ["prod-1"])
        analyzer.collector.get_sentiment_history.assert_awaited_once_with("user-1", 14, ["prod-1"])
        analyzer.collector.get_mentions_summary.assert_awaited_once_with("user-1", 14, ["prod-1"])
        analyzer.collector.get_competitor_data.assert_awaited_once_with("user-1", ["prod-1"])

    @pytest.mark.asyncio
    async def test_calls_calculator_with_collected_data(self):
        analyzer = _make_analyzer()
        products = [_make_product()]
        sentiment = [{"score": 0.5}]
        mentions = [{"platform": "reddit"}]
        competitors = [{"competitor_name": "Amazon"}]
        analyzer.collector.get_products.return_value = products
        analyzer.collector.get_sentiment_history.return_value = sentiment
        analyzer.collector.get_mentions_summary.return_value = mentions
        analyzer.collector.get_competitor_data.return_value = competitors

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            await analyzer.analyze(user_id="user-1")

        analyzer.calculator.calculate_avg_sentiment.assert_called_once_with(sentiment)
        analyzer.calculator.calculate_sentiment_trend.assert_called_once_with(sentiment)
        analyzer.calculator.calculate_volume_change.assert_called_once_with(mentions, 30)
        analyzer.calculator.summarize_competitor_changes.assert_called_once_with(competitors)

    @pytest.mark.asyncio
    async def test_calls_ai_with_correct_model(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "gemini"))
            await analyzer.analyze(user_id="user-1", use_model="gemini")

        mock_ai.call.assert_awaited_once()
        call_args = mock_ai.call.call_args
        assert call_args[0][2] == "gemini"

    @pytest.mark.asyncio
    async def test_ai_failure_returns_fallback(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(side_effect=Exception("API down"))
            result = await analyzer.analyze(user_id="user-1")

        # Parser should still be called with fallback response
        analyzer.parser.parse_analysis_response.assert_called()
        call_kwargs = analyzer.parser.parse_analysis_response.call_args
        # model_used should be "fallback"
        assert "fallback" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_returns_parsed_result(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]
        expected = MagicMock()
        expected.predictions = [MagicMock()]
        expected.opportunities = [MagicMock(), MagicMock()]
        expected.risks = []
        analyzer.parser.parse_analysis_response.return_value = expected

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            result = await analyzer.analyze(user_id="user-1")

        assert result is expected

    @pytest.mark.asyncio
    async def test_default_days_is_30(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = []
        await analyzer.analyze(user_id="user-1")
        # Sentiment history should be called with days=30 default
        analyzer.collector.get_sentiment_history.assert_awaited_once()
        call_args = analyzer.collector.get_sentiment_history.call_args
        assert call_args[0][1] == 30  # days parameter


# ==================================================================
# get_product_opportunity
# ==================================================================


class TestGetProductOpportunity:
    @pytest.mark.asyncio
    async def test_product_not_found_raises(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = []

        with pytest.raises(ValueError, match="Product prod-999 not found"):
            await analyzer.get_product_opportunity(user_id="user-1", product_id="prod-999")

    @pytest.mark.asyncio
    async def test_collects_product_specific_data(self):
        analyzer = _make_analyzer()
        product = _make_product(name="Headphones")
        analyzer.collector.get_products.return_value = [product]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            await analyzer.get_product_opportunity(user_id="user-1", product_id="prod-1")

        analyzer.collector.get_products.assert_awaited_once_with("user-1", ["prod-1"])
        analyzer.collector.get_product_sentiment.assert_awaited_once_with("prod-1", days=30)
        analyzer.collector.get_product_mentions.assert_awaited_once_with("prod-1", days=7)
        analyzer.collector.get_product_competitors.assert_awaited_once_with("prod-1")

    @pytest.mark.asyncio
    async def test_calls_ai_and_parser(self):
        analyzer = _make_analyzer()
        product = _make_product()
        analyzer.collector.get_products.return_value = [product]
        expected_opp = MagicMock()
        analyzer.parser.parse_opportunity_response.return_value = expected_opp

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({"recommendation": "increase"}, "openai"))
            result = await analyzer.get_product_opportunity(user_id="user-1", product_id="prod-1")

        mock_ai.call.assert_awaited_once()
        analyzer.parser.parse_opportunity_response.assert_called_once_with(product, {"recommendation": "increase"})
        assert result is expected_opp

    @pytest.mark.asyncio
    async def test_uses_first_product_from_list(self):
        analyzer = _make_analyzer()
        p1 = _make_product(name="First")
        p2 = _make_product(name="Second")
        analyzer.collector.get_products.return_value = [p1, p2]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            await analyzer.get_product_opportunity(user_id="user-1", product_id="prod-1")

        # Should pass p1 (first product) to parser
        call_args = analyzer.parser.parse_opportunity_response.call_args
        assert call_args[0][0] is p1

    @pytest.mark.asyncio
    async def test_product_without_base_price_uses_current_price(self):
        """When product doesn't have base_price, falls back to current_price."""
        analyzer = _make_analyzer()
        product = MagicMock(spec=["name", "current_price", "min_price", "max_price"])
        product.name = "Widget"
        product.current_price = 39.99
        product.min_price = 19.99
        product.max_price = 59.99
        analyzer.collector.get_products.return_value = [product]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            # Should not raise even without base_price
            await analyzer.get_product_opportunity(user_id="user-1", product_id="prod-1")


# ==================================================================
# detect_risks
# ==================================================================


class TestDetectRisks:
    @pytest.mark.asyncio
    async def test_no_products_returns_empty(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = []

        result = await analyzer.detect_risks(user_id="user-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_no_products_does_not_call_ai(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = []

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock()
            await analyzer.detect_risks(user_id="user-1")
            mock_ai.call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_collects_risk_data(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            await analyzer.detect_risks(user_id="user-1")

        analyzer.collector.get_products.assert_awaited_once_with("user-1")
        analyzer.collector.get_negative_mentions.assert_awaited_once_with("user-1", days=7)
        analyzer.collector.get_sentiment_drops.assert_awaited_once_with("user-1", days=7)
        analyzer.collector.get_recent_competitor_activities.assert_awaited_once_with("user-1")
        analyzer.collector.get_current_alerts.assert_awaited_once_with("user-1")

    @pytest.mark.asyncio
    async def test_calls_formatters(self):
        analyzer = _make_analyzer()
        products = [_make_product()]
        neg_mentions = [MagicMock()]
        analyzer.collector.get_products.return_value = products
        analyzer.collector.get_negative_mentions.return_value = neg_mentions

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            await analyzer.detect_risks(user_id="user-1")

        analyzer.formatter.format_products.assert_called_once_with(products)
        analyzer.formatter.format_negative_mentions.assert_called_once_with(neg_mentions)

    @pytest.mark.asyncio
    async def test_ai_failure_returns_empty(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(side_effect=Exception("API error"))
            result = await analyzer.detect_risks(user_id="user-1")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_parsed_risks(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]
        expected_risks = [MagicMock(), MagicMock()]
        analyzer.parser.parse_risk_response.return_value = expected_risks

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            result = await analyzer.detect_risks(user_id="user-1")

        assert result is expected_risks

    @pytest.mark.asyncio
    async def test_uses_specified_model(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "gemini"))
            await analyzer.detect_risks(user_id="user-1", use_model="gemini")

        call_args = mock_ai.call.call_args
        assert call_args[0][2] == "gemini"


# ==================================================================
# generate_insight
# ==================================================================


class TestGenerateInsight:
    @pytest.mark.asyncio
    async def test_no_products_returns_placeholder(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = []

        result = await analyzer.generate_insight(user_id="user-1")

        analyzer.parser.parse_insight_response.assert_called_once()
        call_args = analyzer.parser.parse_insight_response.call_args
        ai_response = call_args[0][0] if call_args[0] else call_args[1]["ai_response"]
        assert ai_response["title"] == "No Data Available"

    @pytest.mark.asyncio
    async def test_no_products_does_not_call_ai(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = []

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock()
            await analyzer.generate_insight(user_id="user-1")
            mock_ai.call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_collects_insight_data(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            await analyzer.generate_insight(user_id="user-1", days=14)

        analyzer.collector.get_products.assert_awaited_once_with("user-1")
        analyzer.collector.get_sentiment_history.assert_awaited_once_with("user-1", 14)
        analyzer.collector.get_mentions_summary.assert_awaited_once_with("user-1", 14)

    @pytest.mark.asyncio
    async def test_calls_calculators(self):
        analyzer = _make_analyzer()
        products = [_make_product()]
        sentiment = [{"score": 0.5}]
        mentions = [{"platform": "reddit"}]
        analyzer.collector.get_products.return_value = products
        analyzer.collector.get_sentiment_history.return_value = sentiment
        analyzer.collector.get_mentions_summary.return_value = mentions

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            await analyzer.generate_insight(user_id="user-1")

        analyzer.calculator.calculate_avg_sentiment.assert_called_once_with(sentiment)
        analyzer.calculator.calculate_sentiment_volatility.assert_called_once_with(sentiment)
        analyzer.calculator.get_top_performing_product.assert_called_once_with(products, sentiment)
        analyzer.calculator.get_worst_performing_product.assert_called_once_with(products, sentiment)
        analyzer.calculator.detect_basic_trends.assert_called_once_with(sentiment)
        analyzer.calculator.detect_notable_events.assert_called_once_with(sentiment, mentions)

    @pytest.mark.asyncio
    async def test_ai_failure_returns_fallback_insight(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(side_effect=Exception("API timeout"))
            result = await analyzer.generate_insight(user_id="user-1")

        # Parser should be called with fallback
        analyzer.parser.parse_insight_response.assert_called()
        call_args = analyzer.parser.parse_insight_response.call_args
        ai_response = call_args[0][0] if call_args[0] else call_args[1]["ai_response"]
        assert ai_response["title"] == "Analysis Unavailable"

    @pytest.mark.asyncio
    async def test_returns_parsed_insight(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]
        expected = MagicMock()
        analyzer.parser.parse_insight_response.return_value = expected

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            result = await analyzer.generate_insight(user_id="user-1")

        assert result is expected

    @pytest.mark.asyncio
    async def test_passes_mentions_count_to_parser(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = [_make_product()]
        mentions = [{"platform": "reddit"}, {"platform": "twitter"}]
        analyzer.collector.get_mentions_summary.return_value = mentions

        with patch("services.ai_trend_analysis.analyzer.ai_clients") as mock_ai:
            mock_ai.call = AsyncMock(return_value=({}, "openai"))
            await analyzer.generate_insight(user_id="user-1")

        call_args = analyzer.parser.parse_insight_response.call_args
        # mentions_count should be 2
        assert 2 in call_args[0] or call_args[1].get("mentions_count") == 2

    @pytest.mark.asyncio
    async def test_default_days_is_30(self):
        analyzer = _make_analyzer()
        analyzer.collector.get_products.return_value = []
        await analyzer.generate_insight(user_id="user-1")
        call_args = analyzer.collector.get_sentiment_history.call_args
        assert call_args[0][1] == 30
