"""
Tests for services/ai_generator.py — AIGeneratorService

Covers:
- is_available / get_available_providers / _get_primary_provider
- _call_gemini_sync: new API, legacy API
- _call_gemini: async wrapper
- _call_openai: calls completions
- _generate: gemini success, gemini fail → openai fallback, both fail, no providers
- _parse_json_response: plain JSON, markdown fenced, invalid JSON
- generate_product_description: success, JSON parse failure, no provider raises
- generate_pricing_explanation: success, AI failure → fallback, no provider → fallback
- _fallback_pricing_explanation: increase/decrease
- get_health: healthy/degraded
"""

import sys
import os
import json
from types import ModuleType
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session", "core.config",
    "google", "google.genai", "google.generativeai",
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

_config_stub = ModuleType("core.config")
_fake_settings = MagicMock()
_fake_settings.GEMINI_API_KEY = None
_fake_settings.OPENAI_API_KEY = None
_config_stub.settings = _fake_settings
sys.modules["core.config"] = _config_stub

if "core" not in sys.modules:
    _core = ModuleType("core")
    _core.__path__ = [os.path.join(_backend_dir, "core")]
    sys.modules["core"] = _core

# Suppress google/openai imports
for _m in ("google", "google.genai", "google.generativeai", "openai"):
    sys.modules[_m] = None

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.ai_generator import AIGeneratorService

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

def _make_service(gemini_client=None, openai_client=None):
    svc = AIGeneratorService.__new__(AIGeneratorService)
    svc.gemini_client = gemini_client
    svc.openai_client = openai_client
    svc.gemini_model_name = "gemini-2.0-flash-exp"
    svc.openai_model = "gpt-4o-mini"
    svc._using_new_api = True if gemini_client else False
    return svc


# ===========================================================================
# Tests
# ===========================================================================

class TestIsAvailable:
    def test_no_providers(self):
        assert _make_service().is_available() is False

    def test_gemini_only(self):
        assert _make_service(gemini_client=MagicMock()).is_available() is True

    def test_openai_only(self):
        assert _make_service(openai_client=MagicMock()).is_available() is True

    def test_both(self):
        assert _make_service(gemini_client=MagicMock(), openai_client=MagicMock()).is_available() is True


class TestGetAvailableProviders:
    def test_none(self):
        assert _make_service().get_available_providers() == []

    def test_gemini(self):
        assert _make_service(gemini_client=MagicMock()).get_available_providers() == ["gemini"]

    def test_both(self):
        assert _make_service(gemini_client=MagicMock(), openai_client=MagicMock()).get_available_providers() == ["gemini", "openai"]


class TestGetPrimaryProvider:
    def test_gemini_preferred(self):
        assert _make_service(gemini_client=MagicMock(), openai_client=MagicMock())._get_primary_provider() == "gemini"

    def test_openai_fallback(self):
        assert _make_service(openai_client=MagicMock())._get_primary_provider() == "openai"

    def test_none(self):
        assert _make_service()._get_primary_provider() == "none"


