"""
Tests for services/ai_support_service.py — AISupportService

Covers:
- Module-level constants: SYSTEM_PROMPT, TOPIC_CONTEXT, TOPIC_ACTIONS, etc.
- AISupportService.__init__: no providers, gemini only, openai only
- is_available / get_available_providers / _get_primary_provider
- _detect_topic: market_insights, analytics, payments, pricing, general
- _fallback_response: structure
- _call_gemini_sync: new API, legacy API, prompt construction
- _call_gemini: async wrapper
- _call_openai: calls chat.completions.create
- chat: gemini success, gemini fail → openai fallback, both fail, no providers,
  topic context injection, conversation history trimming
- get_topics: returns topics structure
- get_health: healthy, degraded
"""

import sys
import os
from types import ModuleType
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session", "core.logging", "core.config",
    "google", "google.genai", "google.generativeai",
    "openai",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# Ensure db.session / core.logging stubs
for _m in ("db.session", "core.logging"):
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

# Compute real filesystem paths
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if "services" not in sys.modules:
    _svc = ModuleType("services")
    _svc.__path__ = [os.path.join(_backend_dir, "services")]
    _svc.__package__ = "services"
    sys.modules["services"] = _svc

# Stub core.config with settings
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

# Suppress google/openai imports — they'll be tested individually
# Force GEMINI_AVAILABLE and OPENAI_AVAILABLE to False at module level
# by ensuring the imports fail
for _m in ("google", "google.genai", "google.generativeai", "openai"):
    sys.modules[_m] = None  # Forces ImportError

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.ai_support_service import (
    AISupportService,
    SYSTEM_PROMPT,
    TOPIC_CONTEXT,
    TOPIC_ACTIONS,
    TOPIC_SUGGESTIONS,
    DEFAULT_GREETING,
    SUGGESTED_QUESTIONS,
)

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
    """Create AISupportService with injected clients (bypasses __init__ provider setup)."""
    svc = AISupportService.__new__(AISupportService)
    svc.gemini_client = gemini_client
    svc.openai_client = openai_client
    svc.gemini_model_name = "gemini-2.0-flash-exp"
    svc.openai_model = "gpt-4o-mini"
    svc._using_new_api = True if gemini_client else False
    return svc


# ===========================================================================
# Module Constants Tests
# ===========================================================================

class TestModuleConstants:
    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_topic_context_keys(self):
        assert set(TOPIC_CONTEXT.keys()) == {"market_insights", "analytics", "payments", "pricing", "general"}

    def test_topic_actions_keys(self):
        assert set(TOPIC_ACTIONS.keys()) == {"market_insights", "analytics", "payments", "pricing", "general"}
        for actions in TOPIC_ACTIONS.values():
            assert isinstance(actions, list)
            assert len(actions) > 0

    def test_topic_suggestions_structure(self):
        assert len(TOPIC_SUGGESTIONS) == 5
        for ts in TOPIC_SUGGESTIONS:
            assert "id" in ts
            assert "label" in ts
            assert "description" in ts

    def test_default_greeting(self):
        assert "ActualPrice" in DEFAULT_GREETING

    def test_suggested_questions(self):
        assert len(SUGGESTED_QUESTIONS) >= 3
        for q in SUGGESTED_QUESTIONS:
            assert isinstance(q, str)
            assert q.endswith("?")


# ===========================================================================
# AISupportService Tests
# ===========================================================================

class TestIsAvailable:
    def test_no_providers(self):
        svc = _make_service()
        assert svc.is_available() is False

    def test_gemini_only(self):
        svc = _make_service(gemini_client=MagicMock())
        assert svc.is_available() is True

    def test_openai_only(self):
        svc = _make_service(openai_client=MagicMock())
        assert svc.is_available() is True

    def test_both_providers(self):
        svc = _make_service(gemini_client=MagicMock(), openai_client=MagicMock())
        assert svc.is_available() is True


class TestGetAvailableProviders:
    def test_no_providers(self):
        svc = _make_service()
        assert svc.get_available_providers() == []

    def test_gemini_only(self):
        svc = _make_service(gemini_client=MagicMock())
        assert svc.get_available_providers() == ["gemini"]

    def test_openai_only(self):
        svc = _make_service(openai_client=MagicMock())
        assert svc.get_available_providers() == ["openai"]

    def test_both(self):
        svc = _make_service(gemini_client=MagicMock(), openai_client=MagicMock())
        assert svc.get_available_providers() == ["gemini", "openai"]


class TestGetPrimaryProvider:
    def test_gemini_primary(self):
        svc = _make_service(gemini_client=MagicMock())
        assert svc._get_primary_provider() == "gemini"

    def test_openai_when_no_gemini(self):
        svc = _make_service(openai_client=MagicMock())
        assert svc._get_primary_provider() == "openai"

    def test_none_when_no_providers(self):
        svc = _make_service()
        assert svc._get_primary_provider() == "none"

    def test_gemini_preferred_over_openai(self):
        svc = _make_service(gemini_client=MagicMock(), openai_client=MagicMock())
        assert svc._get_primary_provider() == "gemini"


