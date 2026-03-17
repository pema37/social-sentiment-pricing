"""Tests for services/ai_trend_analysis/market_trends_visual.py"""

import pytest

from services.ai_trend_analysis.ai_clients import ThoughtType
from services.ai_trend_analysis.market_trends_visual import (
    MarketDataPoint,
    MarketTrendsAnalyzer,
    TrendAgent,
    TrendDirection,
    TrendForecast,
    TrendMessage,
    TrendTimeframe,
)

# ════════════════════════════════════════
# ENUMS
# ════════════════════════════════════════


class TestTrendAgent:
    def test_values(self):
        assert TrendAgent.OBSERVER == "observer"
        assert TrendAgent.ANALYST == "analyst"
        assert TrendAgent.FORECASTER == "forecaster"

    def test_all_members(self):
        assert len(TrendAgent) == 3


class TestTrendDirection:
    def test_values(self):
        assert TrendDirection.STRONG_UP == "strong_up"
        assert TrendDirection.UP == "up"
        assert TrendDirection.STABLE == "stable"
        assert TrendDirection.DOWN == "down"
        assert TrendDirection.STRONG_DOWN == "strong_down"

    def test_all_members(self):
        assert len(TrendDirection) == 5


class TestTrendTimeframe:
    def test_values(self):
        assert TrendTimeframe.IMMEDIATE == "immediate"
        assert TrendTimeframe.SHORT_TERM == "short_term"
        assert TrendTimeframe.MEDIUM_TERM == "medium_term"
        assert TrendTimeframe.LONG_TERM == "long_term"

    def test_all_members(self):
        assert len(TrendTimeframe) == 4


# ════════════════════════════════════════
# DATACLASSES
# ════════════════════════════════════════


class TestTrendMessage:
    def test_creation_defaults(self):
        msg = TrendMessage(
            agent=TrendAgent.OBSERVER,
            thought_type=ThoughtType.OBSERVATION,
            content="Test message",
        )
        assert msg.agent == TrendAgent.OBSERVER
        assert msg.content == "Test message"
        assert msg.is_final is False
        assert msg.metadata == {}

    def test_creation_with_metadata(self):
        msg = TrendMessage(
            agent=TrendAgent.ANALYST,
            thought_type=ThoughtType.ANALYSIS,
            content="Analysis done",
            is_final=True,
            metadata={"key": "value"},
        )
        assert msg.is_final is True
        assert msg.metadata["key"] == "value"

    def test_none_thought_type(self):
        msg = TrendMessage(
            agent=TrendAgent.FORECASTER,
            thought_type=None,
            content="No type",
        )
        assert msg.thought_type is None


class TestMarketDataPoint:
    def test_defaults(self):
        dp = MarketDataPoint()
        assert dp.sentiment_score == 0.0
        assert dp.sentiment_trend == "stable"
        assert dp.volume_24h == 0
        assert dp.volume_trend == "stable"
        assert dp.price_change_7d == 0.0
        assert dp.price_change_30d == 0.0
        assert dp.social_mentions == 0
        assert dp.social_trend == "stable"
        assert dp.competitor_activity == "normal"
        assert dp.market_position == "mid"
        assert dp.seasonality == "normal"

    def test_custom_values(self):
        dp = MarketDataPoint(
            sentiment_score=0.8,
            volume_24h=5000,
            price_change_7d=12.5,
        )
        assert dp.sentiment_score == 0.8
        assert dp.volume_24h == 5000
        assert dp.price_change_7d == 12.5


