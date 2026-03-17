"""
Market Intelligence API Routes

Public demo endpoints for DeveloperWeek 2026 Hackathon - You.com Challenge Track.
No authentication required - this is a public demo.

Endpoints:
- POST /api/v1/market-intelligence/analyze - Streaming multi-agent analysis via SSE
- GET  /api/v1/market-intelligence/analyze - Same as POST (easy browser/curl testing)
- GET  /api/v1/market-intelligence/health  - Health check for demo
"""

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.config import settings
from core.logging import get_logger
from services.market_intelligence import (
    IntelligenceRequest,
    MarketIntelligencePipeline,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/market-intelligence", tags=["Market Intelligence Demo"])


# =============================================================================
# SCHEMAS
# =============================================================================


class IntelligenceQueryRequest(BaseModel):
    """Request body for market intelligence analysis."""

    product_name: str = Field(..., min_length=1, max_length=200, description="Product name to analyze")
    current_price: float | None = Field(default=None, gt=0, description="Your current price")
    brand: str | None = Field(default=None, max_length=100, description="Brand name")
    category: str | None = Field(default=None, max_length=100, description="Product category")
    features: list[str] | None = Field(default=None, description="List of product features")


class IntelligenceHealthResponse(BaseModel):
    """Health check response."""

    status: str
    youcom_configured: bool
    gemini_configured: bool
    demo_ready: bool
    message: str


# =============================================================================
# HELPER
# =============================================================================


async def generate_sse_stream(request: IntelligenceRequest):
    """Generate Server-Sent Events from the multi-agent pipeline."""
    pipeline: MarketIntelligencePipeline | None = None
    try:
        pipeline = MarketIntelligencePipeline()

        async for event in pipeline.run(request):
            data = json.dumps(event.to_dict())
            yield f"data: {data}\n\n"

        # Done signal
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        logger.error(f"SSE stream error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

    finally:
        if pipeline:
            await pipeline.close()


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/health", response_model=IntelligenceHealthResponse)
async def intelligence_health_check():
    """
    Health check for the Market Intelligence demo.

    Verifies that You.com and Gemini APIs are configured.
    """
    youcom_ok = bool(getattr(settings, "YOUCOM_API_KEY", None))
    gemini_ok = bool(settings.GEMINI_API_KEY)
    demo_ready = youcom_ok  # Gemini is optional (fallback exists)

    if demo_ready:
        msg = "Market Intelligence demo is ready!"
        if not gemini_ok:
            msg += " (Gemini not configured — using heuristic fallback)"
    else:
        msg = "You.com API key not configured. Set YOUCOM_API_KEY in .env"

    return IntelligenceHealthResponse(
        status="healthy" if demo_ready else "degraded",
        youcom_configured=youcom_ok,
        gemini_configured=gemini_ok,
        demo_ready=demo_ready,
        message=msg,
    )


@router.post("/analyze")
async def analyze_market_streaming(body: IntelligenceQueryRequest):
    """
    Analyze a product's market position with streaming multi-agent response.

    Runs Scout → Analyst → Strategist pipeline:
    1. Scout searches live web via You.com APIs (parallel searches)
    2. Analyst synthesizes market position via Gemini
    3. Strategist recommends optimal price with confidence score

    Returns Server-Sent Events (SSE) stream.
    """
    youcom_key = getattr(settings, "YOUCOM_API_KEY", None)
    if not youcom_key:
        raise HTTPException(
            status_code=503,
            detail="Market Intelligence demo not available — YOUCOM_API_KEY not configured.",
        )

    request = IntelligenceRequest(
        product_name=body.product_name,
        current_price=body.current_price,
        brand=body.brand,
        category=body.category,
        features=body.features,
    )

    logger.info(
        "Starting market intelligence analysis",
        product=body.product_name,
        price=body.current_price,
        brand=body.brand,
        category=body.category,
    )

    return StreamingResponse(
        generate_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering (Railway)
        },
    )


@router.get("/analyze")
async def analyze_market_streaming_get(
    product_name: str = Query(..., min_length=1, max_length=200, description="Product name"),
    current_price: float | None = Query(default=None, gt=0, description="Your current price"),
    brand: str | None = Query(default=None, max_length=100, description="Brand name"),
    category: str | None = Query(default=None, max_length=100, description="Product category"),
):
    """
    GET version of /analyze for easy browser and curl testing.

    Example:
        curl -N "http://localhost:8000/api/v1/market-intelligence/analyze?product_name=Nike+Air+Max+90&current_price=130"
    """
    youcom_key = getattr(settings, "YOUCOM_API_KEY", None)
    if not youcom_key:
        raise HTTPException(
            status_code=503,
            detail="Market Intelligence demo not available — YOUCOM_API_KEY not configured.",
        )

    request = IntelligenceRequest(
        product_name=product_name,
        current_price=current_price,
        brand=brand,
        category=category,
    )

    return StreamingResponse(
        generate_sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
