"""
Tests for services/ai_trend_analysis/visual_pricing_analyzer.py

Covers:
- Enums: AgentRole
- Dataclasses: AgentMessage, ProductInfo, PricingRecommendation
- VisualPricingAnalyzer:
  - __init__
  - _parse_recommendation (JSON code block, generic block, raw JSON regex, no JSON fallback, zero price)
  - run_scout_agent (streaming + structured extraction)
  - run_analyst_agent (price differential calc, position classification, error handling)
  - run_strategist_agent (streaming + parsed recommendation)
  - analyze (full orchestration, scout failure early exit)
"""

import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
for mod in ["db.session", "google.genai", "google.genai.types"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
mock_settings = MagicMock()
mock_settings.OPENAI_API_KEY = "test"
mock_settings.GEMINI_API_KEY = "test"

from services.ai_trend_analysis.ai_clients import (
    ImageAnalysisResult,
    StreamChunk,
    ThoughtType,
)
from services.ai_trend_analysis.visual_analyzer import (
    AgentMessage,
    AgentRole,
    PricingRecommendation,
    ProductInfo,
    VisualPricingAnalyzer,
)

# ── Helpers ───────────────────────────────────────────────────────


def _make_product(**overrides):
    defaults = dict(
        name="Widget Pro",
        price=Decimal("29.99"),
        currency="USD",
        features=["Fast", "Durable"],
        source="manual",
    )
    defaults.update(overrides)
    return ProductInfo(**defaults)


def _make_competitor_data(**overrides):
    defaults = dict(
        product_name="CompetitorWidget",
        price="$24.99",
        currency="USD",
        features=["Light", "Cheap"],
        promo_signals=["20% OFF"],
        confidence=0.9,
    )
    defaults.update(overrides)
    return defaults


# ==================================================================
# Enums
# ==================================================================


class TestAgentRole:
    def test_scout(self):
        assert AgentRole.SCOUT == "scout"

    def test_analyst(self):
        assert AgentRole.ANALYST == "analyst"

    def test_strategist(self):
        assert AgentRole.STRATEGIST == "strategist"

    def test_is_str(self):
        assert isinstance(AgentRole.SCOUT, str)


# ==================================================================
# Dataclasses
# ==================================================================


class TestAgentMessage:
    def test_basic(self):
        msg = AgentMessage(
            agent=AgentRole.SCOUT,
            thought_type=ThoughtType.OBSERVATION,
            content="Scanning...",
        )
        assert msg.agent == AgentRole.SCOUT
        assert msg.is_final is False
        assert msg.metadata == {}

    def test_final_with_metadata(self):
        msg = AgentMessage(
            agent=AgentRole.ANALYST,
            thought_type=ThoughtType.DECISION,
            content="Done",
            is_final=True,
            metadata={"key": "val"},
        )
        assert msg.is_final is True
        assert msg.metadata["key"] == "val"

    def test_separate_metadata_dicts(self):
        m1 = AgentMessage(agent=AgentRole.SCOUT, thought_type=None, content="a")
        m2 = AgentMessage(agent=AgentRole.SCOUT, thought_type=None, content="b")
        assert m1.metadata is not m2.metadata


class TestProductInfo:
    def test_defaults(self):
        p = ProductInfo(name="X", price=Decimal("10.00"))
        assert p.currency == "USD"
        assert p.features == []
        assert p.reviews_summary is None
        assert p.promo_signals == []
        assert p.source == "manual"

    def test_full(self):
        p = ProductInfo(
            name="Y",
            price=Decimal("50.00"),
            currency="EUR",
            features=["A"],
            reviews_summary="Good",
            promo_signals=["SALE"],
            source="screenshot",
        )
        assert p.currency == "EUR"
        assert p.source == "screenshot"

    def test_separate_default_lists(self):
        p1 = ProductInfo(name="A", price=Decimal("1"))
        p2 = ProductInfo(name="B", price=Decimal("2"))
        assert p1.features is not p2.features
        assert p1.promo_signals is not p2.promo_signals


class TestPricingRecommendation:
    def test_basic(self):
        r = PricingRecommendation(
            recommended_price=Decimal("27.99"),
            confidence=0.85,
            reasoning="Lower to match",
            price_change_percent=-6.7,
            strategy="decrease",
            risk_level="low",
        )
        assert r.recommended_price == Decimal("27.99")
        assert r.key_factors == []
        assert r.alternative_prices == []

    def test_separate_default_lists(self):
        r1 = PricingRecommendation(
            recommended_price=Decimal("10"),
            confidence=0.5,
            reasoning="x",
            price_change_percent=0,
            strategy="maintain",
            risk_level="low",
        )
        r2 = PricingRecommendation(
            recommended_price=Decimal("10"),
            confidence=0.5,
            reasoning="x",
            price_change_percent=0,
            strategy="maintain",
            risk_level="low",
        )
        assert r1.key_factors is not r2.key_factors


# ==================================================================
# __init__
# ==================================================================


class TestInit:
    def test_model_set(self):
        analyzer = VisualPricingAnalyzer()
        assert analyzer.model is not None


# ==================================================================
# _parse_recommendation
# ==================================================================


class TestParseRecommendation:
    def setup_method(self):
        self.analyzer = VisualPricingAnalyzer()
        self.product = _make_product()

    def test_json_code_block(self):
        response = 'Analysis:\n```json\n{"recommended_price": 27.99, "confidence": 0.9, "strategy": "decrease", "risk_level": "low", "key_factors": ["competition"]}\n```'
        result = self.analyzer._parse_recommendation(response, self.product)
        assert result.recommended_price == Decimal("27.99")
        assert result.confidence == 0.9
        assert result.strategy == "decrease"
        assert result.risk_level == "low"
        assert "competition" in result.key_factors

    def test_generic_code_block(self):
        response = 'Strategy:\n```\n{"recommended_price": 32.00, "strategy": "increase"}\n```'
        result = self.analyzer._parse_recommendation(response, self.product)
        assert result.recommended_price == Decimal("32.00")
        assert result.strategy == "increase"

    def test_raw_json_regex(self):
        response = 'My recommendation is {"recommended_price": 29.99, "confidence": 0.8} based on analysis.'
        result = self.analyzer._parse_recommendation(response, self.product)
        assert result.recommended_price == Decimal("29.99")
        assert result.confidence == 0.8

    def test_no_json_returns_fallback(self):
        response = "No structured data here."
        result = self.analyzer._parse_recommendation(response, self.product)
        assert result.recommended_price == self.product.price
        assert result.confidence == 0.3
        assert result.strategy == "maintain"
        assert result.price_change_percent == 0

    def test_change_percent_calculated(self):
        response = '```json\n{"recommended_price": 35.99}\n```'
        result = self.analyzer._parse_recommendation(response, self.product)
        expected_pct = float((Decimal("35.99") - Decimal("29.99")) / Decimal("29.99") * 100)
        assert abs(result.price_change_percent - expected_pct) < 0.1

    def test_zero_current_price(self):
        product = _make_product(price=Decimal("0"))
        response = '```json\n{"recommended_price": 10.00}\n```'
        result = self.analyzer._parse_recommendation(response, product)
        assert result.price_change_percent == 0

    def test_invalid_json_returns_fallback(self):
        response = "```json\n{broken json\n```"
        result = self.analyzer._parse_recommendation(response, self.product)
        assert result.recommended_price == self.product.price
        assert result.confidence == 0.3

    def test_missing_fields_use_defaults(self):
        response = '```json\n{"recommended_price": 25.00}\n```'
        result = self.analyzer._parse_recommendation(response, self.product)
        assert result.confidence == 0.5
        assert result.strategy == "maintain"
        assert result.risk_level == "medium"
        assert result.key_factors == []


# ==================================================================
# run_scout_agent
# ==================================================================


class TestRunScoutAgent:
    @pytest.mark.asyncio
    async def test_yields_messages(self):
        analyzer = VisualPricingAnalyzer()

        async def mock_image_stream(*args, **kwargs):
            yield StreamChunk(text="Scanning product page", thought_type=ThoughtType.OBSERVATION)
            yield StreamChunk(text="", is_final=True)

        mock_structured = ImageAnalysisResult(
            product_name="CompWidget",
            price="$24.99",
            currency="USD",
            features=["Light"],
            promo_signals=[],
            confidence=0.9,
        )

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.analyze_image_stream = mock_image_stream
            mock_ai.analyze_image = AsyncMock(return_value=mock_structured)

            messages = []
            async for msg in analyzer.run_scout_agent(b"fake_img", "png"):
                messages.append(msg)

        assert len(messages) >= 2  # opening + content + final
        assert messages[0].agent == AgentRole.SCOUT
        assert messages[-1].is_final is True
        assert "extracted_data" in messages[-1].metadata
        assert messages[-1].metadata["extracted_data"]["product_name"] == "CompWidget"

    @pytest.mark.asyncio
    async def test_opening_message_is_observation(self):
        analyzer = VisualPricingAnalyzer()

        async def mock_image_stream(*args, **kwargs):
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.analyze_image_stream = mock_image_stream
            mock_ai.analyze_image = AsyncMock(return_value=ImageAnalysisResult())

            messages = []
            async for msg in analyzer.run_scout_agent(b"img", "png"):
                messages.append(msg)

        assert messages[0].thought_type == ThoughtType.OBSERVATION


# ==================================================================
# run_analyst_agent
# ==================================================================


class TestRunAnalystAgent:
    @pytest.mark.asyncio
    async def test_yields_messages_with_analysis(self):
        analyzer = VisualPricingAnalyzer()
        product = _make_product()
        comp_data = _make_competitor_data()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="Comparing products", thought_type=ThoughtType.ANALYSIS)
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_analyst_agent(product, comp_data):
                messages.append(msg)

        assert len(messages) >= 2
        assert messages[0].agent == AgentRole.ANALYST
        final = messages[-1]
        assert final.is_final is True
        assert "analysis" in final.metadata

    @pytest.mark.asyncio
    async def test_premium_position(self):
        """Your product more expensive → premium."""
        analyzer = VisualPricingAnalyzer()
        product = _make_product(price=Decimal("50.00"))
        comp_data = _make_competitor_data(price="$24.99")

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_analyst_agent(product, comp_data):
                messages.append(msg)

        final = messages[-1]
        assert final.metadata["analysis"]["market_position"] == "premium"

    @pytest.mark.asyncio
    async def test_discount_position(self):
        """Your product cheaper → discount."""
        analyzer = VisualPricingAnalyzer()
        product = _make_product(price=Decimal("20.00"))
        comp_data = _make_competitor_data(price="$30.00")

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_analyst_agent(product, comp_data):
                messages.append(msg)

        final = messages[-1]
        assert final.metadata["analysis"]["market_position"] == "discount"

    @pytest.mark.asyncio
    async def test_competitive_position(self):
        """Similar price → competitive."""
        analyzer = VisualPricingAnalyzer()
        product = _make_product(price=Decimal("30.00"))
        comp_data = _make_competitor_data(price="$29.50")

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_analyst_agent(product, comp_data):
                messages.append(msg)

        final = messages[-1]
        assert final.metadata["analysis"]["market_position"] == "competitive"

    @pytest.mark.asyncio
    async def test_zero_competitor_price(self):
        analyzer = VisualPricingAnalyzer()
        product = _make_product()
        comp_data = _make_competitor_data(price="$0")

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_analyst_agent(product, comp_data):
                messages.append(msg)

        final = messages[-1]
        assert final.metadata["analysis"]["market_position"] == "unknown"

    @pytest.mark.asyncio
    async def test_unparseable_competitor_price(self):
        analyzer = VisualPricingAnalyzer()
        product = _make_product()
        comp_data = _make_competitor_data(price="FREE")

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_analyst_agent(product, comp_data):
                messages.append(msg)

        final = messages[-1]
        assert final.metadata["analysis"]["market_position"] == "unknown"


