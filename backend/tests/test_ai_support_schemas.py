"""
Test Suite: backend/schemas/ai_support.py
Covers: ChatMessageSchema, SupportChatRequest, SupportChatResponse,
        TopicSuggestion, SupportTopicsResponse, SupportHealthResponse.

Place at: backend/tests/test_ai_support_schemas.py
Run: pytest backend/tests/test_ai_support_schemas.py -v
"""

import pytest
from pydantic import ValidationError

from schemas.ai_support import (
    ChatMessageSchema,
    SupportChatRequest,
    SupportChatResponse,
    SupportHealthResponse,
    SupportTopicsResponse,
    TopicSuggestion,
)

# =====================================================================
# ChatMessageSchema
# =====================================================================


class TestChatMessageSchema:
    def test_valid_user(self):
        m = ChatMessageSchema(role="user", content="How do I set up pricing rules?")
        assert m.role == "user"

    def test_valid_assistant(self):
        m = ChatMessageSchema(role="assistant", content="Here's how to set up rules...")
        assert m.role == "assistant"

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError):
            ChatMessageSchema(role="system", content="test")

    def test_empty_content_raises(self):
        with pytest.raises(ValidationError):
            ChatMessageSchema(role="user", content="")

    def test_content_max_length(self):
        with pytest.raises(ValidationError):
            ChatMessageSchema(role="user", content="x" * 5001)

    def test_missing_role_raises(self):
        with pytest.raises(ValidationError):
            ChatMessageSchema(content="test")

    def test_missing_content_raises(self):
        with pytest.raises(ValidationError):
            ChatMessageSchema(role="user")


# =====================================================================
# SupportChatRequest
# =====================================================================


class TestSupportChatRequest:
    def test_valid_minimal(self):
        r = SupportChatRequest(message="Help me with pricing")
        assert r.message == "Help me with pricing"
        assert r.conversation_history == []
        assert r.topic is None

    def test_valid_full(self):
        r = SupportChatRequest(
            message="How do I create a rule?",
            conversation_history=[
                ChatMessageSchema(role="user", content="Hello"),
                ChatMessageSchema(role="assistant", content="Hi! How can I help?"),
            ],
            topic="pricing_rules",
        )
        assert len(r.conversation_history) == 2
        assert r.topic == "pricing_rules"

    def test_empty_message_raises(self):
        with pytest.raises(ValidationError):
            SupportChatRequest(message="")

    def test_message_max_length(self):
        with pytest.raises(ValidationError):
            SupportChatRequest(message="x" * 2001)

    def test_missing_message_raises(self):
        with pytest.raises(ValidationError):
            SupportChatRequest()


# =====================================================================
# SupportChatResponse
# =====================================================================


class TestSupportChatResponse:
    def test_valid_minimal(self):
        r = SupportChatResponse(message="Here's how to do it...")
        assert r.topic_detected is None
        assert r.suggested_actions == []
        assert r.timestamp  # auto-generated

    def test_valid_full(self):
        r = SupportChatResponse(
            message="You can create a pricing rule by...",
            topic_detected="pricing_rules",
            suggested_actions=["Go to Settings > Pricing Rules", "Click Create Rule"],
            timestamp="2026-02-08T12:00:00",
        )
        assert r.topic_detected == "pricing_rules"
        assert len(r.suggested_actions) == 2


# =====================================================================
# TopicSuggestion
# =====================================================================


class TestTopicSuggestion:
    def test_valid(self):
        t = TopicSuggestion(
            id="pricing",
            label="Pricing Rules",
            description="Learn how to set up and manage pricing rules",
        )
        assert t.id == "pricing"

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            TopicSuggestion(id="pricing", label="Pricing")


# =====================================================================
# SupportTopicsResponse
# =====================================================================


class TestSupportTopicsResponse:
    def test_valid(self):
        r = SupportTopicsResponse(
            topics=[
                TopicSuggestion(id="pricing", label="Pricing", description="Pricing help"),
                TopicSuggestion(id="sentiment", label="Sentiment", description="Sentiment help"),
            ],
            default_greeting="Hi! How can I help you today?",
            suggested_questions=["How do I set up pricing rules?", "What is sentiment analysis?"],
        )
        assert len(r.topics) == 2
        assert len(r.suggested_questions) == 2

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            SupportTopicsResponse(topics=[])


# =====================================================================
# SupportHealthResponse
# =====================================================================


class TestSupportHealthResponse:
    def test_valid_defaults(self):
        r = SupportHealthResponse(
            status="ok",
            openai_configured=True,
            features=["chat", "topic_detection"],
        )
        assert r.service == "ai_support"
        assert r.model == "gpt-4o-mini"

    def test_valid_custom(self):
        r = SupportHealthResponse(
            status="degraded",
            service="ai_support_v2",
            openai_configured=False,
            model="gpt-4o",
            features=[],
        )
        assert r.model == "gpt-4o"
        assert r.openai_configured is False

    def test_missing_status_raises(self):
        with pytest.raises(ValidationError):
            SupportHealthResponse(
                openai_configured=True,
                features=[],
            )
