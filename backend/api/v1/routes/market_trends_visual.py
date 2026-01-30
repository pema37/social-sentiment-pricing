"""
Market Trends Visual - SSE Streaming Endpoint
Multimodal trend analysis with 3-agent pipeline.
"""

import json
import random
from typing import Optional
from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from services.ai_trend_analysis.market_trends_visual import market_trends_analyzer

router = APIRouter(prefix="/trends-visual", tags=["Market Trends Visual"])


def generate_mock_market_data(product: str, category: str, simulate_trend: str) -> dict:
    """Generate realistic mock market data for demo."""
    
    base_sentiment = random.uniform(0.3, 0.8)
    
    if simulate_trend == "bullish":
        sentiment_score = min(base_sentiment + 0.3, 0.95)
        price_change = random.uniform(5, 15)
        volume_trend = "increasing"
        sentiment_trend = "improving"
    elif simulate_trend == "bearish":
        sentiment_score = max(base_sentiment - 0.3, 0.1)
        price_change = random.uniform(-15, -5)
        volume_trend = "decreasing"
        sentiment_trend = "declining"
    else:
        sentiment_score = base_sentiment
        price_change = random.uniform(-3, 3)
        volume_trend = "stable"
        sentiment_trend = "stable"
    
    return {
        "product": product,
        "category": category,
        "sentiment_score": round(sentiment_score, 2),
        "sentiment_trend": sentiment_trend,
        "volume_24h": random.randint(1000, 50000),
        "volume_trend": volume_trend,
        "price_change_7d": round(price_change, 1),
        "social_mentions": random.randint(50, 500),
        "competitor_activity": random.choice(["low", "moderate", "high"]),
        "market_position": random.choice(["leader", "challenger", "follower"])
    }


async def stream_analysis(
    product: str,
    category: str,
    simulate_trend: str,
    image_bytes: Optional[bytes] = None
):
    """Stream market trend analysis."""
    
    market_data = generate_mock_market_data(product, category, simulate_trend)
    
    yield f"data: {json.dumps({'agent': 'system', 'content': f'Analyzing market trends for {product}...'})}\n\n"
    
    try:
        async for msg in market_trends_analyzer.analyze_stream(
            product=product,
            category=category,
            market_data=market_data,
            image_bytes=image_bytes
        ):
            yield f"data: {json.dumps({
                'agent': msg.agent,
                'thought_type': msg.thought_type,
                'content': msg.content,
                'is_final': msg.is_final,
                'metadata': msg.metadata or {}
            })}\n\n"
        
        yield f"data: {json.dumps({'done': True, 'market_data': market_data})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.get("/analyze/stream")
async def analyze_trends_stream(
    product: str = Query(..., description="Product name"),
    category: str = Query("electronics", description="Product category"),
    simulate_trend: str = Query("neutral", description="Trend simulation: bullish, bearish, neutral")
):
    """Stream market trend analysis (text-only, no image)."""
    
    return StreamingResponse(
        stream_analysis(product, category, simulate_trend),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/analyze/stream")
async def analyze_trends_stream_with_image(
    product: str = Form(...),
    category: str = Form("electronics"),
    simulate_trend: str = Form("neutral"),
    image: Optional[UploadFile] = File(None)
):
    """Stream market trend analysis with optional chart/graph image."""
    
    image_bytes = None
    if image:
        image_bytes = await image.read()
    
    return StreamingResponse(
        stream_analysis(product, category, simulate_trend, image_bytes),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )




