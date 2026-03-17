"""
Tests for services/openai_sentiment.py — OpenAISentimentAnalyzer

Covers:
- __init__: client setup, no API key
- is_available: True/False
- _fallback_response: structure, neutral defaults
- analyze: success, JSON parse failure → fallback, API error → fallback,
  markdown fenced response, no client raises, context included
- analyze_batch: empty list, multiple texts, exception → fallback replacement
"""

import json
import os
import sys
from decimal import Decimal
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------

_MOCKED = [
    "db.session",
    "core.config",
    "openai",
]

_originals = {m: sys.modules.get(m) for m in _MOCKED}

for _m in ("db.session",):
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if "services" not in sys.modules:
    _svc = ModuleType("services")
    _svc.__path__ = [os.path.join(_backend_dir, "services")]
    _svc.__package__ = "services"
    sys.modules["services"] = _svc

if "core" not in sys.modules:
    _core = ModuleType("core")
    _core.__path__ = [os.path.join(_backend_dir, "core")]
    sys.modules["core"] = _core

_config_stub = ModuleType("core.config")
_fake_settings = MagicMock()
_fake_settings.OPENAI_API_KEY = "sk-test-key"
_config_stub.settings = _fake_settings
sys.modules["core.config"] = _config_stub

# Stub openai
_openai_stub = ModuleType("openai")
_FakeAsyncOpenAI = MagicMock()
_openai_stub.AsyncOpenAI = _FakeAsyncOpenAI
sys.modules["openai"] = _openai_stub

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.openai_sentiment import OpenAISentimentAnalyzer

# ---------------------------------------------------------------------------
# 3. Restore sys.modules
# ---------------------------------------------------------------------------
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m


# ===========================================================================
# Helpers
# ===========================================================================


def _make_analyzer(client=None):
    """Create analyzer with injected client."""
    svc = OpenAISentimentAnalyzer.__new__(OpenAISentimentAnalyzer)
    svc.client = client
    svc.model = "gpt-4o-mini"
    return svc


def _mock_openai_response(content: str):
    """Create a mock OpenAI completion response."""
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def _valid_ai_json(**overrides):
    """Return valid JSON string matching expected AI response format."""
    data = {
        "sentiment_score": 0.75,
        "sentiment_label": "positive",
        "confidence": 0.9,
        "positive_score": 0.8,
        "negative_score": 0.05,
        "neutral_score": 0.15,
        "emotions": {"joy": 0.8, "anger": 0.0, "fear": 0.0, "surprise": 0.1, "sadness": 0.0},
        "topics": ["quality", "shipping"],
        "is_sarcastic": False,
    }
    data.update(overrides)
    return json.dumps(data)


# ===========================================================================
# Tests
# ===========================================================================


class TestInit:
    def test_with_api_key(self):
        # Uses the stub so client will be whatever AsyncOpenAI returns
        svc = OpenAISentimentAnalyzer()
        assert svc.client is not None
        assert svc.model == "gpt-4o-mini"

    def test_without_api_key(self):
        svc = OpenAISentimentAnalyzer.__new__(OpenAISentimentAnalyzer)
        svc.client = None
        svc.model = "gpt-4o-mini"
        assert svc.client is None


class TestIsAvailable:
    def test_available(self):
        assert _make_analyzer(client=MagicMock()).is_available() is True

    def test_not_available(self):
        assert _make_analyzer(client=None).is_available() is False


