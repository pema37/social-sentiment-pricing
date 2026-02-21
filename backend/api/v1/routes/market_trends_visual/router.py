"""
Market Trends Visual - API Router

Thin routing layer that:
- Defines API endpoints
- Validates input via Pydantic schemas
- Delegates business logic to service layer
- Formats responses

Follows FastAPI best practices with clear separation from business logic.
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from core.logging import get_logger

from .schemas import MarketDataInput, TrendAnalysisResponse, TrendHealthResponse
from .service import market_trends_analyzer

logger = get_logger(__name__)

router = APIRouter(prefix="/trends-visual", tags=["Market Trends Visual"])


# =========================================================================
# ENDPOINTS
# =========================================================================

@router.post("/analyze", response_model=TrendAnalysisResponse)
async def analyze_trends(data: MarketDataInput):
    """
    Analyze market trends for a product (non-streaming).
    
    Runs all three agents (Observer → Analyst → Forecaster) and returns
    a summary of the analysis.
    """
    try:
        market_data = data.to_dict()
        
        # Collect all messages
        message_count = 0
        async for msg in market_trends_analyzer.analyze_stream(
            product=data.product,
            category=data.category,
            market_data=market_data
        ):
            message_count += 1
        
        return TrendAnalysisResponse(
            status="success",
            message=f"Analysis complete. {message_count} messages generated.",
            product=data.product,
            category=data.category,
            message_count=message_count
        )
        
    except Exception as e:
        logger.error(f"Trend analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/stream")
async def analyze_trends_stream(data: MarketDataInput):
    """
    Analyze market trends with streaming response.
    
    Returns Server-Sent Events (SSE) with real-time analysis updates
    from each agent as they process.
    
    Event format:
    ```
    data: {"agent": "observer", "thought_type": "observation", "content": "...", "is_final": false}
    ```
    """
    market_data = data.to_dict()
    
    async def generate():
        try:
            async for msg in market_trends_analyzer.analyze_stream(
                product=data.product,
                category=data.category,
                market_data=market_data
            ):
                yield f"data: {json.dumps(msg.to_dict())}\n\n"
            
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming analysis failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@router.post("/analyze/with-image")
async def analyze_trends_with_image(
    product: str = Form(..., description="Product name"),
    category: str = Form(..., description="Product category"),
    sentiment_score: float = Form(0.0),
    sentiment_trend: str = Form("stable"),
    volume_24h: int = Form(0),
    volume_trend: str = Form("stable"),
    price_change_7d: float = Form(0.0),
    price_change_30d: float = Form(0.0),
    social_mentions: int = Form(0),
    social_trend: str = Form("stable"),
    competitor_activity: str = Form("normal"),
    market_position: str = Form("mid"),
    seasonality: str = Form("normal"),
    image: UploadFile = File(..., description="Chart/graph image for visual analysis")
):
    """
    Analyze market trends including visual chart analysis.
    
    Accepts an image file (chart/graph) for multimodal analysis.
    The Observer agent will analyze the chart patterns in addition
    to the numerical market data.
    
    Returns streaming SSE response.
    """
    # Validate image
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Read image
    image_bytes = await image.read()
    image_type = image.content_type.split("/")[1] if image.content_type else "png"
    
    market_data = {
        "sentiment_score": sentiment_score,
        "sentiment_trend": sentiment_trend,
        "volume_24h": volume_24h,
        "volume_trend": volume_trend,
        "price_change_7d": price_change_7d,
        "price_change_30d": price_change_30d,
        "social_mentions": social_mentions,
        "social_trend": social_trend,
        "competitor_activity": competitor_activity,
        "market_position": market_position,
        "seasonality": seasonality,
    }
    
    async def generate():
        try:
            async for msg in market_trends_analyzer.analyze_stream(
                product=product,
                category=category,
                market_data=market_data,
                image_bytes=image_bytes,
                image_type=image_type
            ):
                yield f"data: {json.dumps(msg.to_dict())}\n\n"
            
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/analyze/image-only")
async def analyze_image_only(
    product: str = Form(...),
    category: str = Form(...),
    image: UploadFile = File(...)
):
    """
    Analyze just a chart image without additional market data.
    
    Useful for quick visual pattern recognition on uploaded charts.
    Returns the visual analysis as plain text.
    """
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    image_bytes = await image.read()
    image_type = image.content_type.split("/")[1] if image.content_type else "png"
    
    try:
        analysis = await market_trends_analyzer.analyze_image(
            image_bytes=image_bytes,
            image_type=image_type,
            product=product,
            category=category
        )
        
        return {
            "status": "success",
            "product": product,
            "category": category,
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Image-only analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=TrendHealthResponse)
async def trends_visual_health():
    """
    Health check for trends visual analyzer.
    
    Returns service status, model info, and available agents.
    """
    return TrendHealthResponse(
        status="healthy",
        service="market-trends-visual",
        model=market_trends_analyzer.model,
        agents=["observer", "analyst", "forecaster"]
    )


@router.get("/agents")
async def list_agents():
    """
    List available analysis agents and their roles.
    """
    return {
        "agents": [
            {
                "name": "observer",
                "role": "Scans market data and visual charts for patterns",
                "outputs": ["patterns", "signals", "anomalies"]
            },
            {
                "name": "analyst", 
                "role": "Interprets correlations, drivers, and risks",
                "outputs": ["trend_strength", "risks", "opportunities"]
            },
            {
                "name": "forecaster",
                "role": "Predicts trends and recommends pricing actions",
                "outputs": ["direction", "recommendation", "timing"]
            }
        ],
        "flow": "observer → analyst → forecaster",
        "supports_multimodal": True
    }




