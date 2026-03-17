"""Launch Detection API - SSE streaming endpoint."""

import json

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from core.logging import get_logger
from services.ai_trend_analysis.launch_detector import LaunchSignal, launch_detector

logger = get_logger(__name__)
router = APIRouter(prefix="/launch", tags=["Launch Detection"])


def generate_mock_signals(competitor: str, has_launch: bool = True) -> list[LaunchSignal]:
    """Generate mock signals for demo."""
    if has_launch:
        return [
            LaunchSignal(
                source="twitter",
                content=f"{competitor} just announced their new product line! Exciting features coming soon. #newlaunch",
            ),
            LaunchSignal(
                source="reddit",
                content=f"Anyone else see the {competitor} announcement? Looks like they're releasing a competitor to our favorite product.",
            ),
            LaunchSignal(
                source="news",
                content=f"{competitor} unveils next-generation product with AI features, targeting premium market segment.",
            ),
        ]
    return [
        LaunchSignal(source="twitter", content=f"Just bought from {competitor}, same great product as always."),
        LaunchSignal(source="reddit", content=f"Regular {competitor} discussion thread - nothing new to report."),
    ]


@router.post("/analyze/stream")
async def stream_launch_analysis(
    competitor: str = Form(..., description="Competitor name"),
    your_product: str = Form(..., description="Your product name"),
    simulate_launch: bool = Form(False, description="Simulate launch for demo"),
    image: UploadFile | None = File(None, description="Product screenshot"),
):
    """
    Stream launch detection analysis via SSE.

    Accepts optional image upload for multimodal analysis.
    """

    async def event_generator():
        try:
            image_data = None
            image_type = "png"

            if image:
                image_data = await image.read()
                if image.content_type:
                    image_type = image.content_type.split("/")[-1]

            signals = generate_mock_signals(competitor, has_launch=simulate_launch)

            async for msg in launch_detector.analyze(
                signals=signals,
                competitor_name=competitor,
                your_product=your_product,
                image_data=image_data,
                image_type=image_type,
            ):
                event = {
                    "agent": msg.agent.value,
                    "thought_type": msg.thought_type.value if msg.thought_type else None,
                    "content": msg.content,
                    "is_final": msg.is_final,
                    "metadata": msg.metadata,
                }
                yield f"data: {json.dumps(event)}\n\n"

            yield 'data: {"done": true}\n\n'

        except Exception as e:
            logger.error(f"Launch analysis failed: {e}")
            yield f'data: {{"error": "{e!s}"}}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/analyze/stream")
async def stream_launch_analysis_get(
    competitor: str = Query(..., description="Competitor name"),
    your_product: str = Query(..., description="Your product name"),
    simulate_launch: bool = Query(False, description="Simulate launch for demo"),
):
    """GET version for simple testing without image upload."""

    async def event_generator():
        try:
            signals = generate_mock_signals(competitor, has_launch=simulate_launch)

            async for msg in launch_detector.analyze(
                signals=signals, competitor_name=competitor, your_product=your_product
            ):
                event = {
                    "agent": msg.agent.value,
                    "thought_type": msg.thought_type.value if msg.thought_type else None,
                    "content": msg.content,
                    "is_final": msg.is_final,
                    "metadata": msg.metadata,
                }
                yield f"data: {json.dumps(event)}\n\n"

            yield 'data: {"done": true}\n\n'

        except Exception as e:
            logger.error(f"Launch analysis failed: {e}")
            yield f'data: {{"error": "{e!s}"}}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/health")
async def health():
    """Health check for launch detection service."""
    return {"status": "ok", "service": "launch-detector"}
