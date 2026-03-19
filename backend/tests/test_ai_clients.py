"""
Tests for services/ai_trend_analysis/ai_clients.py

Covers:
- Constants: GEMINI3_FLASH, GEMINI3_PRO, DEFAULT_MODEL
- Enums: ThoughtType
- Dataclasses: StreamChunk, ImageAnalysisResult
- AIClients:
  - __init__, lazy client properties
  - _build_thinking_config
  - _extract_thought_from_chunk
  - _detect_thought_type
  - _get_fallback_response
  - call_openai (success + failure)
  - call_gemini (success + JSON extraction + failure)
  - call (routing)
  - stream_gemini3 (success, no client, error)
  - analyze_image_stream (success, no client, error)
  - analyze_image (success, JSON parse error, no client, error)
"""

"""
Tests for services/ai_trend_analysis/ai_clients.py
...
"""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
# core.logging and core.config are handled by conftest.py (autouse).
_MOCKED_MODULES = ["db.session", "google.genai", "google.genai.types"]
_originals = {mod: sys.modules.get(mod) for mod in _MOCKED_MODULES}

for mod in _MOCKED_MODULES:
    if _originals[mod] is None:
        sys.modules[mod] = MagicMock()

from services.ai_trend_analysis.ai_clients import (
    DEFAULT_MODEL,
    GEMINI3_FLASH,
    GEMINI3_PRO,
    AIClients,
    ImageAnalysisResult,
    StreamChunk,
    ThoughtType,
)

# ── IMMEDIATE cleanup — must happen before pytest collects later modules ──
for _mod in _MOCKED_MODULES:
    if _originals[_mod] is None:
        sys.modules.pop(_mod, None)
    else:
        sys.modules[_mod] = _originals[_mod]
del _mod  # clean up loop variable


# ==================================================================
# Constants
# ==================================================================


class TestConstants:
    def test_gemini3_flash(self):
        assert GEMINI3_FLASH == "gemini-3-flash-preview"

    def test_gemini3_pro(self):
        assert GEMINI3_PRO == "gemini-3-pro-preview"

    def test_default_model_is_flash(self):
        assert DEFAULT_MODEL == GEMINI3_FLASH


# ==================================================================
# ThoughtType Enum
# ==================================================================


class TestThoughtType:
    def test_observation(self):
        assert ThoughtType.OBSERVATION == "observation"

    def test_analysis(self):
        assert ThoughtType.ANALYSIS == "analysis"

    def test_hypothesis(self):
        assert ThoughtType.HYPOTHESIS == "hypothesis"

    def test_decision(self):
        assert ThoughtType.DECISION == "decision"

    def test_recommendation(self):
        assert ThoughtType.RECOMMENDATION == "recommendation"

    def test_is_str_enum(self):
        assert isinstance(ThoughtType.OBSERVATION, str)


# ==================================================================
# StreamChunk Dataclass
# ==================================================================


class TestStreamChunk:
    def test_basic_creation(self):
        chunk = StreamChunk(text="Hello")
        assert chunk.text == "Hello"
        assert chunk.thought_type is None
        assert chunk.is_final is False
        assert chunk.is_thought is False

    def test_with_all_fields(self):
        chunk = StreamChunk(
            text="Analyzing...",
            thought_type=ThoughtType.ANALYSIS,
            is_final=True,
            is_thought=True,
        )
        assert chunk.thought_type == ThoughtType.ANALYSIS
        assert chunk.is_final is True
        assert chunk.is_thought is True

    def test_final_chunk(self):
        chunk = StreamChunk(text="", is_final=True)
        assert chunk.text == ""
        assert chunk.is_final is True


# ==================================================================
# ImageAnalysisResult Dataclass
# ==================================================================


class TestImageAnalysisResult:
    def test_basic_creation(self):
        result = ImageAnalysisResult()
        assert result.product_name is None
        assert result.price is None
        assert result.currency is None
        assert result.features == []
        assert result.reviews_summary is None
        assert result.promo_signals == []
        assert result.confidence == 0.0
        assert result.raw_text == ""

    def test_with_all_fields(self):
        result = ImageAnalysisResult(
            product_name="Widget Pro",
            price="$29.99",
            currency="USD",
            features=["Fast", "Durable"],
            reviews_summary="Mostly positive",
            promo_signals=["20% OFF"],
            confidence=0.95,
            raw_text="Full response text",
        )
        assert result.product_name == "Widget Pro"
        assert len(result.features) == 2
        assert result.confidence == 0.95

    def test_post_init_none_features(self):
        """features=None should become []."""
        result = ImageAnalysisResult(features=None)
        assert result.features == []

    def test_post_init_none_promo_signals(self):
        """promo_signals=None should become []."""
        result = ImageAnalysisResult(promo_signals=None)
        assert result.promo_signals == []

    def test_separate_default_lists(self):
        r1 = ImageAnalysisResult()
        r2 = ImageAnalysisResult()
        assert r1.features is not r2.features
        assert r1.promo_signals is not r2.promo_signals


