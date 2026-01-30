"""Crisis Detection API - SSE streaming endpoint."""

import json
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from core.logging import get_logger
from services.ai_trend_analysis.crisis_detector import (
    crisis_detector, SentimentPoint
)

logger = get_logger(__name__)
router = APIRouter(prefix="/crisis", tags=["Crisis Detection"])


def generate_mock_data(product: str, crisis: bool = False) -> list[SentimentPoint]:
    """Generate mock sentiment data for demo."""
    import random
    now = datetime.now()
    data = []
    
    for i in range(24):  # 24 hours of data
        hours_ago = 24 - i
        base_score = 0.3 if not crisis else (0.3 if i < 12 else -0.4)
        
        data.append(SentimentPoint(
            timestamp=now - timedelta(hours=hours_ago),
            score=base_score + random.uniform(-0.2, 0.2),
            volume=random.randint(10, 50) if not crisis else random.randint(10, 150),
            source=random.choice(["twitter", "reddit", "news"]),
            sample_text=f"Sample mention about {product}" if random.random() > 0.5 else None
        ))
    
    return data


@router.get("/analyze/stream")
async def stream_crisis_analysis(
    product: str = Query(..., description="Product name to monitor"),
    simulate_crisis: bool = Query(False, description="Simulate crisis for demo"),
    baseline: float = Query(0.3, description="Baseline sentiment score")
):
    """
    Stream crisis detection analysis via SSE.
    
    Returns Server-Sent Events with agent thinking in real-time.
    """
    async def event_generator():
        try:
            # For demo: use mock data (replace with real DB query in production)
            data = generate_mock_data(product, crisis=simulate_crisis)
            
            async for msg in crisis_detector.analyze(data, product, baseline):
                event = {
                    "agent": msg.agent.value,
                    "thought_type": msg.thought_type.value if msg.thought_type else None,
                    "content": msg.content,
                    "is_final": msg.is_final,
                    "metadata": msg.metadata
                }
                yield f"data: {json.dumps(event)}\n\n"
            
            yield "data: {\"done\": true}\n\n"
            
        except Exception as e:
            logger.error(f"Crisis analysis failed: {e}")
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/health")
async def health():
    """Health check for crisis detection service."""
    return {"status": "ok", "service": "crisis-detector"}



