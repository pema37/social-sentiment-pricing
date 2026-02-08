# backend/schemas/ai_support.py
"""
Pydantic schemas for AI Support Chat feature.
"""

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field


class ChatMessageSchema(BaseModel):
    """A single message in the conversation history."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=5000)


class SupportChatRequest(BaseModel):
    """Request body for POST /api/v1/support/chat"""
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_history: List[ChatMessageSchema] = Field(default_factory=list)
    topic: Optional[str] = Field(default=None)


class SupportChatResponse(BaseModel):
    """Response body from POST /api/v1/support/chat"""
    message: str
    topic_detected: Optional[str] = None
    suggested_actions: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())



class TopicSuggestion(BaseModel):
    """A single topic suggestion."""
    id: str
    label: str
    description: str


class SupportTopicsResponse(BaseModel):
    """Response body from GET /api/v1/support/topics"""
    topics: List[TopicSuggestion]
    default_greeting: str
    suggested_questions: List[str]


class SupportHealthResponse(BaseModel):
    """Response body from GET /api/v1/support/health"""
    status: str
    service: str = "ai_support"
    openai_configured: bool
    model: str = "gpt-4o-mini"
    features: List[str]

