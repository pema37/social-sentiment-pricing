"""
Tests for services/ai_trend_analysis/autonomous_orchestrator.py

Covers:
- Pydantic schemas: MarketSignal, MarketAssessment, PricingDecision, AgentStreamEvent
- Enums: AgentPhase
- Tool execution handlers: all 7 handle_tool_call functions
- AutonomousOrchestrator: _run_scout, _run_analyst, _run_strategist, _sse_event
- AutonomousOrchestrator: run_pipeline, run_pipeline_streaming
- AutonomousTrigger: start_monitoring, stop_monitoring
"""

import sys
import json
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
# Stub google.genai to avoid API key requirement at import
import types as _types
_google = _types.ModuleType("google")
_genai = _types.ModuleType("google.genai")
_genai.Client = MagicMock()
_genai_types = _types.ModuleType("google.genai.types")
_genai_types.Tool = MagicMock()
_genai_types.GoogleSearch = MagicMock()
_genai_types.GenerateContentConfig = MagicMock()
_genai_types.ThinkingConfig = MagicMock()
_google.genai = _genai
sys.modules["google"] = _google
sys.modules["google.genai"] = _genai
sys.modules["google.genai.types"] = _genai_types


for mod in ["db.session"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


from services.ai_trend_analysis.autonomous_orchestrator import (
    AgentPhase,
    MarketSignal,
    MarketAssessment,
    PricingDecision,
    AgentStreamEvent,
    handle_tool_call,
    _handle_fetch_competitor_price,
    _handle_detect_price_change,
    _handle_analyze_sentiment,
    _handle_calculate_elasticity,
    _handle_assess_risk,
    _handle_calculate_optimal_price,
    _handle_write_price_to_chain,
    AutonomousOrchestrator,
    AutonomousTrigger,
)


# ==================================================================
# Enums
# ==================================================================

class TestAgentPhase:
    def test_scout(self):
        assert AgentPhase.SCOUT == "scout"

    def test_analyst(self):
        assert AgentPhase.ANALYST == "analyst"

    def test_strategist(self):
        assert AgentPhase.STRATEGIST == "strategist"

    def test_execution(self):
        assert AgentPhase.EXECUTION == "execution"

    def test_is_str_enum(self):
        assert isinstance(AgentPhase.SCOUT, str)


# ==================================================================
# Pydantic Schemas
# ==================================================================

class TestMarketSignal:
    def test_basic_creation(self):
        sig = MarketSignal(
            competitor_name="Amazon",
            competitor_price=89.99,
            price_change_pct=-15.0,
            signal_type="price_drop",
            product_category="electronics",
            source="google_search",
            confidence=0.85,
        )
        assert sig.competitor_name == "Amazon"
        assert sig.competitor_price == 89.99
        assert sig.confidence == 0.85

    def test_defaults(self):
        sig = MarketSignal(
            competitor_name="X",
            competitor_price=10.0,
            price_change_pct=0.0,
            signal_type="stable",
            product_category="toys",
            source="api",
            confidence=0.5,
        )
        assert sig.raw_data == {}
        assert sig.timestamp is not None

    def test_confidence_bounds(self):
        sig = MarketSignal(
            competitor_name="X",
            competitor_price=10.0,
            price_change_pct=0.0,
            signal_type="stable",
            product_category="toys",
            source="api",
            confidence=0.0,
        )
        assert sig.confidence == 0.0

    def test_json_serializable(self):
        sig = MarketSignal(
            competitor_name="Test",
            competitor_price=50.0,
            price_change_pct=-5.0,
            signal_type="price_drop",
            product_category="electronics",
            source="scraper",
            confidence=0.9,
        )
        data = json.loads(sig.model_dump_json())
        assert data["competitor_name"] == "Test"


class TestMarketAssessment:
    def test_basic_creation(self):
        a = MarketAssessment(
            sentiment_score=-0.42,
            sentiment_label="bearish",
            demand_elasticity=-1.8,
            risk_level="medium",
            opportunity_score=0.65,
            market_context="Market is bearish",
            recommended_direction="decrease",
            max_safe_change_pct=15.0,
        )
        assert a.sentiment_score == -0.42
        assert a.recommended_direction == "decrease"

    def test_defaults(self):
        a = MarketAssessment(
            sentiment_score=0.0,
            sentiment_label="neutral",
            demand_elasticity=-1.0,
            risk_level="low",
            opportunity_score=0.5,
            market_context="Stable",
            recommended_direction="hold",
            max_safe_change_pct=5.0,
        )
        assert a.risk_factors == []

    def test_json_serializable(self):
        a = MarketAssessment(
            sentiment_score=0.5,
            sentiment_label="bullish",
            demand_elasticity=-0.5,
            risk_level="low",
            opportunity_score=0.8,
            market_context="Strong demand",
            recommended_direction="increase",
            max_safe_change_pct=10.0,
        )
        data = json.loads(a.model_dump_json())
        assert data["sentiment_label"] == "bullish"


class TestPricingDecision:
    def test_basic_creation(self):
        d = PricingDecision(
            recommended_price=87.99,
            current_price=99.99,
            change_pct=-12.0,
            confidence_score=0.87,
            reasoning="Price drop needed",
            action="execute",
            risk_acknowledgment="Competitor undercut",
            expected_revenue_impact="9.6% volume increase",
        )
        assert d.recommended_price == 87.99
        assert d.action == "execute"

    def test_optional_defaults(self):
        d = PricingDecision(
            recommended_price=50.0,
            current_price=50.0,
            change_pct=0.0,
            confidence_score=0.5,
            reasoning="Hold",
            action="hold",
            risk_acknowledgment="None",
            expected_revenue_impact="None",
        )
        assert d.tx_hash is None
        assert d.executed_at is None

    def test_with_tx_hash(self):
        d = PricingDecision(
            recommended_price=87.99,
            current_price=99.99,
            change_pct=-12.0,
            confidence_score=0.87,
            reasoning="Execute",
            action="execute",
            risk_acknowledgment="Known",
            expected_revenue_impact="Positive",
            tx_hash="0xabc123",
            executed_at="2026-02-08T12:00:00Z",
        )
        assert d.tx_hash == "0xabc123"


class TestAgentStreamEvent:
    def test_basic_creation(self):
        e = AgentStreamEvent(
            agent="scout",
            phase="starting",
            content="Scanning...",
        )
        assert e.agent == "scout"
        assert e.is_complete is False
        assert e.data is None
        assert e.timestamp is not None

    def test_complete_event(self):
        e = AgentStreamEvent(
            agent="strategist",
            phase="complete",
            content="Done",
            is_complete=True,
            data={"price": 87.99},
        )
        assert e.is_complete is True
        assert e.data["price"] == 87.99

    def test_json_serializable(self):
        e = AgentStreamEvent(agent="analyst", phase="starting", content="Analyzing")
        data = json.loads(e.model_dump_json())
        assert data["agent"] == "analyst"


# ==================================================================
# Tool Handlers
# ==================================================================

class TestHandleToolCall:
    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        result = await handle_tool_call("nonexistent_tool", {})
        assert "error" in result
        assert "Unknown tool" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatches_to_correct_handler(self):
        result = await handle_tool_call("fetch_competitor_price", {"product_category": "electronics"})
        assert "competitor_name" in result
        assert "current_price" in result


class TestFetchCompetitorPrice:
    @pytest.mark.asyncio
    async def test_returns_price_data(self):
        result = await _handle_fetch_competitor_price({"product_category": "electronics"})
        assert result["competitor_name"] == "CompetitorX"
        assert result["current_price"] == 89.99
        assert result["previous_price"] == 105.99
        assert "last_updated" in result

    @pytest.mark.asyncio
    async def test_uses_provided_category(self):
        result = await _handle_fetch_competitor_price({"product_category": "toys"})
        assert result["product"] == "toys"


class TestDetectPriceChange:
    @pytest.mark.asyncio
    async def test_price_drop(self):
        result = await _handle_detect_price_change({
            "current_price": 80.0,
            "last_known_price": 100.0,
            "product_id": "test",
        })
        assert result["change_detected"] is True
        assert result["change_pct"] == -20.0
        assert result["signal_type"] == "price_drop"
        assert result["significance"] == "high"

    @pytest.mark.asyncio
    async def test_price_increase(self):
        result = await _handle_detect_price_change({
            "current_price": 110.0,
            "last_known_price": 100.0,
            "product_id": "test",
        })
        assert result["change_detected"] is True
        assert result["signal_type"] == "price_increase"

    @pytest.mark.asyncio
    async def test_stable_price(self):
        result = await _handle_detect_price_change({
            "current_price": 100.0,
            "last_known_price": 100.0,
            "product_id": "test",
        })
        assert result["change_detected"] is False
        assert result["signal_type"] == "stable"

    @pytest.mark.asyncio
    async def test_zero_last_known_price(self):
        result = await _handle_detect_price_change({
            "current_price": 50.0,
            "last_known_price": 0,
            "product_id": "test",
        })
        assert result["change_pct"] == 0

    @pytest.mark.asyncio
    async def test_medium_significance(self):
        result = await _handle_detect_price_change({
            "current_price": 93.0,
            "last_known_price": 100.0,
            "product_id": "test",
        })
        assert result["significance"] == "medium"

    @pytest.mark.asyncio
    async def test_low_significance(self):
        result = await _handle_detect_price_change({
            "current_price": 97.0,
            "last_known_price": 100.0,
            "product_id": "test",
        })
        assert result["significance"] == "low"


class TestAnalyzeSentiment:
    @pytest.mark.asyncio
    async def test_returns_sentiment_data(self):
        result = await _handle_analyze_sentiment({"product_category": "electronics"})
        assert result["sentiment_score"] == -0.42
        assert result["sentiment_label"] == "bearish"
        assert "platforms" in result
        assert "top_keywords" in result

    @pytest.mark.asyncio
    async def test_default_timeframe(self):
        result = await _handle_analyze_sentiment({})
        assert result["timeframe_hours"] == 24

    @pytest.mark.asyncio
    async def test_custom_timeframe(self):
        result = await _handle_analyze_sentiment({"timeframe_hours": 48})
        assert result["timeframe_hours"] == 48


class TestCalculateElasticity:
    @pytest.mark.asyncio
    async def test_returns_elasticity_data(self):
        result = await _handle_calculate_elasticity({"product_id": "test"})
        assert result["elasticity_coefficient"] == -1.8
        assert result["interpretation"] == "elastic_demand"
        assert "optimal_range" in result


class TestAssessRisk:
    @pytest.mark.asyncio
    async def test_returns_risk_assessment(self):
        result = await _handle_assess_risk({"signal": {}, "sentiment_score": -0.5})
        assert result["risk_level"] == "medium"
        assert len(result["risk_factors"]) > 0
        assert "mitigation" in result


class TestCalculateOptimalPrice:
    @pytest.mark.asyncio
    async def test_decrease_direction(self):
        result = await _handle_calculate_optimal_price({
            "current_price": 100.0,
            "assessment": {"recommended_direction": "decrease"},
        })
        assert result["optimal_price"] == 88.0  # 100 * 0.88
        assert result["change_pct"] < 0

    @pytest.mark.asyncio
    async def test_increase_direction(self):
        result = await _handle_calculate_optimal_price({
            "current_price": 100.0,
            "assessment": {"recommended_direction": "increase"},
        })
        assert result["optimal_price"] == 105.0  # 100 * 1.05
        assert result["change_pct"] > 0

    @pytest.mark.asyncio
    async def test_hold_direction(self):
        result = await _handle_calculate_optimal_price({
            "current_price": 100.0,
            "assessment": {"recommended_direction": "hold"},
        })
        assert result["optimal_price"] == 100.0
        assert result["change_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_default_price(self):
        result = await _handle_calculate_optimal_price({
            "assessment": {"recommended_direction": "hold"},
        })
        assert result["optimal_price"] == 99.99


class TestWritePriceToChain:
    @pytest.mark.asyncio
    async def test_returns_tx_data(self):
        result = await _handle_write_price_to_chain({
            "product_id": "test",
            "new_price": 87.99,
            "confidence": 0.87,
        })
        assert result["success"] is True
        assert result["tx_hash"].startswith("0x")
        assert result["chain"] == "BNB Chain Testnet"
        assert "block_number" in result
        assert "executed_at" in result
        assert "explorer_url" in result


# ==================================================================
# AutonomousOrchestrator
# ==================================================================

class TestOrchestratorInit:
    def test_creates_with_defaults(self):
        with patch("services.ai_trend_analysis.autonomous_orchestrator.client"):
            orch = AutonomousOrchestrator()
            assert orch.model is not None
            assert orch._reasoning_log == []


class TestSSEEvent:
    def test_format(self):
        result = AutonomousOrchestrator._sse_event("scout", "starting", "Scanning...")
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        parsed = json.loads(result.replace("data: ", "").strip())
        assert parsed["agent"] == "scout"
        assert parsed["phase"] == "starting"
        assert parsed["content"] == "Scanning..."
        assert parsed["is_complete"] is False

    def test_complete_event(self):
        result = AutonomousOrchestrator._sse_event("analyst", "complete", "Done", is_complete=True)
        parsed = json.loads(result.replace("data: ", "").strip())
        assert parsed["is_complete"] is True


class TestRunScout:
    @pytest.mark.asyncio
    async def test_returns_market_signal(self):
        orch = AutonomousOrchestrator()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "competitor_name": "TestComp",
            "competitor_price": 79.99,
            "price_change_pct": -10.0,
            "signal_type": "price_drop",
            "product_category": "electronics",
            "source": "google_search",
            "confidence": 0.9,
        })
        orch.client = MagicMock()
        orch.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await orch._run_scout("prod-1", "electronics")
        assert isinstance(result, MarketSignal)
        assert result.competitor_name == "TestComp"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_fallback_on_parse_error(self):
        orch = AutonomousOrchestrator()
        mock_response = MagicMock()
        mock_response.text = "not valid json"
        orch.client = MagicMock()
        orch.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        result = await orch._run_scout("prod-1", "electronics")
        assert isinstance(result, MarketSignal)
        # Should return fallback values
        assert result.competitor_name == "CompetitorX"
        assert result.product_category == "electronics"