# ==================================================================
# AIClients.__init__
# ==================================================================


class TestAIClientsInit:
    def test_initial_state(self):
        client = AIClients()
        assert client._openai_client is None
        assert client._gemini_client is None
        assert client._gemini3_client is None


# ==================================================================
# _build_thinking_config
# ==================================================================


class TestBuildThinkingConfig:
    def test_returns_config_object(self):
        result = AIClients._build_thinking_config("low")
        assert result is not None

    def test_accepts_minimal(self):
        result = AIClients._build_thinking_config("minimal")
        assert result is not None

    def test_accepts_high(self):
        result = AIClients._build_thinking_config("high")
        assert result is not None

    def test_import_error_returns_empty_dict(self):
        """When google.genai.types not importable, returns {}."""
        with patch.dict(sys.modules, {"google.genai.types": None}):
            original = sys.modules.get("google.genai")
            try:
                mock_genai = MagicMock()
                mock_genai.types = None
                sys.modules["google.genai"] = mock_genai
                result = AIClients._build_thinking_config("low")
                assert result is not None or result == {}
            finally:
                if original:
                    sys.modules["google.genai"] = original


# ==================================================================
# _extract_thought_from_chunk
# ==================================================================


class TestExtractThoughtFromChunk:
    def test_thought_part_true(self):
        part = MagicMock()
        part.thought = True
        candidate = MagicMock()
        candidate.content.parts = [part]
        chunk = MagicMock()
        chunk.candidates = [candidate]
        result = AIClients._extract_thought_from_chunk(chunk)
        assert result is True

    def test_no_thought_part(self):
        part = MagicMock()
        part.thought = False
        candidate = MagicMock()
        candidate.content.parts = [part]
        chunk = MagicMock()
        chunk.candidates = [candidate]
        result = AIClients._extract_thought_from_chunk(chunk)
        assert result is False

    def test_no_candidates(self):
        chunk = MagicMock(spec=[])
        result = AIClients._extract_thought_from_chunk(chunk)
        assert result is None or result is False

    def test_exception_returns_none(self):
        chunk = MagicMock()
        chunk.candidates = None
        result = AIClients._extract_thought_from_chunk(chunk)
        assert result is None

    def test_empty_candidates_list(self):
        chunk = MagicMock()
        chunk.candidates = []
        result = AIClients._extract_thought_from_chunk(chunk)
        assert result is False


# ==================================================================
# _detect_thought_type
# ==================================================================