class TestDetectTopic:
    def test_market_insights_sentiment(self):
        svc = _make_service()
        assert svc._detect_topic("What's the sentiment for my product?") == "market_insights"

    def test_market_insights_twitter(self):
        svc = _make_service()
        assert svc._detect_topic("Check twitter trends") == "market_insights"

    def test_market_insights_reddit(self):
        svc = _make_service()
        assert svc._detect_topic("reddit mentions") == "market_insights"

    def test_analytics(self):
        svc = _make_service()
        assert svc._detect_topic("Show me the dashboard metrics") == "analytics"

    def test_analytics_chart(self):
        svc = _make_service()
        assert svc._detect_topic("Can I see a chart of sales?") == "analytics"

    def test_payments_mnee(self):
        svc = _make_service()
        assert svc._detect_topic("How do MNEE payments work?") == "payments"

    def test_payments_wallet(self):
        svc = _make_service()
        assert svc._detect_topic("Connect my wallet") == "payments"

    def test_payments_crypto(self):
        svc = _make_service()
        assert svc._detect_topic("crypto token balance") == "payments"

    def test_pricing(self):
        svc = _make_service()
        assert svc._detect_topic("What price should I set?") == "pricing"

    def test_pricing_competitor(self):
        svc = _make_service()
        assert svc._detect_topic("Track competitor prices") == "pricing"

    def test_general(self):
        svc = _make_service()
        assert svc._detect_topic("Hello how are you?") == "general"

    def test_case_insensitive(self):
        svc = _make_service()
        assert svc._detect_topic("SENTIMENT ANALYSIS") == "market_insights"


class TestFallbackResponse:
    def test_structure(self):
        svc = _make_service()
        result = svc._fallback_response("Something went wrong")
        assert result["message"] == "Something went wrong"
        assert result["topic_detected"] == "general"
        assert result["ai_provider"] == "none"
        assert isinstance(result["suggested_actions"], list)