class TestRunAnalyst:
    @pytest.mark.asyncio
    async def test_returns_market_assessment(self):
        orch = AutonomousOrchestrator()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "sentiment_score": -0.5,
            "sentiment_label": "bearish",
            "demand_elasticity": -2.0,
            "risk_level": "high",
            "risk_factors": ["Competitor undercut"],
            "opportunity_score": 0.7,
            "market_context": "Bearish",
            "recommended_direction": "decrease",
            "max_safe_change_pct": 12.0,
        })
        orch.client = MagicMock()
        orch.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = MarketSignal(
            competitor_name="X", competitor_price=80.0, price_change_pct=-10.0,
            signal_type="price_drop", product_category="electronics",
            source="api", confidence=0.8,
        )
        result = await orch._run_analyst(signal)
        assert isinstance(result, MarketAssessment)
        assert result.sentiment_score == -0.5
        assert result.recommended_direction == "decrease"

    @pytest.mark.asyncio
    async def test_fallback_on_parse_error(self):
        orch = AutonomousOrchestrator()
        mock_response = MagicMock()
        mock_response.text = "bad json"
        orch.client = MagicMock()
        orch.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = MarketSignal(
            competitor_name="X", competitor_price=80.0, price_change_pct=-10.0,
            signal_type="price_drop", product_category="electronics",
            source="api", confidence=0.8,
        )
        result = await orch._run_analyst(signal)
        assert isinstance(result, MarketAssessment)
        assert result.sentiment_label == "bearish"


class TestRunStrategist:
    @pytest.mark.asyncio
    async def test_returns_pricing_decision(self):
        orch = AutonomousOrchestrator()
        mock_response = MagicMock()
        mock_response.text = "Recommending 12% decrease based on market analysis"
        mock_response.candidates = []
        orch.client = MagicMock()
        orch.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = MarketSignal(
            competitor_name="X", competitor_price=80.0, price_change_pct=-15.0,
            signal_type="price_drop", product_category="electronics",
            source="api", confidence=0.85,
        )
        assessment = MarketAssessment(
            sentiment_score=-0.42, sentiment_label="bearish",
            demand_elasticity=-1.8, risk_level="medium",
            risk_factors=["Competitor undercut"],
            opportunity_score=0.65, market_context="Bearish market",
            recommended_direction="decrease", max_safe_change_pct=15.0,
        )

        result = await orch._run_strategist(
            signal, assessment,
            current_price=99.99, cost_basis=45.0,
            margin_floor_pct=20.0, product_id="prod-1",
        )
        assert isinstance(result, PricingDecision)
        assert result.recommended_price < result.current_price
        assert result.action == "execute"
        assert result.tx_hash is not None

    @pytest.mark.asyncio
    async def test_hold_direction_no_execution(self):
        orch = AutonomousOrchestrator()
        mock_response = MagicMock()
        mock_response.text = "Holding price steady"
        mock_response.candidates = []
        orch.client = MagicMock()
        orch.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = MarketSignal(
            competitor_name="X", competitor_price=100.0, price_change_pct=0.0,
            signal_type="stable", product_category="electronics",
            source="api", confidence=0.5,
        )
        assessment = MarketAssessment(
            sentiment_score=0.0, sentiment_label="neutral",
            demand_elasticity=-1.0, risk_level="low",
            risk_factors=[],
            opportunity_score=0.3, market_context="Stable",
            recommended_direction="hold", max_safe_change_pct=5.0,
        )

        result = await orch._run_strategist(
            signal, assessment,
            current_price=99.99, cost_basis=45.0,
            margin_floor_pct=20.0, product_id="prod-1",
        )
        assert result.action == "hold"
        assert result.change_pct == 0.0

    @pytest.mark.asyncio
    async def test_function_call_execution(self):
        """When Gemini makes a write_price_to_chain function call."""
        orch = AutonomousOrchestrator()

        # Build mock response with function call
        fc_part = MagicMock()
        fc_part.function_call = MagicMock()
        fc_part.function_call.name = "write_price_to_chain"
        fc_part.function_call.args = {
            "product_id": "prod-1",
            "new_price": 87.99,
            "confidence": 0.87,
        }

        text_part = MagicMock()
        text_part.function_call = None
        text_part.text = "Executing price change"

        mock_response = MagicMock()
        mock_response.text = "Executing price change"
        candidate = MagicMock()
        candidate.content.parts = [text_part, fc_part]
        mock_response.candidates = [candidate]

        orch.client = MagicMock()
        orch.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        signal = MarketSignal(
            competitor_name="X", competitor_price=80.0, price_change_pct=-15.0,
            signal_type="price_drop", product_category="electronics",
            source="api", confidence=0.85,
        )
        assessment = MarketAssessment(
            sentiment_score=-0.42, sentiment_label="bearish",
            demand_elasticity=-1.8, risk_level="medium",
            risk_factors=["Undercut"],
            opportunity_score=0.65, market_context="Bearish",
            recommended_direction="decrease", max_safe_change_pct=15.0,
        )

        result = await orch._run_strategist(
            signal, assessment,
            current_price=99.99, cost_basis=45.0,
            margin_floor_pct=20.0, product_id="prod-1",
        )
        assert result.tx_hash is not None
        assert result.action == "execute"


class TestRunPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        orch = AutonomousOrchestrator()
        orch._run_scout = AsyncMock(return_value=MarketSignal(
            competitor_name="X", competitor_price=80.0, price_change_pct=-15.0,
            signal_type="price_drop", product_category="electronics",
            source="api", confidence=0.85,
        ))
        orch._run_analyst = AsyncMock(return_value=MarketAssessment(
            sentiment_score=-0.42, sentiment_label="bearish",
            demand_elasticity=-1.8, risk_level="medium",
            risk_factors=[],
            opportunity_score=0.65, market_context="Bearish",
            recommended_direction="decrease", max_safe_change_pct=15.0,
        ))
        orch._run_strategist = AsyncMock(return_value=PricingDecision(
            recommended_price=87.99, current_price=99.99,
            change_pct=-12.0, confidence_score=0.87,
            reasoning="Decrease needed", action="execute",
            risk_acknowledgment="Known", expected_revenue_impact="Positive",
            tx_hash="0xabc", executed_at="2026-02-08T12:00:00Z",
        ))

        result = await orch.run_pipeline("prod-1")
        assert isinstance(result, PricingDecision)
        assert result.recommended_price == 87.99
        orch._run_scout.assert_awaited_once()
        orch._run_analyst.assert_awaited_once()
        orch._run_strategist.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_params_through(self):
        orch = AutonomousOrchestrator()
        orch._run_scout = AsyncMock(return_value=MarketSignal(
            competitor_name="X", competitor_price=80.0, price_change_pct=0,
            signal_type="stable", product_category="toys",
            source="api", confidence=0.5,
        ))
        orch._run_analyst = AsyncMock(return_value=MarketAssessment(
            sentiment_score=0, sentiment_label="neutral",
            demand_elasticity=-1.0, risk_level="low", risk_factors=[],
            opportunity_score=0.3, market_context="Stable",
            recommended_direction="hold", max_safe_change_pct=5.0,
        ))
        orch._run_strategist = AsyncMock(return_value=PricingDecision(
            recommended_price=50.0, current_price=50.0,
            change_pct=0, confidence_score=0.5,
            reasoning="Hold", action="hold",
            risk_acknowledgment="None", expected_revenue_impact="None",
        ))

        await orch.run_pipeline(
            product_id="prod-2",
            current_price=50.0,
            product_category="toys",
            cost_basis=20.0,
            margin_floor_pct=30.0,
        )
        orch._run_scout.assert_awaited_with("prod-2", "toys")