# ==================================================================
# run_strategist_agent
# ==================================================================


class TestRunStrategistAgent:
    @pytest.mark.asyncio
    async def test_yields_messages_with_recommendation(self):
        analyzer = VisualPricingAnalyzer()
        product = _make_product()
        comp_data = _make_competitor_data()
        analysis = {"market_position": "premium", "price_differential_percent": 20.0}

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(
                text='```json\n{"recommended_price": 27.99, "confidence": 0.85, "strategy": "decrease", "risk_level": "low", "key_factors": ["competition"]}\n```',
                thought_type=ThoughtType.RECOMMENDATION,
            )
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_strategist_agent(product, comp_data, analysis):
                messages.append(msg)

        assert len(messages) >= 2
        assert messages[0].agent == AgentRole.STRATEGIST
        final = messages[-1]
        assert final.is_final is True
        assert "recommendation" in final.metadata
        assert final.metadata["recommendation"]["recommended_price"] == 27.99

    @pytest.mark.asyncio
    async def test_fallback_recommendation_on_bad_json(self):
        analyzer = VisualPricingAnalyzer()
        product = _make_product()

        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="No JSON here", thought_type=ThoughtType.RECOMMENDATION)
            yield StreamChunk(text="", is_final=True)

        with patch("services.ai_trend_analysis.visual_analyzer.ai_clients") as mock_ai:
            mock_ai.stream_gemini3 = mock_stream

            messages = []
            async for msg in analyzer.run_strategist_agent(product, {}, {}):
                messages.append(msg)

        final = messages[-1]
        rec = final.metadata["recommendation"]
        assert rec["recommended_price"] == float(product.price)
        assert rec["confidence"] == 0.3
        assert rec["strategy"] == "maintain"


