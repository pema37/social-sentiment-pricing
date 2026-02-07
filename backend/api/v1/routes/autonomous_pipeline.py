"""
Autonomous Pipeline API Routes
VETROX AGENTIC 3.0 - Track 3: The Hand

Public endpoints that let judges trigger and observe the autonomous
pricing pipeline. No auth required for demo routes.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.services.ai_trend_analysis.autonomous_orchestrator import (
    AutonomousOrchestrator,
    AutonomousTrigger,
    PricingDecision,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autonomous", tags=["Autonomous Pipeline"])

# Singleton orchestrator and trigger
_orchestrator = AutonomousOrchestrator()
_trigger = AutonomousTrigger()


# ---------------------------------------------------------------------------
# Request/Response Schemas
# ---------------------------------------------------------------------------

class PipelineTriggerRequest(BaseModel):
    """Request to trigger the autonomous pipeline."""
    product_id: str = Field(default="demo-product-001", description="Product to analyze")
    current_price: float = Field(default=99.99, description="Current product price in USD")
    product_category: str = Field(default="electronics", description="Product category")
    cost_basis: float = Field(default=45.00, description="Cost to produce/source")
    margin_floor_pct: float = Field(default=20.0, description="Minimum margin percentage")


class PipelineResponse(BaseModel):
    """Full pipeline execution result."""
    success: bool
    decision: PricingDecision
    pipeline_duration_ms: int
    agents_executed: list[str] = ["Scout", "Analyst", "Strategist"]


class MonitoringStartRequest(BaseModel):
    """Request to start autonomous monitoring."""
    product_id: str = Field(default="demo-product-001")
    current_price: float = Field(default=99.99)
    check_interval_seconds: int = Field(default=300, ge=60, le=3600)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/trigger", response_model=PipelineResponse)
async def trigger_pipeline(request: PipelineTriggerRequest):
    """
    🚀 Trigger the full autonomous pricing pipeline.

    Executes: Scout → Analyst → Strategist → On-Chain
    No human intervention required.

    This is the core demonstration for VETROX AGENTIC 3.0 Track 3 "The Hand."
    """
    import time
    start = time.monotonic()

    try:
        decision = await _orchestrator.run_pipeline(
            product_id=request.product_id,
            current_price=request.current_price,
            product_category=request.product_category,
            cost_basis=request.cost_basis,
            margin_floor_pct=request.margin_floor_pct,
        )

        duration_ms = int((time.monotonic() - start) * 1000)

        return PipelineResponse(
            success=True,
            decision=decision,
            pipeline_duration_ms=duration_ms,
        )

    except Exception as e:
        logger.exception(f"Pipeline trigger failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/{product_id}")
async def stream_pipeline(
    product_id: str,
    current_price: float = Query(default=99.99),
    product_category: str = Query(default="electronics"),
    cost_basis: float = Query(default=45.00),
    margin_floor_pct: float = Query(default=20.0),
):
    """
    📡 Stream the autonomous pipeline execution via Server-Sent Events.

    Watch each agent's reasoning in real-time:
    - Scout: Market signal detection
    - Analyst: Sentiment + risk assessment
    - Strategist: Price calculation + on-chain execution

    Connect with EventSource in the browser or curl -N.
    """
    return StreamingResponse(
        _orchestrator.run_pipeline_streaming(
            product_id=product_id,
            current_price=current_price,
            product_category=product_category,
            cost_basis=cost_basis,
            margin_floor_pct=margin_floor_pct,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@router.post("/monitor/start")
async def start_monitoring(
    request: MonitoringStartRequest,
    background_tasks: BackgroundTasks,
):
    """
    🔄 Start autonomous monitoring loop.

    The system will continuously scan for market changes and
    automatically trigger the pricing pipeline when signals are detected.
    This runs in the background — no human oversight needed.
    """
    background_tasks.add_task(
        _trigger.start_monitoring,
        product_id=request.product_id,
        check_interval_seconds=request.check_interval_seconds,
        current_price=request.current_price,
    )
    return {
        "status": "monitoring_started",
        "product_id": request.product_id,
        "interval_seconds": request.check_interval_seconds,
        "message": "Autonomous monitoring is now active. The system will detect and respond to market changes without human intervention.",
    }


@router.post("/monitor/stop")
async def stop_monitoring():
    """⏹️ Stop the autonomous monitoring loop."""
    _trigger.stop_monitoring()
    return {"status": "monitoring_stopped"}


@router.get("/health")
async def autonomous_health():
    """
    Health check for the autonomous pipeline.
    Verifies Gemini API connectivity and agent readiness.
    """
    try:
        from google import genai
        test_client = genai.Client()
        # Quick model check
        response = test_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents="Return 'OK' if you can read this.",
            config={"thinking_config": {"thinking_level": "minimal"}},
        )
        gemini_status = "connected" if response.text else "error"
    except Exception as e:
        gemini_status = f"error: {str(e)}"

    return {
        "status": "healthy" if gemini_status == "connected" else "degraded",
        "gemini_api": gemini_status,
        "model": "gemini-3-flash-preview",
        "agents": {
            "scout": "ready",
            "analyst": "ready",
            "strategist": "ready",
        },
        "pipeline": "autonomous",
        "track": "VETROX AGENTIC 3.0 - The Hand",
    }



