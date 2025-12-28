# backend/api/v1/routes/support.py
"""
AI Support Chat API routes.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException

from schemas.ai_support import (
    SupportChatRequest,
    SupportChatResponse,
    SupportTopicsResponse,
    SupportHealthResponse,
)
from services.ai_support_service import ai_support_service


router = APIRouter(prefix="/support", tags=["AI Support"])


@router.post("/chat", response_model=SupportChatResponse)
async def chat_with_support(request: SupportChatRequest) -> SupportChatResponse:
    """Send a message to the AI support assistant."""
    try:
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ] if request.conversation_history else None
        
        result = await ai_support_service.chat(
            message=request.message,
            conversation_history=history,
            topic=request.topic
        )
        
        return SupportChatResponse(
            message=result["message"],
            topic_detected=result.get("topic_detected"),
            suggested_actions=result.get("suggested_actions", []),
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/topics", response_model=SupportTopicsResponse)
async def get_support_topics() -> SupportTopicsResponse:
    """Get available support topics for the chat UI."""
    data = ai_support_service.get_topics()
    return SupportTopicsResponse(
        topics=[{"id": t["id"], "label": t["label"], "description": t["description"]} for t in data["topics"]],
        default_greeting=data["default_greeting"],
        suggested_questions=data["suggested_questions"]
    )


@router.get("/health", response_model=SupportHealthResponse)
async def support_health_check() -> SupportHealthResponse:
    """Check if AI support service is operational."""
    health = ai_support_service.get_health()
    return SupportHealthResponse(
        status=health["status"],
        service=health["service"],
        openai_configured=health["openai_configured"],
        model=health["model"],
        features=health["features"]
    )

