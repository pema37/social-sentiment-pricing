# backend/api/v1/routes/health.py

from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db.session import get_session
from schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])

START_TIME = datetime.utcnow()


@router.get("/", response_model=HealthResponse)
async def health_check(session: AsyncSession = Depends(get_session)):
    """Basic health check."""

    # Test DB connection
    try:
        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    uptime_seconds = (datetime.utcnow() - START_TIME).total_seconds()

    return HealthResponse(
        status="ok",
        api="Social Sentiment Pricing API",
        version="v1",
        database=db_status,
        uptime_seconds=uptime_seconds,
        timestamp_utc=datetime.utcnow().isoformat(),
    )