class TestRunPipelineStreaming:
    @pytest.mark.asyncio
    async def test_yields_sse_events(self):
        orch = AutonomousOrchestrator()
        orch._run_scout = AsyncMock(return_value=MarketSignal(
            competitor_name="X", competitor_price=80.0, price_change_pct=-15.0,
            signal_type="price_drop", product_category="electronics",
            source="api", confidence=0.85,
        ))
        orch._run_analyst = AsyncMock(return_value=MarketAssessment(
            sentiment_score=-0.42, sentiment_label="bearish",
            demand_elasticity=-1.8, risk_level="medium", risk_factors=[],
            opportunity_score=0.65, market_context="Bearish",
            recommended_direction="decrease", max_safe_change_pct=15.0,
        ))
        orch._run_strategist = AsyncMock(return_value=PricingDecision(
            recommended_price=87.99, current_price=99.99,
            change_pct=-12.0, confidence_score=0.87,
            reasoning="Decrease", action="execute",
            risk_acknowledgment="Known", expected_revenue_impact="Positive",
            tx_hash="0xabc", executed_at="2026-02-08T12:00:00Z",
        ))

        events = []
        async for event in orch.run_pipeline_streaming("prod-1"):
            events.append(event)

        assert len(events) > 0
        assert all(e.startswith("data: ") for e in events)
        # Should have scout, analyst, strategist, execution, pipeline events
        all_text = " ".join(events)
        assert "scout" in all_text
        assert "analyst" in all_text
        assert "strategist" in all_text

    @pytest.mark.asyncio
    async def test_error_yields_error_event(self):
        orch = AutonomousOrchestrator()
        orch._run_scout = AsyncMock(side_effect=Exception("API timeout"))

        events = []
        async for event in orch.run_pipeline_streaming("prod-1"):
            events.append(event)

        assert any("error" in e for e in events)


