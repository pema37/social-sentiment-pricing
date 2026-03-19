"""
Visual Pricing Intelligence API Routes

Public demo endpoints for the Gemini 3 Hackathon.
No authentication required - this is a public demo.

Endpoints:
- POST /api/v1/visual-pricing/analyze - Upload screenshot + get streaming analysis
- POST /api/v1/visual-pricing/analyze-sync - Non-streaming version
- GET /api/v1/visual-pricing/health - Health check for demo
"""

import contextlib
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.logging import get_logger
from services.ai_trend_analysis import (
    AgentMessage,
    AgentRole,
    visual_analyzer,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/visual-pricing", tags=["Visual Pricing Demo"])


# =============================================================================
# SCHEMAS
# =============================================================================


class AnalyzeRequest(BaseModel):
    """Request body for non-file fields in analyze endpoint."""

    product_name: str = Field(..., description="Your product name")
    product_price: float = Field(..., gt=0, description="Your current price")
    product_currency: str = Field(default="USD", description="Currency code")
    product_features: list[str] | None = Field(default=None, description="List of your product features")


class AgentMessageResponse(BaseModel):
    """Single agent message in the response stream."""

    agent: str
    thought_type: str | None
    content: str
    is_final: bool
    metadata: dict | None = None


class AnalyzeResponse(BaseModel):
    """Final response from analysis."""

    success: bool
    competitor_data: dict | None = None
    analysis: dict | None = None
    recommendation: dict | None = None
    error: str | None = None


class DemoHealthResponse(BaseModel):
    """Health check response for demo."""

    status: str
    gemini_available: bool
    demo_ready: bool
    message: str


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def agent_message_to_dict(msg: AgentMessage) -> dict:
    """Convert AgentMessage to JSON-serializable dict."""
    return {
        "agent": msg.agent.value,
        "thought_type": msg.thought_type.value if msg.thought_type else None,
        "content": msg.content,
        "is_final": msg.is_final,
        "metadata": msg.metadata if msg.metadata else None,
    }


async def generate_sse_stream(
    image_data: bytes,
    image_type: str,
    product_name: str,
    product_price: float,
    product_currency: str,
    product_features: list[str],
):
    """Generate Server-Sent Events stream from agent analysis."""
    try:
        async for msg in visual_analyzer.analyze(
            image_data=image_data,
            image_type=image_type,
            your_product_name=product_name,
            your_product_price=product_price,
            your_product_currency=product_currency,
            your_product_features=product_features,
        ):
            data = json.dumps(agent_message_to_dict(msg))
            yield f"data: {data}\n\n"

        # Send done signal
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        logger.error(f"SSE stream error: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/health", response_model=DemoHealthResponse)
async def demo_health_check():
    """
    Health check for the Visual Pricing demo.

    Verifies that Gemini 3 is available and the demo is ready.
    """
    from services.ai_trend_analysis import ai_clients

    gemini_available = ai_clients.gemini3_client is not None

    return DemoHealthResponse(
        status="healthy" if gemini_available else "degraded",
        gemini_available=gemini_available,
        demo_ready=gemini_available,
        message="Visual Pricing Intelligence demo is ready!"
        if gemini_available
        else "Gemini 3 client not configured. Check GEMINI_API_KEY.",
    )


@router.post("/analyze")
async def analyze_competitor_streaming(
    screenshot: UploadFile = File(..., description="Competitor product screenshot"),
    product_name: str = Form(..., description="Your product name"),
    product_price: float = Form(..., gt=0, description="Your current price"),
    product_currency: str = Form(default="USD", description="Currency code"),
    product_features: str = Form(default="", description="Comma-separated list of features"),
):
    """
    Analyze competitor screenshot with streaming multi-agent response.

    This is the main demo endpoint. It:
    1. Accepts a competitor product screenshot
    2. Runs Scout → Analyst → Strategist agents
    3. Streams their "thinking" in real-time via SSE

    Returns Server-Sent Events (SSE) stream.
    """
    # Validate file type
    if not screenshot.content_type or not screenshot.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (PNG, JPEG, WebP, or GIF)")

    # Read image data
    image_data = await screenshot.read()

    if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Image too large. Maximum size is 10MB.")

    # Determine image type
    content_type = screenshot.content_type or "image/png"
    image_type = content_type.split("/")[1]
    if image_type not in ["png", "jpeg", "jpg", "webp", "gif"]:
        image_type = "png"
    if image_type == "jpg":
        image_type = "jpeg"

    # Parse features
    features = [f.strip() for f in product_features.split(",") if f.strip()] if product_features else []

    logger.info(f"Starting visual analysis for product: {product_name} at {product_price} {product_currency}")

    return StreamingResponse(
        generate_sse_stream(
            image_data=image_data,
            image_type=image_type,
            product_name=product_name,
            product_price=product_price,
            product_currency=product_currency,
            product_features=features,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post("/analyze-sync", response_model=AnalyzeResponse)
async def analyze_competitor_sync(
    screenshot: UploadFile = File(..., description="Competitor product screenshot"),
    product_name: str = Form(..., description="Your product name"),
    product_price: float = Form(..., gt=0, description="Your current price"),
    product_currency: str = Form(default="USD", description="Currency code"),
    product_features: str = Form(default="", description="Comma-separated list of features"),
):
    """
    Analyze competitor screenshot (non-streaming version).

    Same as /analyze but waits for complete response.
    Useful for integrations that don't support SSE.
    """
    # Validate file type
    if not screenshot.content_type or not screenshot.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (PNG, JPEG, WebP, or GIF)")

    image_data = await screenshot.read()

    if len(image_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Maximum size is 10MB.")

    content_type = screenshot.content_type or "image/png"
    image_type = content_type.split("/")[1]
    if image_type not in ["png", "jpeg", "jpg", "webp", "gif"]:
        image_type = "png"
    if image_type == "jpg":
        image_type = "jpeg"

    features = [f.strip() for f in product_features.split(",") if f.strip()] if product_features else []

    try:
        competitor_data = None
        analysis_data = None
        recommendation_data = None

        async for msg in visual_analyzer.analyze(
            image_data=image_data,
            image_type=image_type,
            your_product_name=product_name,
            your_product_price=product_price,
            your_product_currency=product_currency,
            your_product_features=features,
        ):
            # Capture final messages from each agent
            if msg.is_final:
                if msg.agent == AgentRole.SCOUT and msg.metadata:
                    competitor_data = msg.metadata.get("extracted_data")
                elif msg.agent == AgentRole.ANALYST and msg.metadata:
                    analysis_data = msg.metadata.get("analysis")
                elif msg.agent == AgentRole.STRATEGIST and msg.metadata:
                    recommendation_data = msg.metadata.get("recommendation")

        return AnalyzeResponse(
            success=True, competitor_data=competitor_data, analysis=analysis_data, recommendation=recommendation_data
        )

    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return AnalyzeResponse(success=False, error=str(e))


@router.websocket("/ws/analyze")
async def analyze_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time analysis.

    Protocol:
    1. Client connects
    2. Client sends JSON: {"image_base64": "...", "image_type": "png", "product_name": "...", ...}
    3. Server streams AgentMessage objects
    4. Server sends {"done": true} when complete
    """
    await websocket.accept()

    try:
        # Receive analysis request
        data = await websocket.receive_json()

        import base64

        # Parse request
        image_base64 = data.get("image_base64")
        if not image_base64:
            await websocket.send_json({"error": "image_base64 is required"})
            await websocket.close()
            return

        try:
            image_data = base64.b64decode(image_base64)
        except Exception:
            await websocket.send_json({"error": "Invalid base64 image data"})
            await websocket.close()
            return

        image_type = data.get("image_type", "png")
        product_name = data.get("product_name", "My Product")
        product_price = float(data.get("product_price", 0))
        product_currency = data.get("product_currency", "USD")
        product_features = data.get("product_features", [])

        if product_price <= 0:
            await websocket.send_json({"error": "product_price must be greater than 0"})
            await websocket.close()
            return

        # Stream analysis
        async for msg in visual_analyzer.analyze(
            image_data=image_data,
            image_type=image_type,
            your_product_name=product_name,
            your_product_price=product_price,
            your_product_currency=product_currency,
            your_product_features=product_features,
        ):
            await websocket.send_json(agent_message_to_dict(msg))

        # Send completion signal
        await websocket.send_json({"done": True})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        with contextlib.suppress(BaseException):
            await websocket.send_json({"error": str(e)})
    finally:
        with contextlib.suppress(BaseException):
            await websocket.close()