class TestCallGeminiSync:
    def test_new_api_prompt_construction(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini!"
        mock_client.models.generate_content.return_value = mock_response

        svc = _make_service(gemini_client=mock_client)
        svc._using_new_api = True

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi there"},
        ]
        result = svc._call_gemini_sync(messages)

        assert result == "Hello from Gemini!"
        call_kwargs = mock_client.models.generate_content.call_args
        prompt = call_kwargs.kwargs.get("contents") or call_kwargs[1].get("contents")
        assert "Instructions: You are helpful." in prompt
        assert "User: Hi there" in prompt
        assert prompt.endswith("Assistant:")

    def test_legacy_api(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Hello from legacy!"
        mock_client.generate_content.return_value = mock_response

        svc = _make_service(gemini_client=mock_client)
        svc._using_new_api = False

        messages = [{"role": "user", "content": "Test"}]
        result = svc._call_gemini_sync(messages)

        assert result == "Hello from legacy!"
        mock_client.generate_content.assert_called_once()

    def test_includes_assistant_messages(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Response"
        mock_client.models.generate_content.return_value = mock_response

        svc = _make_service(gemini_client=mock_client)
        svc._using_new_api = True

        messages = [
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
        ]
        svc._call_gemini_sync(messages)

        call_args = mock_client.models.generate_content.call_args
        prompt = call_args.kwargs.get("contents") or call_args[1].get("contents")
        assert "Assistant: A1" in prompt


class TestCallGemini:
    @pytest.mark.asyncio
    async def test_async_wrapper(self):
        svc = _make_service(gemini_client=MagicMock())
        svc._call_gemini_sync = MagicMock(return_value="async result")

        result = await svc._call_gemini([{"role": "user", "content": "Hi"}])
        assert result == "async result"


class TestCallOpenAI:
    @pytest.mark.asyncio
    async def test_calls_completions(self):
        mock_client = AsyncMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "OpenAI response"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        svc = _make_service(openai_client=mock_client)

        messages = [{"role": "user", "content": "Hi"}]
        result = await svc._call_openai(messages)

        assert result == "OpenAI response"
        mock_client.chat.completions.create.assert_awaited_once_with(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )


class TestChat:
    @pytest.mark.asyncio
    async def test_no_providers_returns_fallback(self):
        svc = _make_service()
        result = await svc.chat("Hello")
        assert result["ai_provider"] == "none"
        assert "trouble connecting" in result["message"]

    @pytest.mark.asyncio
    async def test_gemini_success(self):
        svc = _make_service(gemini_client=MagicMock())
        svc._call_gemini = AsyncMock(return_value="Gemini says hi!")

        result = await svc.chat("Tell me about pricing")
        assert result["message"] == "Gemini says hi!"
        assert result["ai_provider"] == "gemini"
        assert result["topic_detected"] == "pricing"

    @pytest.mark.asyncio
    async def test_gemini_fails_openai_fallback(self):
        svc = _make_service(gemini_client=MagicMock(), openai_client=MagicMock())
        svc._call_gemini = AsyncMock(side_effect=Exception("Gemini down"))
        svc._call_openai = AsyncMock(return_value="OpenAI fallback response")

        result = await svc.chat("Help with payments")
        assert result["message"] == "OpenAI fallback response"
        assert result["ai_provider"] == "openai"

    @pytest.mark.asyncio
    async def test_both_fail_returns_fallback(self):
        svc = _make_service(gemini_client=MagicMock(), openai_client=MagicMock())
        svc._call_gemini = AsyncMock(side_effect=Exception("Gemini down"))
        svc._call_openai = AsyncMock(side_effect=Exception("OpenAI down"))

        result = await svc.chat("Hello")
        assert result["ai_provider"] == "none"
        assert "trouble" in result["message"]

    @pytest.mark.asyncio
    async def test_openai_only_no_gemini(self):
        svc = _make_service(openai_client=MagicMock())
        svc._call_openai = AsyncMock(return_value="OpenAI direct")

        result = await svc.chat("Hello")
        assert result["ai_provider"] == "openai"
        assert result["message"] == "OpenAI direct"

    @pytest.mark.asyncio
    async def test_topic_context_injected(self):
        svc = _make_service(gemini_client=MagicMock())
        captured_messages = []

        async def capture_gemini(messages):
            captured_messages.extend(messages)
            return "Response"

        svc._call_gemini = capture_gemini

        await svc.chat("Help", topic="payments")
        # Should have system prompt, user message, and topic context
        system_messages = [m for m in captured_messages if m["role"] == "system"]
        assert len(system_messages) >= 2  # SYSTEM_PROMPT + topic context
        topic_msg = system_messages[-1]["content"]
        assert "payments" in topic_msg.lower()

    @pytest.mark.asyncio
    async def test_conversation_history_included(self):
        svc = _make_service(gemini_client=MagicMock())
        captured_messages = []

        async def capture_gemini(messages):
            captured_messages.extend(messages)
            return "Response"

        svc._call_gemini = capture_gemini

        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        await svc.chat("Follow up", conversation_history=history)

        user_messages = [m for m in captured_messages if m["role"] == "user"]
        assert len(user_messages) == 2  # history + current
        assert user_messages[0]["content"] == "Previous question"
        assert user_messages[1]["content"] == "Follow up"

    @pytest.mark.asyncio
    async def test_conversation_history_trimmed_to_20(self):
        svc = _make_service(gemini_client=MagicMock())
        captured_messages = []

        async def capture_gemini(messages):
            captured_messages.extend(messages)
            return "Response"

        svc._call_gemini = capture_gemini

        history = [{"role": "user", "content": f"Msg {i}"} for i in range(30)]
        await svc.chat("Latest", conversation_history=history)

        # Should have: 1 system + 20 history + 1 current user = 22
        user_messages = [m for m in captured_messages if m["role"] == "user"]
        assert len(user_messages) == 21  # 20 from history + 1 current

    @pytest.mark.asyncio
    async def test_suggested_actions_in_response(self):
        svc = _make_service(gemini_client=MagicMock())
        svc._call_gemini = AsyncMock(return_value="Here's your pricing info")

        result = await svc.chat("pricing recommendations")
        assert "suggested_actions" in result
        assert isinstance(result["suggested_actions"], list)


class TestGetTopics:
    def test_returns_structure(self):
        svc = _make_service()
        result = svc.get_topics()
        assert "topics" in result
        assert "default_greeting" in result
        assert "suggested_questions" in result
        assert len(result["topics"]) == 5


class TestGetHealth:
    def test_healthy_with_both(self):
        svc = _make_service(gemini_client=MagicMock(), openai_client=MagicMock())
        result = svc.get_health()
        assert result["status"] == "healthy"
        assert result["gemini_configured"] is True
        assert result["openai_configured"] is True
        assert result["primary_provider"] == "gemini"
        assert "gemini" in result["available_providers"]
        assert "openai" in result["available_providers"]

    def test_healthy_gemini_only(self):
        svc = _make_service(gemini_client=MagicMock())
        result = svc.get_health()
        assert result["status"] == "healthy"
        assert result["gemini_model"] == "gemini-2.0-flash-exp"
        assert result["openai_model"] is None

    def test_degraded_no_providers(self):
        svc = _make_service()
        result = svc.get_health()
        assert result["status"] == "degraded"
        assert result["gemini_configured"] is False
        assert result["openai_configured"] is False
        assert result["primary_provider"] == "none"

    def test_features_list(self):
        svc = _make_service()
        result = svc.get_health()
        assert "features" in result
        assert "gemini_primary" in result["features"]
        assert "openai_fallback" in result["features"]


        