class TestFallbackResponse:
    def test_structure(self):
        svc = _make_analyzer()
        result = svc._fallback_response()

        assert result["compound"] == Decimal("0")
        assert result["positive"] == Decimal("0.33")
        assert result["negative"] == Decimal("0.33")
        assert result["neutral"] == Decimal("0.34")
        assert result["label"] == "neutral"
        assert result["confidence"] == Decimal("0")
        assert result["emotions"] == {"joy": 0, "anger": 0, "fear": 0, "surprise": 0, "sadness": 0}
        assert result["topics"] == []
        assert result["is_sarcastic"] is False


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_openai_response(_valid_ai_json()))
        svc = _make_analyzer(client=mock_client)

        result = await svc.analyze("This product is amazing!")

        assert result["compound"] == Decimal("0.75")
        assert result["label"] == "positive"
        assert result["confidence"] == Decimal("0.9")
        assert result["positive"] == Decimal("0.8")
        assert result["topics"] == ["quality", "shipping"]
        assert result["is_sarcastic"] is False

    @pytest.mark.asyncio
    async def test_with_context(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_openai_response(_valid_ai_json()))
        svc = _make_analyzer(client=mock_client)

        await svc.analyze("Great product!", context="Electronics review")

        call_args = mock_client.chat.completions.create.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        assert "Electronics review" in user_msg

    @pytest.mark.asyncio
    async def test_markdown_fenced_json(self):
        mock_client = AsyncMock()
        fenced = f"```json\n{_valid_ai_json()}\n```"
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_openai_response(fenced))
        svc = _make_analyzer(client=mock_client)

        result = await svc.analyze("Test text")
        assert result["compound"] == Decimal("0.75")

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_fallback(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_openai_response("not valid json at all"))
        svc = _make_analyzer(client=mock_client)

        result = await svc.analyze("Test text")
        assert result["compound"] == Decimal("0")
        assert result["label"] == "neutral"

    @pytest.mark.asyncio
    async def test_api_error_returns_fallback(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API rate limit"))
        svc = _make_analyzer(client=mock_client)

        result = await svc.analyze("Test text")
        assert result["compound"] == Decimal("0")
        assert result["label"] == "neutral"

    @pytest.mark.asyncio
    async def test_no_client_raises(self):
        svc = _make_analyzer(client=None)

        with pytest.raises(ValueError, match="not configured"):
            await svc.analyze("Test text")

    @pytest.mark.asyncio
    async def test_negative_sentiment(self):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(
                _valid_ai_json(
                    sentiment_score=-0.8,
                    sentiment_label="very_negative",
                    positive_score=0.05,
                    negative_score=0.85,
                    neutral_score=0.1,
                    is_sarcastic=True,
                )
            )
        )
        svc = _make_analyzer(client=mock_client)

        result = await svc.analyze("Terrible product, total waste")
        assert result["compound"] == Decimal("-0.8")
        assert result["label"] == "very_negative"
        assert result["is_sarcastic"] is True

    @pytest.mark.asyncio
    async def test_missing_fields_use_defaults(self):
        mock_client = AsyncMock()
        # Minimal JSON with only some fields
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_openai_response('{"sentiment_score": 0.5}'))
        svc = _make_analyzer(client=mock_client)

        result = await svc.analyze("Okay product")
        assert result["compound"] == Decimal("0.5")
        assert result["label"] == "neutral"  # default
        assert result["topics"] == []  # default
        assert result["is_sarcastic"] is False  # default


class TestAnalyzeBatch:
    @pytest.mark.asyncio
    async def test_empty_list(self):
        svc = _make_analyzer(client=MagicMock())
        result = await svc.analyze_batch([])
        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_texts(self):
        svc = _make_analyzer(client=MagicMock())
        svc.analyze = AsyncMock(
            side_effect=[
                {"compound": Decimal("0.5"), "label": "positive"},
                {"compound": Decimal("-0.3"), "label": "negative"},
            ]
        )

        results = await svc.analyze_batch(["Great!", "Bad!"])
        assert len(results) == 2
        assert results[0]["compound"] == Decimal("0.5")
        assert results[1]["compound"] == Decimal("-0.3")

    @pytest.mark.asyncio
    async def test_exception_replaced_with_fallback(self):
        svc = _make_analyzer(client=MagicMock())
        svc.analyze = AsyncMock(
            side_effect=[
                {"compound": Decimal("0.5"), "label": "positive"},
                Exception("API error"),
            ]
        )

        results = await svc.analyze_batch(["Good!", "Crash!"])
        assert len(results) == 2
        assert results[0]["compound"] == Decimal("0.5")
        # Second result should be fallback
        assert results[1]["compound"] == Decimal("0")
        assert results[1]["label"] == "neutral"

    @pytest.mark.asyncio
    async def test_respects_concurrency_limit(self):
        svc = _make_analyzer(client=MagicMock())
        call_count = 0

        async def mock_analyze(text):
            nonlocal call_count
            call_count += 1
            return {"compound": Decimal("0"), "label": "neutral"}

        svc.analyze = mock_analyze

        texts = [f"Text {i}" for i in range(15)]
        results = await svc.analyze_batch(texts, max_concurrent=5)

        assert len(results) == 15
        assert call_count == 15