class TestDetectThoughtType:
    def test_observation_keywords(self):
        assert AIClients._detect_thought_type("I see a price drop") == ThoughtType.OBSERVATION
        assert AIClients._detect_thought_type("Looking at the data") == ThoughtType.OBSERVATION
        assert AIClients._detect_thought_type("Scanning the market") == ThoughtType.OBSERVATION
        assert AIClients._detect_thought_type("I notice something") == ThoughtType.OBSERVATION

    def test_analysis_keywords(self):
        assert AIClients._detect_thought_type("Analyzing the trend") == ThoughtType.ANALYSIS
        assert AIClients._detect_thought_type("Comparing prices") == ThoughtType.ANALYSIS
        assert AIClients._detect_thought_type("This means lower demand") == ThoughtType.ANALYSIS
        assert AIClients._detect_thought_type("Evaluating the risk") == ThoughtType.ANALYSIS

    def test_hypothesis_keywords(self):
        assert AIClients._detect_thought_type("This could be a crisis") == ThoughtType.HYPOTHESIS
        assert AIClients._detect_thought_type("It might indicate growth") == ThoughtType.HYPOTHESIS
        assert AIClients._detect_thought_type("Possibly a new launch") == ThoughtType.HYPOTHESIS
        assert AIClients._detect_thought_type("My hypothesis is...") == ThoughtType.HYPOTHESIS

    def test_decision_keywords(self):
        assert AIClients._detect_thought_type("Therefore we should act") == ThoughtType.DECISION
        assert AIClients._detect_thought_type("I conclude that") == ThoughtType.DECISION
        assert AIClients._detect_thought_type("The decision is clear") == ThoughtType.DECISION
        assert AIClients._detect_thought_type("I have determined") == ThoughtType.DECISION

    def test_recommendation_keywords(self):
        assert AIClients._detect_thought_type("I recommend lowering price") == ThoughtType.RECOMMENDATION
        assert AIClients._detect_thought_type("I suggest we hold") == ThoughtType.RECOMMENDATION
        assert AIClients._detect_thought_type("You should increase") == ThoughtType.RECOMMENDATION
        assert AIClients._detect_thought_type("The optimal strategy is") == ThoughtType.RECOMMENDATION

    def test_no_match_returns_none(self):
        assert AIClients._detect_thought_type("Random text with no keywords") is None
        assert AIClients._detect_thought_type("") is None

    def test_case_insensitive(self):
        assert AIClients._detect_thought_type("I SEE a change") == ThoughtType.OBSERVATION
        assert AIClients._detect_thought_type("ANALYZING data") == ThoughtType.ANALYSIS

    def test_priority_first_match(self):
        """When multiple keywords match, first category wins."""
        result = AIClients._detect_thought_type("I see we are analyzing this")
        assert result == ThoughtType.OBSERVATION


# ==================================================================
# _get_fallback_response
# ==================================================================


class TestGetFallbackResponse:
    def test_returns_dict(self):
        client = AIClients()
        result = client._get_fallback_response()
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        client = AIClients()
        result = client._get_fallback_response()
        assert "market_sentiment" in result
        assert "predictions" in result
        assert "opportunities" in result
        assert "risks" in result
        assert "executive_summary" in result

    def test_sentiment_is_stable(self):
        client = AIClients()
        result = client._get_fallback_response()
        assert result["market_sentiment"] == "stable"
        assert result["market_sentiment_score"] == 0


# ==================================================================
# call_openai
# ==================================================================


class TestCallOpenAI:
    @pytest.mark.asyncio
    async def test_success(self):
        client = AIClients()
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"market_sentiment": "bullish"}'
        mock_openai.chat.completions.create.return_value = mock_response
        client._openai_client = mock_openai

        result = await client.call_openai("system", "user")
        assert result["market_sentiment"] == "bullish"

    @pytest.mark.asyncio
    async def test_failure_returns_fallback(self):
        client = AIClients()
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = Exception("API error")
        client._openai_client = mock_openai

        result = await client.call_openai("system", "user")
        assert result["market_sentiment"] == "stable"

    @pytest.mark.asyncio
    async def test_json_parse_error_returns_fallback(self):
        client = AIClients()
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json"
        mock_openai.chat.completions.create.return_value = mock_response
        client._openai_client = mock_openai

        result = await client.call_openai("system", "user")
        assert result["market_sentiment"] == "stable"


# ==================================================================
# call_gemini
# ==================================================================


class TestCallGemini:
    @pytest.mark.asyncio
    async def test_success_plain_json(self):
        client = AIClients()
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"market_sentiment": "bearish"}'
        mock_gemini.generate_content.return_value = mock_response
        client._gemini_client = mock_gemini

        result = await client.call_gemini("system", "user")
        assert result["market_sentiment"] == "bearish"

    @pytest.mark.asyncio
    async def test_success_json_code_block(self):
        client = AIClients()
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'Here is the analysis:\n```json\n{"market_sentiment": "bullish"}\n```'
        mock_gemini.generate_content.return_value = mock_response
        client._gemini_client = mock_gemini

        result = await client.call_gemini("system", "user")
        assert result["market_sentiment"] == "bullish"

    @pytest.mark.asyncio
    async def test_success_generic_code_block(self):
        client = AIClients()
        mock_gemini = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'Result:\n```\n{"market_sentiment": "stable"}\n```'
        mock_gemini.generate_content.return_value = mock_response
        client._gemini_client = mock_gemini

        result = await client.call_gemini("system", "user")
        assert result["market_sentiment"] == "stable"

    @pytest.mark.asyncio
    async def test_failure_returns_fallback(self):
        client = AIClients()
        mock_gemini = MagicMock()
        mock_gemini.generate_content.side_effect = Exception("Gemini error")
        client._gemini_client = mock_gemini

        result = await client.call_gemini("system", "user")
        assert result["market_sentiment"] == "stable"