# ==================================================================
# AutonomousTrigger
# ==================================================================

class TestAutonomousTrigger:
    def test_init(self):
        trigger = AutonomousTrigger()
        assert trigger.orchestrator is not None
        assert trigger._is_running is False

    def test_stop_monitoring(self):
        trigger = AutonomousTrigger()
        trigger._is_running = True
        trigger.stop_monitoring()
        assert trigger._is_running is False

    @pytest.mark.asyncio
    async def test_start_monitoring_runs_pipeline(self):
        trigger = AutonomousTrigger()
        call_count = 0

        async def mock_pipeline(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            trigger.stop_monitoring()  # Stop after first iteration
            return PricingDecision(
                recommended_price=87.99, current_price=99.99,
                change_pct=-12.0, confidence_score=0.87,
                reasoning="Test", action="execute",
                risk_acknowledgment="None", expected_revenue_impact="Positive",
                tx_hash="0xabc", executed_at="2026-02-08T12:00:00Z",
            )

        trigger.orchestrator.run_pipeline = mock_pipeline

        # Use very short interval and stop quickly
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await trigger.start_monitoring(
                "prod-1",
                check_interval_seconds=0,
                current_price=99.99,
            )

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_updates_price_on_execute(self):
        trigger = AutonomousTrigger()
        prices_seen = []
        call_count = 0

        async def mock_pipeline(product_id, current_price=99.99, **kwargs):
            nonlocal call_count
            prices_seen.append(current_price)
            call_count += 1
            if call_count >= 2:
                trigger.stop_monitoring()
            return PricingDecision(
                recommended_price=87.99, current_price=current_price,
                change_pct=-12.0, confidence_score=0.87,
                reasoning="Test", action="execute",
                risk_acknowledgment="None", expected_revenue_impact="Positive",
                tx_hash="0xabc", executed_at="2026-02-08T12:00:00Z",
            )

        trigger.orchestrator.run_pipeline = mock_pipeline

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await trigger.start_monitoring(
                "prod-1",
                check_interval_seconds=0,
                current_price=99.99,
            )

        assert prices_seen[0] == 99.99
        assert prices_seen[1] == 87.99  # Updated after first execution

    @pytest.mark.asyncio
    async def test_recovers_from_error(self):
        trigger = AutonomousTrigger()
        call_count = 0

        async def mock_pipeline(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Transient error")
            trigger.stop_monitoring()
            return PricingDecision(
                recommended_price=99.99, current_price=99.99,
                change_pct=0, confidence_score=0.5,
                reasoning="Hold", action="hold",
                risk_acknowledgment="None", expected_revenue_impact="None",
            )

        trigger.orchestrator.run_pipeline = mock_pipeline

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await trigger.start_monitoring(
                "prod-1",
                check_interval_seconds=0,
                current_price=99.99,
            )

        assert call_count == 2  # Recovered and ran again


        