# ==================================================================
# analyze (full orchestration)
# ==================================================================


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_runs_all_three_agents(self):
        analyzer = VisualPricingAnalyzer()

        # Mock scout
        async def mock_scout(*args, **kwargs):
            yield AgentMessage(
                AgentRole.SCOUT,
                ThoughtType.OBSERVATION,
                "Scanning...",
            )
            yield AgentMessage(
                AgentRole.SCOUT,
                ThoughtType.DECISION,
                "Done",
                is_final=True,
                metadata={"extracted_data": _make_competitor_data()},
            )

        # Mock analyst
        async def mock_analyst(*args, **kwargs):
            yield AgentMessage(
                AgentRole.ANALYST,
                ThoughtType.ANALYSIS,
                "Comparing...",
            )
            yield AgentMessage(
                AgentRole.ANALYST,
                ThoughtType.DECISION,
                "Done",
                is_final=True,
                metadata={"analysis": {"market_position": "competitive", "price_differential_percent": 2.0}},
            )

        # Mock strategist
        async def mock_strategist(*args, **kwargs):
            yield AgentMessage(
                AgentRole.STRATEGIST,
                ThoughtType.RECOMMENDATION,
                "Recommending...",
            )
            yield AgentMessage(
                AgentRole.STRATEGIST,
                ThoughtType.RECOMMENDATION,
                "Done",
                is_final=True,
                metadata={"recommendation": {"recommended_price": 29.99}},
            )

        analyzer.run_scout_agent = mock_scout
        analyzer.run_analyst_agent = mock_analyst
        analyzer.run_strategist_agent = mock_strategist

        messages = []
        async for msg in analyzer.analyze(b"img", "png", "Widget Pro", 29.99, "USD", ["Fast"]):
            messages.append(msg)

        agents = set(m.agent for m in messages)
        assert AgentRole.SCOUT in agents
        assert AgentRole.ANALYST in agents
        assert AgentRole.STRATEGIST in agents

    @pytest.mark.asyncio
    async def test_scout_failure_stops_pipeline(self):
        analyzer = VisualPricingAnalyzer()

        async def mock_scout(*args, **kwargs):
            yield AgentMessage(
                AgentRole.SCOUT,
                ThoughtType.OBSERVATION,
                "Scanning...",
            )
            # Final message WITHOUT extracted_data
            yield AgentMessage(
                AgentRole.SCOUT,
                ThoughtType.DECISION,
                "Failed",
                is_final=True,
                metadata={},
            )

        analyzer.run_scout_agent = mock_scout
        analyst_called = False

        async def mock_analyst(*args, **kwargs):
            nonlocal analyst_called
            analyst_called = True
            yield AgentMessage(AgentRole.ANALYST, None, "x")

        analyzer.run_analyst_agent = mock_analyst

        messages = []
        async for msg in analyzer.analyze(b"img", "png", "Widget", 29.99):
            messages.append(msg)

        # Should have error message and analyst never called
        assert not analyst_called
        assert any("failed" in m.content.lower() or "cannot" in m.content.lower() for m in messages)

    @pytest.mark.asyncio
    async def test_creates_product_info_correctly(self):
        analyzer = VisualPricingAnalyzer()

        captured_product = None

        async def mock_scout(*args, **kwargs):
            yield AgentMessage(
                AgentRole.SCOUT,
                ThoughtType.DECISION,
                "Done",
                is_final=True,
                metadata={"extracted_data": _make_competitor_data()},
            )

        async def mock_analyst(product, *args, **kwargs):
            nonlocal captured_product
            captured_product = product
            yield AgentMessage(
                AgentRole.ANALYST,
                ThoughtType.DECISION,
                "Done",
                is_final=True,
                metadata={"analysis": {}},
            )

        async def mock_strategist(*args, **kwargs):
            yield AgentMessage(
                AgentRole.STRATEGIST,
                ThoughtType.RECOMMENDATION,
                "Done",
                is_final=True,
                metadata={"recommendation": {}},
            )

        analyzer.run_scout_agent = mock_scout
        analyzer.run_analyst_agent = mock_analyst
        analyzer.run_strategist_agent = mock_strategist

        messages = []
        async for msg in analyzer.analyze(b"img", "png", "MyWidget", 39.99, "EUR", ["Feature1"]):
            messages.append(msg)

        assert captured_product is not None
        assert captured_product.name == "MyWidget"
        assert captured_product.price == Decimal("39.99")
        assert captured_product.currency == "EUR"
        assert captured_product.features == ["Feature1"]

    @pytest.mark.asyncio
    async def test_default_features_none_becomes_empty_list(self):
        analyzer = VisualPricingAnalyzer()

        captured_product = None

        async def mock_scout(*args, **kwargs):
            yield AgentMessage(
                AgentRole.SCOUT,
                ThoughtType.DECISION,
                "Done",
                is_final=True,
                metadata={"extracted_data": _make_competitor_data()},
            )

        async def mock_analyst(product, *args, **kwargs):
            nonlocal captured_product
            captured_product = product
            yield AgentMessage(
                AgentRole.ANALYST,
                ThoughtType.DECISION,
                "Done",
                is_final=True,
                metadata={"analysis": {}},
            )

        async def mock_strategist(*args, **kwargs):
            yield AgentMessage(
                AgentRole.STRATEGIST,
                ThoughtType.RECOMMENDATION,
                "Done",
                is_final=True,
                metadata={"recommendation": {}},
            )

        analyzer.run_scout_agent = mock_scout
        analyzer.run_analyst_agent = mock_analyst
        analyzer.run_strategist_agent = mock_strategist

        messages = []
        async for msg in analyzer.analyze(b"img", "png", "Widget", 10.00):
            messages.append(msg)

        assert captured_product.features == []