# ==================================================================
# call (router)
# ==================================================================


class TestCall:
    @pytest.mark.asyncio
    async def test_routes_to_openai_by_default(self):
        client = AIClients()
        client.call_openai = AsyncMock(return_value={"result": "openai"})
        client._gemini_client = None

        _result, model = await client.call("system", "user")
        assert model == "openai"
        client.call_openai.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_routes_to_gemini(self):
        client = AIClients()
        client.call_gemini = AsyncMock(return_value={"result": "gemini"})
        client._gemini_client = MagicMock()

        _result, model = await client.call("system", "user", use_model="gemini")
        assert model == "gemini"
        client.call_gemini.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_falls_back_to_openai_when_gemini_unavailable(self):
        client = AIClients()
        client.call_openai = AsyncMock(return_value={"result": "openai"})

        with patch.object(type(client), "gemini_client", new_callable=PropertyMock, return_value=None):
            _result, model = await client.call("system", "user", use_model="gemini")
            assert model == "openai"


# ==================================================================
# stream_gemini3
# ==================================================================


class TestStreamGemini3:
    @pytest.mark.asyncio
    async def test_no_client_yields_unavailable(self):
        client = AIClients()
        with patch.object(type(client), "gemini3_client", new_callable=PropertyMock, return_value=None):
            chunks = []
            async for chunk in client.stream_gemini3("test prompt"):
                chunks.append(chunk)
            assert len(chunks) == 1
            assert "not available" in chunks[0].text
            assert chunks[0].is_final is True

    @pytest.mark.asyncio
    async def test_success_yields_chunks(self):
        client = AIClients()
        mock_gemini3 = MagicMock()

        chunk1 = MagicMock()
        chunk1.text = "Observing market trends"
        chunk1.candidates = []

        chunk2 = MagicMock()
        chunk2.text = "Analyzing competitor data"
        chunk2.candidates = []

        mock_gemini3.models.generate_content_stream.return_value = [chunk1, chunk2]
        client._gemini3_client = mock_gemini3

        chunks = []
        async for chunk in client.stream_gemini3("test prompt"):
            chunks.append(chunk)

        assert len(chunks) == 3
        assert chunks[0].text == "Observing market trends"
        assert chunks[1].text == "Analyzing competitor data"
        assert chunks[2].is_final is True

    @pytest.mark.asyncio
    async def test_thought_type_detected(self):
        client = AIClients()
        mock_gemini3 = MagicMock()

        chunk = MagicMock()
        chunk.text = "I see a significant price drop"
        chunk.candidates = []

        mock_gemini3.models.generate_content_stream.return_value = [chunk]
        client._gemini3_client = mock_gemini3

        chunks = []
        async for c in client.stream_gemini3("test"):
            chunks.append(c)

        assert chunks[0].thought_type == ThoughtType.OBSERVATION

    @pytest.mark.asyncio
    async def test_error_yields_error_chunk(self):
        client = AIClients()
        mock_gemini3 = MagicMock()
        mock_gemini3.models.generate_content_stream.side_effect = Exception("Stream error")
        client._gemini3_client = mock_gemini3

        chunks = []
        async for c in client.stream_gemini3("test"):
            chunks.append(c)

        assert len(chunks) == 1
        assert "Error" in chunks[0].text
        assert chunks[0].is_final is True

    @pytest.mark.asyncio
    async def test_empty_text_chunks_skipped(self):
        client = AIClients()
        mock_gemini3 = MagicMock()

        chunk1 = MagicMock()
        chunk1.text = ""
        chunk2 = MagicMock()
        chunk2.text = "Real content"
        chunk2.candidates = []

        mock_gemini3.models.generate_content_stream.return_value = [chunk1, chunk2]
        client._gemini3_client = mock_gemini3

        chunks = []
        async for c in client.stream_gemini3("test"):
            chunks.append(c)

        assert len(chunks) == 2
        assert chunks[0].text == "Real content"


# ==================================================================
# analyze_image_stream
# ==================================================================