class TestCallGeminiSync:
    def test_new_api(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "  Generated text  "
        mock_client.models.generate_content.return_value = mock_response

        svc = _make_service(gemini_client=mock_client)
        svc._using_new_api = True

        result = svc._call_gemini_sync("System prompt", "User message")
        assert result == "Generated text"
        call_kwargs = mock_client.models.generate_content.call_args
        prompt = call_kwargs.kwargs.get("contents") or call_kwargs[1].get("contents")
        assert "System prompt" in prompt
        assert "User message" in prompt

    def test_legacy_api(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "  Legacy result  "
        mock_client.generate_content.return_value = mock_response

        svc = _make_service(gemini_client=mock_client)
        svc._using_new_api = False

        result = svc._call_gemini_sync("Sys", "User")
        assert result == "Legacy result"


class TestCallGemini:
    @pytest.mark.asyncio
    async def test_async_wrapper(self):
        svc = _make_service(gemini_client=MagicMock())
        svc._call_gemini_sync = MagicMock(return_value="async result")

        result = await svc._call_gemini("sys", "user")
        assert result == "async result"


class TestCallOpenAI:
    @pytest.mark.asyncio
    async def test_calls_completions(self):
        mock_client = AsyncMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "  OpenAI response  "
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        svc = _make_service(openai_client=mock_client)
        result = await svc._call_openai("sys", "user", temperature=0.5, max_tokens=300)

        assert result == "OpenAI response"
        mock_client.chat.completions.create.assert_awaited_once()


class TestGenerate:
    @pytest.mark.asyncio
    async def test_gemini_success(self):
        svc = _make_service(gemini_client=MagicMock())
        svc._call_gemini = AsyncMock(return_value="Gemini output")

        text, provider = await svc._generate("sys", "user")
        assert text == "Gemini output"
        assert provider == "gemini"

    @pytest.mark.asyncio
    async def test_gemini_fails_openai_fallback(self):
        svc = _make_service(gemini_client=MagicMock(), openai_client=MagicMock())
        svc._call_gemini = AsyncMock(side_effect=Exception("Gemini down"))
        svc._call_openai = AsyncMock(return_value="OpenAI fallback")

        text, provider = await svc._generate("sys", "user")
        assert text == "OpenAI fallback"
        assert provider == "openai"

    @pytest.mark.asyncio
    async def test_both_fail_raises(self):
        svc = _make_service(gemini_client=MagicMock(), openai_client=MagicMock())
        svc._call_gemini = AsyncMock(side_effect=Exception("Gemini down"))
        svc._call_openai = AsyncMock(side_effect=Exception("OpenAI down"))

        with pytest.raises(ValueError, match="All AI services failed"):
            await svc._generate("sys", "user")

    @pytest.mark.asyncio
    async def test_no_providers_raises(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="No AI service available"):
            await svc._generate("sys", "user")

    @pytest.mark.asyncio
    async def test_openai_only(self):
        svc = _make_service(openai_client=MagicMock())
        svc._call_openai = AsyncMock(return_value="OpenAI direct")

        text, provider = await svc._generate("sys", "user")
        assert provider == "openai"


class TestParseJsonResponse:
    def test_plain_json(self):
        svc = _make_service()
        result = svc._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_fenced(self):
        svc = _make_service()
        text = '```json\n{"key": "value"}\n```'
        result = svc._parse_json_response(text)
        assert result == {"key": "value"}

    def test_markdown_fenced_no_lang(self):
        svc = _make_service()
        text = '```\n{"key": "value"}\n```'
        result = svc._parse_json_response(text)
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        svc = _make_service()
        with pytest.raises(json.JSONDecodeError):
            svc._parse_json_response("not json at all")


class TestGenerateProductDescription:
    @pytest.mark.asyncio
    async def test_success(self):
        svc = _make_service(gemini_client=MagicMock())
        ai_response = json.dumps({
            "description": "<p>Great widget</p>",
            "seo_title": "Best Widget 2026",
            "meta_description": "Buy the best widget",
            "suggested_keywords": ["widget", "gadget"],
        })
        svc._generate = AsyncMock(return_value=(ai_response, "gemini"))

        result = await svc.generate_product_description(name="Widget", category="Gadgets")

        assert result["description"] == "<p>Great widget</p>"
        assert result["seo_title"] == "Best Widget 2026"
        assert result["ai_generated"] is True
        assert result["ai_provider"] == "gemini"

    @pytest.mark.asyncio
    async def test_seo_title_truncated(self):
        svc = _make_service(gemini_client=MagicMock())
        ai_response = json.dumps({
            "description": "desc",
            "seo_title": "A" * 100,
            "meta_description": "B" * 200,
            "suggested_keywords": list(range(20)),
        })
        svc._generate = AsyncMock(return_value=(ai_response, "gemini"))

        result = await svc.generate_product_description(name="Widget")

        assert len(result["seo_title"]) <= 60
        assert len(result["meta_description"]) <= 160
        assert len(result["suggested_keywords"]) <= 10

    @pytest.mark.asyncio
    async def test_json_parse_failure_raises(self):
        svc = _make_service(gemini_client=MagicMock())
        svc._generate = AsyncMock(return_value=("not json", "gemini"))

        with pytest.raises(ValueError, match="Failed to generate description"):
            await svc.generate_product_description(name="Widget")

    @pytest.mark.asyncio
    async def test_no_provider_raises(self):
        svc = _make_service()

        with pytest.raises(ValueError, match="No AI API key configured"):
            await svc.generate_product_description(name="Widget")

    @pytest.mark.asyncio
    async def test_includes_optional_context(self):
        svc = _make_service(gemini_client=MagicMock())
        ai_response = json.dumps({
            "description": "d", "seo_title": "t",
            "meta_description": "m", "suggested_keywords": [],
        })
        svc._generate = AsyncMock(return_value=(ai_response, "gemini"))

        await svc.generate_product_description(
            name="Widget",
            category="Gadgets",
            keywords=["premium", "quality"],
            current_description="Old desc",
            tone="casual",
            length="long",
        )

        call_args = svc._generate.call_args
        user_msg = call_args[0][1]
        assert "Gadgets" in user_msg
        assert "premium" in user_msg
        assert "Old desc" in user_msg


class TestGeneratePricingExplanation:
    @pytest.mark.asyncio
    async def test_success(self):
        svc = _make_service(gemini_client=MagicMock())
        ai_response = json.dumps({
            "explanation": "Price should increase due to demand.",
            "key_factors": ["demand", "sentiment"],
            "confidence_reason": "Strong data signals",
        })
        svc._generate = AsyncMock(return_value=(ai_response, "gemini"))

        result = await svc.generate_pricing_explanation(
            product_name="Widget",
            current_price=19.99,
            suggested_price=24.99,
            sentiment_score=0.7,
            competitor_prices=[22.99, 25.99],
            factors=["sentiment", "competition"],
        )

        assert result["explanation"] == "Price should increase due to demand."
        assert result["ai_generated"] is True

    @pytest.mark.asyncio
    async def test_ai_failure_returns_fallback(self):
        svc = _make_service(gemini_client=MagicMock())
        svc._generate = AsyncMock(side_effect=Exception("AI down"))

        result = await svc.generate_pricing_explanation(
            product_name="Widget",
            current_price=19.99,
            suggested_price=24.99,
        )

        assert result["ai_generated"] is False
        assert result["ai_provider"] == "none"

    @pytest.mark.asyncio
    async def test_no_provider_returns_fallback(self):
        svc = _make_service()

        result = await svc.generate_pricing_explanation(
            product_name="Widget",
            current_price=19.99,
            suggested_price=14.99,
        )

        assert result["ai_generated"] is False
        assert "lowering" in result["explanation"]


class TestFallbackPricingExplanation:
    def test_price_increase(self):
        svc = _make_service()
        result = svc._fallback_pricing_explanation("Widget", 19.99, 24.99, ["demand"])
        assert "raising" in result["explanation"]
        assert result["ai_generated"] is False
        assert result["key_factors"] == ["demand"]

    def test_price_decrease(self):
        svc = _make_service()
        result = svc._fallback_pricing_explanation("Widget", 24.99, 19.99, None)
        assert "lowering" in result["explanation"]
        assert result["key_factors"] == ["Market analysis", "Sentiment data"]


class TestGetHealth:
    def test_healthy(self):
        svc = _make_service(gemini_client=MagicMock(), openai_client=MagicMock())
        result = svc.get_health()
        assert result["status"] == "healthy"
        assert result["service"] == "ai_generator"
        assert result["gemini_configured"] is True
        assert result["openai_configured"] is True

    def test_degraded(self):
        svc = _make_service()
        result = svc.get_health()
        assert result["status"] == "degraded"
        assert result["gemini_configured"] is False
        assert result["openai_configured"] is False
        assert result["primary_provider"] == "none"

    def test_models_shown_when_configured(self):
        svc = _make_service(gemini_client=MagicMock())
        result = svc.get_health()
        assert result["gemini_model"] == "gemini-2.0-flash-exp"
        assert result["openai_model"] is None

        