class TestTrendForecast:
    def test_creation_with_defaults(self):
        fc = TrendForecast(
            direction=TrendDirection.UP,
            confidence=85.0,
            timeframe=TrendTimeframe.SHORT_TERM,
            recommended_action="Increase price 5%",
        )
        assert fc.direction == TrendDirection.UP
        assert fc.confidence == 85.0
        assert fc.price_adjustment is None
        assert fc.key_drivers == []
        assert fc.risks == []
        assert fc.opportunities == []
        assert fc.monitoring_points == []

    def test_creation_full(self):
        fc = TrendForecast(
            direction=TrendDirection.STRONG_UP,
            confidence=92.0,
            timeframe=TrendTimeframe.MEDIUM_TERM,
            recommended_action="Premium positioning",
            price_adjustment=15.0,
            key_drivers=["viral sentiment", "low competition"],
            risks=["market correction"],
            opportunities=["expand SKUs"],
            monitoring_points=["daily sentiment"],
        )
        assert fc.price_adjustment == 15.0
        assert len(fc.key_drivers) == 2
        assert "market correction" in fc.risks


# ════════════════════════════════════════
# MarketTrendsAnalyzer - Helper Methods
# ════════════════════════════════════════


class TestMarketTrendsAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return MarketTrendsAnalyzer()

    # ── _format_market_data ──

    def test_format_market_data_defaults(self, analyzer):
        result = analyzer._format_market_data({})
        assert "SENTIMENT" in result
        assert "VOLUME" in result
        assert "PRICE" in result
        assert "SOCIAL" in result
        assert "COMPETITIVE" in result
        assert "SEASONAL" in result

    def test_format_market_data_with_values(self, analyzer):
        data = {
            "sentiment_score": 0.75,
            "volume_24h": 12000,
            "price_change_7d": 8.5,
            "social_mentions": 340,
            "competitor_activity": "aggressive",
        }
        result = analyzer._format_market_data(data)
        assert "0.75" in result
        assert "12000" in result
        assert "8.5" in result
        assert "340" in result
        assert "aggressive" in result

    # ── _classify_observer_thought ──

    def test_classify_observer_always_observation(self, analyzer):
        assert analyzer._classify_observer_thought("anything") == ThoughtType.OBSERVATION
        assert analyzer._classify_observer_thought("pattern found") == ThoughtType.OBSERVATION
        assert analyzer._classify_observer_thought("signal detected") == ThoughtType.OBSERVATION

    # ── _classify_analyst_thought ──

    def test_classify_analyst_hypothesis(self, analyzer):
        assert analyzer._classify_analyst_thought("This is likely due to market shifts") == ThoughtType.HYPOTHESIS
        assert analyzer._classify_analyst_thought("Because demand increased") == ThoughtType.HYPOTHESIS
        assert analyzer._classify_analyst_thought("My hypothesis is...") == ThoughtType.HYPOTHESIS

    def test_classify_analyst_analysis(self, analyzer):
        assert analyzer._classify_analyst_thought("The trend shows moderate growth") == ThoughtType.ANALYSIS
        assert analyzer._classify_analyst_thought("Correlation is strong") == ThoughtType.ANALYSIS

    # ── _classify_forecaster_thought ──

    def test_classify_forecaster_recommendation(self, analyzer):
        assert analyzer._classify_forecaster_thought("I recommend increasing price") == ThoughtType.RECOMMENDATION
        assert analyzer._classify_forecaster_thought("You should monitor daily") == ThoughtType.RECOMMENDATION
        assert analyzer._classify_forecaster_thought("Take action now") == ThoughtType.RECOMMENDATION

    def test_classify_forecaster_decision(self, analyzer):
        assert analyzer._classify_forecaster_thought("In conclusion, hold") == ThoughtType.DECISION
        assert analyzer._classify_forecaster_thought("Final verdict") == ThoughtType.DECISION

    def test_classify_forecaster_hypothesis(self, analyzer):
        assert analyzer._classify_forecaster_thought("Price will likely rise 5%") == ThoughtType.HYPOTHESIS
        assert analyzer._classify_forecaster_thought("Outlook is positive") == ThoughtType.HYPOTHESIS

    # ── _extract_observations ──

    def test_extract_observations_no_signals(self, analyzer):
        data = {"sentiment_score": 0.2, "price_change_7d": 3, "volume_trend": "stable"}
        result = analyzer._extract_observations("Some analysis text", data)
        assert result["signals"] == []
        assert result["full_analysis"] == "Some analysis text"

    def test_extract_observations_strong_sentiment(self, analyzer):
        data = {"sentiment_score": 0.8, "price_change_7d": 2, "volume_trend": "stable"}
        result = analyzer._extract_observations("", data)
        assert any("sentiment" in s.lower() for s in result["signals"])

    def test_extract_observations_price_spike(self, analyzer):
        data = {"sentiment_score": 0.1, "price_change_7d": 15, "volume_trend": "stable"}
        result = analyzer._extract_observations("", data)
        assert any("price" in s.lower() for s in result["signals"])

    def test_extract_observations_rising_volume(self, analyzer):
        data = {"sentiment_score": 0.1, "price_change_7d": 2, "volume_trend": "up"}
        result = analyzer._extract_observations("", data)
        assert any("volume" in s.lower() for s in result["signals"])

    def test_extract_observations_multiple_signals(self, analyzer):
        data = {"sentiment_score": -0.9, "price_change_7d": -20, "volume_trend": "strong_up"}
        result = analyzer._extract_observations("", data)
        assert len(result["signals"]) == 3

    # ── _parse_analyst_json ──

    def test_parse_analyst_json_valid(self, analyzer):
        response = 'Some text\n```json\n{"trend_strength": "strong", "confidence": 90}\n```\nMore text'
        result = analyzer._parse_analyst_json(response)
        assert result["trend_strength"] == "strong"
        assert result["confidence"] == 90
        # Defaults should still be present
        assert "trend_stage" in result
        assert "primary_driver" in result

    def test_parse_analyst_json_no_json(self, analyzer):
        result = analyzer._parse_analyst_json("Just plain text with no JSON")
        assert result["trend_strength"] == "moderate"
        assert result["confidence"] == 50

    def test_parse_analyst_json_raw_json(self, analyzer):
        response = 'Analysis text {"trend_strength": "weak", "key_risks": ["competition"]}'
        result = analyzer._parse_analyst_json(response)
        assert result["trend_strength"] == "weak"
        assert "competition" in result["key_risks"]

    def test_parse_analyst_json_invalid(self, analyzer):
        result = analyzer._parse_analyst_json("```json\n{broken json}\n```")
        assert result["trend_strength"] == "moderate"  # Falls back to default

    def test_parse_analyst_json_generic_code_block(self, analyzer):
        response = 'Text\n```\n{"trend_strength": "strong"}\n```'
        result = analyzer._parse_analyst_json(response)
        assert result["trend_strength"] == "strong"

    # ── _parse_forecaster_json ──

    def test_parse_forecaster_json_valid(self, analyzer):
        response = '```json\n{"direction": "up", "confidence": 80, "recommended_action": "increase 5%"}\n```'
        result = analyzer._parse_forecaster_json(response)
        assert result["direction"] == "up"
        assert result["confidence"] == 80
        assert result["recommended_action"] == "increase 5%"

    def test_parse_forecaster_json_no_json(self, analyzer):
        result = analyzer._parse_forecaster_json("No JSON here")
        assert result["direction"] == "stable"
        assert result["confidence"] == 50
        assert result["timing"] == "wait_and_monitor"

    def test_parse_forecaster_json_partial(self, analyzer):
        response = '```json\n{"direction": "strong_down", "key_triggers": ["price war"]}\n```'
        result = analyzer._parse_forecaster_json(response)
        assert result["direction"] == "strong_down"
        assert "price war" in result["key_triggers"]
        # Defaults filled in
        assert result["review_in_days"] == 7

    def test_parse_forecaster_json_invalid(self, analyzer):
        result = analyzer._parse_forecaster_json("```json\n{not valid}\n```")
        assert result["direction"] == "stable"

    # ── Analyzer init ──

    def test_analyzer_defaults(self, analyzer):
        assert analyzer.model == "gemini-2.0-flash"
        assert analyzer.significant_sentiment_change == 0.2
        assert analyzer.high_volume_multiplier == 1.5
        assert analyzer.min_confidence == 0.4