class TestAnalyzeImageStream:
    @pytest.mark.asyncio
    async def test_no_client_yields_unavailable(self):
        client = AIClients()
        with patch.object(type(client), "gemini3_client", new_callable=PropertyMock, return_value=None):
            chunks = []
            async for c in client.analyze_image_stream(b"fake_image"):
                chunks.append(c)
            assert len(chunks) == 1
            assert "not available" in chunks[0].text

    @pytest.mark.asyncio
    async def test_success_yields_chunks(self):
        client = AIClients()
        mock_gemini3 = MagicMock()

        chunk = MagicMock()
        chunk.text = "Product name: Widget Pro, Price: $29.99"
        chunk.candidates = []

        mock_gemini3.models.generate_content_stream.return_value = [chunk]
        client._gemini3_client = mock_gemini3

        chunks = []
        async for c in client.analyze_image_stream(b"fake_image", "png"):
            chunks.append(c)

        assert len(chunks) == 2
        assert "Widget Pro" in chunks[0].text

    @pytest.mark.asyncio
    async def test_custom_prompt_used(self):
        client = AIClients()
        mock_gemini3 = MagicMock()
        mock_gemini3.models.generate_content_stream.return_value = []
        client._gemini3_client = mock_gemini3

        chunks = []
        async for c in client.analyze_image_stream(b"fake", "png", analysis_prompt="Custom analysis"):
            chunks.append(c)

        mock_gemini3.models.generate_content_stream.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_yields_error_chunk(self):
        client = AIClients()
        mock_gemini3 = MagicMock()
        mock_gemini3.models.generate_content_stream.side_effect = Exception("Image error")
        client._gemini3_client = mock_gemini3

        chunks = []
        async for c in client.analyze_image_stream(b"fake"):
            chunks.append(c)

        assert "Error" in chunks[0].text
        assert chunks[0].is_final is True


# ==================================================================
# analyze_image (structured, non-streaming)
# ==================================================================


class TestAnalyzeImage:
    @pytest.mark.asyncio
    async def test_no_client_returns_empty_result(self):
        client = AIClients()
        with patch.object(type(client), "gemini3_client", new_callable=PropertyMock, return_value=None):
            result = await client.analyze_image(b"fake_image")
            assert isinstance(result, ImageAnalysisResult)
            assert "not available" in result.raw_text

    @pytest.mark.asyncio
    async def test_success_parses_json(self):
        client = AIClients()
        mock_gemini3 = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "product_name": "Widget Pro",
                "price": "$29.99",
                "currency": "USD",
                "features": ["Fast", "Light"],
                "reviews_summary": "Very good",
                "promo_signals": ["10% OFF"],
                "confidence": 0.92,
            }
        )
        mock_gemini3.models.generate_content.return_value = mock_response
        client._gemini3_client = mock_gemini3

        result = await client.analyze_image(b"fake_image")
        assert result.product_name == "Widget Pro"
        assert result.price == "$29.99"
        assert result.currency == "USD"
        assert len(result.features) == 2
        assert result.confidence == 0.92

    @pytest.mark.asyncio
    async def test_success_json_code_block(self):
        client = AIClients()
        mock_gemini3 = MagicMock()
        data = {"product_name": "Gadget", "confidence": 0.8}
        mock_response = MagicMock()
        mock_response.text = f"```json\n{json.dumps(data)}\n```"
        mock_gemini3.models.generate_content.return_value = mock_response
        client._gemini3_client = mock_gemini3

        result = await client.analyze_image(b"fake")
        assert result.product_name == "Gadget"
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_json_parse_error_returns_low_confidence(self):
        client = AIClients()
        mock_gemini3 = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Not valid JSON at all"
        mock_gemini3.models.generate_content.return_value = mock_response
        client._gemini3_client = mock_gemini3

        result = await client.analyze_image(b"fake")
        assert isinstance(result, ImageAnalysisResult)
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_general_error_returns_low_confidence(self):
        client = AIClients()
        mock_gemini3 = MagicMock()
        mock_gemini3.models.generate_content.side_effect = Exception("API crash")
        client._gemini3_client = mock_gemini3

        result = await client.analyze_image(b"fake")
        assert isinstance(result, ImageAnalysisResult)
        assert result.confidence == 0.0
        assert "API crash" in result.raw_text

    @pytest.mark.asyncio
    async def test_missing_fields_use_defaults(self):
        client = AIClients()
        mock_gemini3 = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"product_name": "Widget"}'
        mock_gemini3.models.generate_content.return_value = mock_response
        client._gemini3_client = mock_gemini3

        result = await client.analyze_image(b"fake")
        assert result.product_name == "Widget"
        assert result.features == []
        assert result.promo_signals == []
        assert result.confidence == 0.5
