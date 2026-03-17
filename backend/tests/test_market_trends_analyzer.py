"""
Tests for services/ai_trend_analysis/market_trends_analyzer.py

Covers:
- Enums: TrendAgent, TrendDirection, TrendTimeframe
- Dataclasses: TrendMessage, MarketDataPoint, TrendForecast
- MarketTrendsAnalyzer:
  - __init__ (defaults)
  - _format_market_data
  - _classify_observer_thought
  - _classify_analyst_thought
  - _classify_forecaster_thought
  - _extract_observations (signals from market data)
  - _parse_analyst_json (code blocks, raw JSON, fallback)
  - _parse_forecaster_json (code blocks, raw JSON, fallback)
  - run_observer_agent (streaming)
  - run_analyst_agent (streaming)
  - run_forecaster_agent (streaming)
  - analyze_image (success, error)
  - analyze_stream (full orchestration with/without image)
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
for mod in ["db.session", "google.genai", "google.genai.types"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
mock_settings = MagicMock()
mock_settings.OPENAI_API_KEY = "test"
mock_settings.GEMINI_API_KEY = "test"

from services.ai_trend_analysis.ai_clients import StreamChunk, ThoughtType
from services.ai_trend_analysis.market_trends_visual import (
    MarketDataPoint,
    MarketTrendsAnalyzer,
    TrendAgent,
    TrendDirection,
    TrendForecast,
    TrendMessage,
    TrendTimeframe,
)

# ── Helpers ───────────────────────────────────────────────────────


def _sample_market_data():
    return {
        "sentiment_score": -0.6,
        "sentiment_trend": "down",
        "volume_24h": 1200,
        "volume_trend": "up",
        "price_change_7d": -12.5,
        "price_change_30d": 5.0,
        "social_mentions": 450,
        "social_trend": "stable",
        "competitor_activity": "aggressive",
        "market_position": "mid",
        "seasonality": "normal",
    }


async def _fake_stream(*chunks):
    """Helper to create an async generator of StreamChunks."""
    for c in chunks:
        yield c


# ==================================================================
# Enums
# ==================================================================


class TestTrendAgent:
    def test_observer(self):
        assert TrendAgent.OBSERVER == "observer"

    def test_analyst(self):
        assert TrendAgent.ANALYST == "analyst"

    def test_forecaster(self):
        assert TrendAgent.FORECASTER == "forecaster"

    def test_is_str(self):
        assert isinstance(TrendAgent.OBSERVER, str)


class TestTrendDirection:
    def test_all_values(self):
        assert TrendDirection.STRONG_UP == "strong_up"
        assert TrendDirection.UP == "up"
        assert TrendDirection.STABLE == "stable"
        assert TrendDirection.DOWN == "down"
        assert TrendDirection.STRONG_DOWN == "strong_down"


class TestTrendTimeframe:
    def test_all_values(self):
        assert TrendTimeframe.IMMEDIATE == "immediate"
        assert TrendTimeframe.SHORT_TERM == "short_term"
        assert TrendTimeframe.MEDIUM_TERM == "medium_term"
        assert TrendTimeframe.LONG_TERM == "long_term"


# ==================================================================
# Dataclasses
# ==================================================================


class TestTrendMessage:
    def test_basic_creation(self):
        msg = TrendMessage(
            agent=TrendAgent.OBSERVER,
            thought_type=ThoughtType.OBSERVATION,
            content="Scanning...",
        )
        assert msg.agent == TrendAgent.OBSERVER
        assert msg.content == "Scanning..."
        assert msg.is_final is False
        assert msg.metadata == {}

    def test_final_message_with_metadata(self):
        msg = TrendMessage(
            agent=TrendAgent.ANALYST,
            thought_type=ThoughtType.ANALYSIS,
            content="Done",
            is_final=True,
            metadata={"key": "value"},
        )
        assert msg.is_final is True
        assert msg.metadata["key"] == "value"

    def test_none_thought_type(self):
        msg = TrendMessage(
            agent=TrendAgent.FORECASTER,
            thought_type=None,
            content="test",
        )
        assert msg.thought_type is None

    def test_separate_metadata_dicts(self):
        m1 = TrendMessage(agent=TrendAgent.OBSERVER, thought_type=None, content="a")
        m2 = TrendMessage(agent=TrendAgent.OBSERVER, thought_type=None, content="b")
        assert m1.metadata is not m2.metadata


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
            sentiment_score=-0.8,
            volume_24h=5000,
            price_change_7d=-15.0,
        )
        assert dp.sentiment_score == -0.8
        assert dp.volume_24h == 5000


class TestTrendForecast:
    def test_basic_creation(self):
        fc = TrendForecast(
            direction=TrendDirection.DOWN,
            confidence=0.75,
            timeframe=TrendTimeframe.SHORT_TERM,
            recommended_action="decrease price 5%",
        )
        assert fc.direction == TrendDirection.DOWN
        assert fc.confidence == 0.75
        assert fc.price_adjustment is None
        assert fc.key_drivers == []
        assert fc.risks == []
        assert fc.opportunities == []
        assert fc.monitoring_points == []

    def test_with_all_fields(self):
        fc = TrendForecast(
            direction=TrendDirection.STRONG_UP,
            confidence=0.9,
            timeframe=TrendTimeframe.MEDIUM_TERM,
            recommended_action="increase price",
            price_adjustment=10.0,
            key_drivers=["viral moment"],
            risks=["competitor reaction"],
            opportunities=["margin capture"],
            monitoring_points=["social volume"],
        )
        assert fc.price_adjustment == 10.0
        assert len(fc.key_drivers) == 1

    def test_separate_default_lists(self):
        f1 = TrendForecast(
            direction=TrendDirection.STABLE,
            confidence=0.5,
            timeframe=TrendTimeframe.IMMEDIATE,
            recommended_action="hold",
        )
        f2 = TrendForecast(
            direction=TrendDirection.STABLE,
            confidence=0.5,
            timeframe=TrendTimeframe.IMMEDIATE,
            recommended_action="hold",
        )
        assert f1.key_drivers is not f2.key_drivers
        assert f1.risks is not f2.risks


# ==================================================================
# MarketTrendsAnalyzer.__init__
# ==================================================================


class TestInit:
    def test_defaults(self):
        analyzer = MarketTrendsAnalyzer()
        assert analyzer.model == "gemini-2.0-flash"
        assert analyzer.significant_sentiment_change == 0.2
        assert analyzer.high_volume_multiplier == 1.5
        assert analyzer.min_confidence == 0.4


# ==================================================================
# _format_market_data
# ==================================================================


class TestFormatMarketData:
    def test_includes_all_sections(self):
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._format_market_data(_sample_market_data())
        assert "SENTIMENT" in result
        assert "VOLUME" in result
        assert "PRICE" in result
        assert "SOCIAL" in result
        assert "COMPETITIVE" in result
        assert "SEASONAL" in result

    def test_includes_values(self):
        analyzer = MarketTrendsAnalyzer()
        data = {"sentiment_score": -0.6, "price_change_7d": -12.5}
        result = analyzer._format_market_data(data)
        assert "-0.6" in result
        assert "-12.5" in result

    def test_missing_keys_use_defaults(self):
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._format_market_data({})
        assert "N/A" in result or "stable" in result


# ==================================================================
# _classify_observer_thought
# ==================================================================


class TestClassifyObserverThought:
    def test_always_returns_observation(self):
        analyzer = MarketTrendsAnalyzer()
        assert analyzer._classify_observer_thought("anything") == ThoughtType.OBSERVATION
        assert analyzer._classify_observer_thought("analyzing data") == ThoughtType.OBSERVATION
        assert analyzer._classify_observer_thought("I recommend") == ThoughtType.OBSERVATION
        assert analyzer._classify_observer_thought("") == ThoughtType.OBSERVATION


# ==================================================================
# _classify_analyst_thought
# ==================================================================


class TestClassifyAnalystThought:
    def test_hypothesis_keywords(self):
        analyzer = MarketTrendsAnalyzer()
        assert analyzer._classify_analyst_thought("because of the drop") == ThoughtType.HYPOTHESIS
        assert analyzer._classify_analyst_thought("likely due to competition") == ThoughtType.HYPOTHESIS
        assert analyzer._classify_analyst_thought("my hypothesis is") == ThoughtType.HYPOTHESIS

    def test_default_is_analysis(self):
        analyzer = MarketTrendsAnalyzer()
        assert analyzer._classify_analyst_thought("The trend is strong") == ThoughtType.ANALYSIS
        assert analyzer._classify_analyst_thought("Risk identified") == ThoughtType.ANALYSIS
        assert analyzer._classify_analyst_thought("") == ThoughtType.ANALYSIS

    def test_case_insensitive(self):
        analyzer = MarketTrendsAnalyzer()
        assert analyzer._classify_analyst_thought("BECAUSE of this") == ThoughtType.HYPOTHESIS
        assert analyzer._classify_analyst_thought("LIKELY DUE TO x") == ThoughtType.HYPOTHESIS


# ==================================================================
# _classify_forecaster_thought
# ==================================================================


class TestClassifyForecasterThought:
    def test_recommendation_keywords(self):
        analyzer = MarketTrendsAnalyzer()
        assert analyzer._classify_forecaster_thought("I recommend lowering") == ThoughtType.RECOMMENDATION
        assert analyzer._classify_forecaster_thought("You should hold") == ThoughtType.RECOMMENDATION
        assert analyzer._classify_forecaster_thought("Take action now") == ThoughtType.RECOMMENDATION

    def test_decision_keywords(self):
        analyzer = MarketTrendsAnalyzer()
        assert analyzer._classify_forecaster_thought("I decide to increase") == ThoughtType.DECISION
        assert analyzer._classify_forecaster_thought("In conclusion") == ThoughtType.DECISION
        assert analyzer._classify_forecaster_thought("The final verdict") == ThoughtType.DECISION

    def test_default_is_hypothesis(self):
        analyzer = MarketTrendsAnalyzer()
        assert analyzer._classify_forecaster_thought("The outlook is positive") == ThoughtType.HYPOTHESIS
        assert analyzer._classify_forecaster_thought("Forecast shows growth") == ThoughtType.HYPOTHESIS
        assert analyzer._classify_forecaster_thought("") == ThoughtType.HYPOTHESIS

    def test_case_insensitive(self):
        analyzer = MarketTrendsAnalyzer()
        assert analyzer._classify_forecaster_thought("RECOMMEND this") == ThoughtType.RECOMMENDATION
        assert analyzer._classify_forecaster_thought("FINAL decision") == ThoughtType.DECISION

    def test_priority_recommendation_over_decision(self):
        """'recommend' is checked first, even if 'final' also present."""
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._classify_forecaster_thought("I recommend the final action")
        assert result == ThoughtType.RECOMMENDATION


# ==================================================================
# _extract_observations
# ==================================================================


class TestExtractObservations:
    def test_strong_sentiment_signal(self):
        analyzer = MarketTrendsAnalyzer()
        data = {"sentiment_score": -0.7}
        result = analyzer._extract_observations("response text", data)
        assert any("sentiment" in s.lower() for s in result["signals"])

    def test_significant_price_movement(self):
        analyzer = MarketTrendsAnalyzer()
        data = {"price_change_7d": -15.0}
        result = analyzer._extract_observations("response", data)
        assert any("price" in s.lower() for s in result["signals"])

    def test_rising_volume_signal(self):
        analyzer = MarketTrendsAnalyzer()
        data = {"volume_trend": "up"}
        result = analyzer._extract_observations("response", data)
        assert any("volume" in s.lower() for s in result["signals"])

    def test_strong_up_volume_signal(self):
        analyzer = MarketTrendsAnalyzer()
        data = {"volume_trend": "strong_up"}
        result = analyzer._extract_observations("response", data)
        assert any("volume" in s.lower() for s in result["signals"])

    def test_no_signals_for_normal_data(self):
        analyzer = MarketTrendsAnalyzer()
        data = {"sentiment_score": 0.2, "price_change_7d": 3.0, "volume_trend": "stable"}
        result = analyzer._extract_observations("response", data)
        assert result["signals"] == []

    def test_preserves_full_analysis(self):
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._extract_observations("full text here", {})
        assert result["full_analysis"] == "full text here"

    def test_empty_data(self):
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._extract_observations("", {})
        assert result["signals"] == []

    def test_multiple_signals(self):
        analyzer = MarketTrendsAnalyzer()
        data = {
            "sentiment_score": -0.8,
            "price_change_7d": -20.0,
            "volume_trend": "up",
        }
        result = analyzer._extract_observations("text", data)
        assert len(result["signals"]) == 3


# ==================================================================
# _parse_analyst_json
# ==================================================================


class TestParseAnalystJson:
    def test_json_code_block(self):
        analyzer = MarketTrendsAnalyzer()
        response = 'Analysis:\n```json\n{"trend_strength": "strong", "confidence": 80}\n```'
        result = analyzer._parse_analyst_json(response)
        assert result["trend_strength"] == "strong"
        assert result["confidence"] == 80

    def test_generic_code_block(self):
        analyzer = MarketTrendsAnalyzer()
        response = 'Text:\n```\n{"trend_strength": "weak"}\n```'
        result = analyzer._parse_analyst_json(response)
        assert result["trend_strength"] == "weak"

    def test_raw_json_in_text(self):
        analyzer = MarketTrendsAnalyzer()
        response = 'Here is the analysis {"trend_stage": "late", "primary_driver": "competition"} end'
        result = analyzer._parse_analyst_json(response)
        assert result["trend_stage"] == "late"

    def test_invalid_json_returns_defaults(self):
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._parse_analyst_json("No JSON here at all")
        assert result["trend_strength"] == "moderate"
        assert result["confidence"] == 50

    def test_no_json_block_no_braces_returns_defaults(self):
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._parse_analyst_json("Just plain text analysis.")
        assert result["trend_strength"] == "moderate"

    def test_partial_json_merged_with_defaults(self):
        analyzer = MarketTrendsAnalyzer()
        response = '```json\n{"trend_strength": "strong"}\n```'
        result = analyzer._parse_analyst_json(response)
        assert result["trend_strength"] == "strong"
        # Defaults still present
        assert result["trend_stage"] == "mid"
        assert result["reversal_probability"] == 50

    def test_empty_response(self):
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._parse_analyst_json("")
        assert result["trend_strength"] == "moderate"


# ==================================================================
# _parse_forecaster_json
# ==================================================================


class TestParseForecasterJson:
    def test_json_code_block(self):
        analyzer = MarketTrendsAnalyzer()
        response = '```json\n{"direction": "down", "confidence": 75, "recommended_action": "decrease 5%"}\n```'
        result = analyzer._parse_forecaster_json(response)
        assert result["direction"] == "down"
        assert result["confidence"] == 75

    def test_generic_code_block(self):
        analyzer = MarketTrendsAnalyzer()
        response = '```\n{"direction": "up"}\n```'
        result = analyzer._parse_forecaster_json(response)
        assert result["direction"] == "up"

    def test_raw_json(self):
        analyzer = MarketTrendsAnalyzer()
        response = 'Forecast: {"direction": "strong_up", "price_adjustment_percent": 10}'
        result = analyzer._parse_forecaster_json(response)
        assert result["direction"] == "strong_up"
        assert result["price_adjustment_percent"] == 10

    def test_invalid_json_returns_defaults(self):
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._parse_forecaster_json("No JSON")
        assert result["direction"] == "stable"
        assert result["confidence"] == 50
        assert result["recommended_action"] == "continue monitoring"

    def test_partial_json_merged_with_defaults(self):
        analyzer = MarketTrendsAnalyzer()
        response = '```json\n{"direction": "down"}\n```'
        result = analyzer._parse_forecaster_json(response)
        assert result["direction"] == "down"
        assert result["timing"] == "wait_and_monitor"
        assert result["review_in_days"] == 7

    def test_empty_response(self):
        analyzer = MarketTrendsAnalyzer()
        result = analyzer._parse_forecaster_json("")
        assert result["direction"] == "stable"


# ==================================================================
# analyze_image
# ==================================================================


class TestAnalyzeImage:
    @pytest.mark.asyncio
    async def test_success(self):
        analyzer = MarketTrendsAnalyzer()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="Chart shows upward trend", is_final=False)
            yield StreamChunk(text=" with support at $80", is_final=False)
            yield StreamChunk(text="", is_final=True)

        with patch.object(type(analyzer), "_MarketTrendsAnalyzer__class__", create=True):
            with patch("services.ai_trend_analysis.market_trends_visual.ai_clients") as mock_ai:
                mock_ai.analyze_image_stream = mock_stream
                result = await analyzer.analyze_image(b"fake", "png", "Widget", "electronics")

        assert "upward trend" in result
        assert "support at $80" in result

    @pytest.mark.asyncio
    async def test_error_returns_error_message(self):
        analyzer = MarketTrendsAnalyzer()

        async def mock_stream(*args, **kwargs):
            raise Exception("Image processing failed")
            yield  # Make it a generator

        with patch("services.ai_trend_analysis.market_trends_visual.ai_clients") as mock_ai:
            mock_ai.analyze_image_stream = mock_stream
            result = await analyzer.analyze_image(b"fake", "png", "Widget", "electronics")

        assert "failed" in result.lower()


# ==================================================================
# run_observer_agent
# ==================================================================


class TestRunObserverAgent:
    @pytest.mark.asyncio
    async def test_yields_messages(self):
        analyzer = MarketTrendsAnalyzer()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="I see market patterns", is_final=False)
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.market_trends_visual.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_observer_agent("Widget", "electronics", _sample_market_data()):
                messages.append(msg)

        assert len(messages) >= 2  # At least opening + final
        assert messages[0].agent == TrendAgent.OBSERVER
        assert messages[-1].is_final is True

    @pytest.mark.asyncio
    async def test_final_message_has_observations(self):
        analyzer = MarketTrendsAnalyzer()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="Analysis text", is_final=False)
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.market_trends_visual.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_observer_agent("Widget", "electronics", _sample_market_data()):
                messages.append(msg)

        final = messages[-1]
        assert "observations" in final.metadata

    @pytest.mark.asyncio
    async def test_with_image_analysis(self):
        analyzer = MarketTrendsAnalyzer()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="Chart shows decline", is_final=False)
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.market_trends_visual.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_observer_agent(
                "Widget", "electronics", {}, image_analysis="Chart shows downtrend"
            ):
                messages.append(msg)

        assert len(messages) >= 2


# ==================================================================
# run_analyst_agent
# ==================================================================


class TestRunAnalystAgent:
    @pytest.mark.asyncio
    async def test_yields_messages(self):
        analyzer = MarketTrendsAnalyzer()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text='{"trend_strength": "strong"}', is_final=False)
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.market_trends_visual.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_analyst_agent(
                "Widget",
                "electronics",
                _sample_market_data(),
                {"full_analysis": "Observer found patterns"},
            ):
                messages.append(msg)

        assert len(messages) >= 2
        assert messages[0].agent == TrendAgent.ANALYST
        assert messages[-1].is_final is True

    @pytest.mark.asyncio
    async def test_final_message_has_analysis(self):
        analyzer = MarketTrendsAnalyzer()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(
                text='```json\n{"trend_strength": "strong", "confidence": 80}\n```',
                is_final=False,
            )
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.market_trends_visual.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_analyst_agent("Widget", "electronics", {}, {}):
                messages.append(msg)

        final = messages[-1]
        assert "analysis" in final.metadata


# ==================================================================
# run_forecaster_agent
# ==================================================================


class TestRunForecasterAgent:
    @pytest.mark.asyncio
    async def test_yields_messages(self):
        analyzer = MarketTrendsAnalyzer()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(
                text='```json\n{"direction": "down", "confidence": 70}\n```',
                is_final=False,
            )
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.market_trends_visual.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_forecaster_agent("Widget", "electronics", _sample_market_data(), {}, {}):
                messages.append(msg)

        assert len(messages) >= 2
        assert messages[0].agent == TrendAgent.FORECASTER
        assert messages[-1].is_final is True

    @pytest.mark.asyncio
    async def test_final_message_has_forecast(self):
        analyzer = MarketTrendsAnalyzer()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(
                text='```json\n{"direction": "up", "recommended_action": "increase 5%"}\n```',
                is_final=False,
            )
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.market_trends_visual.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_forecaster_agent("Widget", "electronics", {}, {}, {}):
                messages.append(msg)

        final = messages[-1]
        assert "forecast" in final.metadata


# ==================================================================
# analyze_stream (full orchestration)
# ==================================================================


class TestAnalyzeStream:
    @pytest.mark.asyncio
    async def test_runs_all_three_agents(self):
        analyzer = MarketTrendsAnalyzer()

        # Mock each agent runner
        observer_msgs = [
            TrendMessage(TrendAgent.OBSERVER, ThoughtType.OBSERVATION, "Observing..."),
            TrendMessage(
                TrendAgent.OBSERVER,
                ThoughtType.DECISION,
                "Done",
                is_final=True,
                metadata={"observations": {"signals": [], "full_analysis": "text"}},
            ),
        ]
        analyst_msgs = [
            TrendMessage(TrendAgent.ANALYST, ThoughtType.ANALYSIS, "Analyzing..."),
            TrendMessage(
                TrendAgent.ANALYST,
                ThoughtType.DECISION,
                "Done",
                is_final=True,
                metadata={"analysis": {"trend_strength": "strong"}},
            ),
        ]
        forecaster_msgs = [
            TrendMessage(TrendAgent.FORECASTER, ThoughtType.HYPOTHESIS, "Forecasting..."),
            TrendMessage(
                TrendAgent.FORECASTER,
                ThoughtType.RECOMMENDATION,
                "Done",
                is_final=True,
                metadata={"forecast": {"direction": "down"}},
            ),
        ]

        async def mock_observer(*args, **kwargs):
            for m in observer_msgs:
                yield m

        async def mock_analyst(*args, **kwargs):
            for m in analyst_msgs:
                yield m

        async def mock_forecaster(*args, **kwargs):
            for m in forecaster_msgs:
                yield m

        analyzer.run_observer_agent = mock_observer
        analyzer.run_analyst_agent = mock_analyst
        analyzer.run_forecaster_agent = mock_forecaster

        messages = []
        async for msg in analyzer.analyze_stream("Widget", "electronics", _sample_market_data()):
            messages.append(msg)

        agents_seen = set(m.agent for m in messages)
        assert TrendAgent.OBSERVER in agents_seen
        assert TrendAgent.ANALYST in agents_seen
        assert TrendAgent.FORECASTER in agents_seen

    @pytest.mark.asyncio
    async def test_with_image_calls_analyze_image(self):
        analyzer = MarketTrendsAnalyzer()
        analyzer.analyze_image = AsyncMock(return_value="Chart shows uptrend")

        async def mock_observer(*args, **kwargs):
            yield TrendMessage(
                TrendAgent.OBSERVER,
                ThoughtType.OBSERVATION,
                "Done",
                is_final=True,
                metadata={"observations": {"signals": []}},
            )

        async def mock_analyst(*args, **kwargs):
            yield TrendMessage(
                TrendAgent.ANALYST, ThoughtType.ANALYSIS, "Done", is_final=True, metadata={"analysis": {}}
            )

        async def mock_forecaster(*args, **kwargs):
            yield TrendMessage(
                TrendAgent.FORECASTER, ThoughtType.RECOMMENDATION, "Done", is_final=True, metadata={"forecast": {}}
            )

        analyzer.run_observer_agent = mock_observer
        analyzer.run_analyst_agent = mock_analyst
        analyzer.run_forecaster_agent = mock_forecaster

        messages = []
        async for msg in analyzer.analyze_stream(
            "Widget", "electronics", {}, image_bytes=b"fake_image", image_type="png"
        ):
            messages.append(msg)

        analyzer.analyze_image.assert_awaited_once_with(b"fake_image", "png", "Widget", "electronics")
        # Should have extra image-related messages
        assert len(messages) > 3

    @pytest.mark.asyncio
    async def test_without_image_skips_image_analysis(self):
        analyzer = MarketTrendsAnalyzer()
        analyzer.analyze_image = AsyncMock()

        async def mock_observer(*args, **kwargs):
            yield TrendMessage(
                TrendAgent.OBSERVER,
                ThoughtType.OBSERVATION,
                "Done",
                is_final=True,
                metadata={"observations": {"signals": []}},
            )

        async def mock_analyst(*args, **kwargs):
            yield TrendMessage(
                TrendAgent.ANALYST, ThoughtType.ANALYSIS, "Done", is_final=True, metadata={"analysis": {}}
            )

        async def mock_forecaster(*args, **kwargs):
            yield TrendMessage(
                TrendAgent.FORECASTER, ThoughtType.RECOMMENDATION, "Done", is_final=True, metadata={"forecast": {}}
            )

        analyzer.run_observer_agent = mock_observer
        analyzer.run_analyst_agent = mock_analyst
        analyzer.run_forecaster_agent = mock_forecaster

        messages = []
        async for msg in analyzer.analyze_stream("Widget", "electronics", {}):
            messages.append(msg)

        analyzer.analyze_image.assert_not_awaited()
