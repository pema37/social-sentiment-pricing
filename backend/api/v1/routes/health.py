# backend/api/v1/routes/health.py
"""
Health check endpoints for monitoring and orchestration.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.logging import get_logger
from db.session import get_session

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])

START_TIME = datetime.now(UTC)


async def check_database(session: AsyncSession) -> dict[str, Any]:
    """Check database connectivity."""
    try:
        start = datetime.now(UTC)
        await session.execute(text("SELECT 1"))
        latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def check_redis() -> dict[str, Any]:
    """Check Redis connectivity (non-blocking)."""
    try:
        import redis.asyncio as aioredis

        start = datetime.now(UTC)
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        await r.ping()
        await r.aclose()
        latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
        }
    except Exception as e:
        error_msg = str(e)
        if "Connection refused" in error_msg:
            return {"status": "unavailable", "error": "Redis not running"}
        return {"status": "unhealthy", "error": error_msg}


@router.get("")
@router.get("/")
async def health_check(session: AsyncSession = Depends(get_session)):
    """Basic health check."""
    try:
        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "error"

    uptime_seconds = (datetime.now(UTC) - START_TIME).total_seconds()

    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "uptime_seconds": round(uptime_seconds, 2),
    }


@router.get("/live")
async def liveness_probe():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness_probe(session: AsyncSession = Depends(get_session)):
    """Kubernetes readiness probe."""
    db_check = await check_database(session)
    redis_check = await check_redis()

    db_healthy = db_check.get("status") == "healthy"

    response_data = {
        "status": "ready" if db_healthy else "not_ready",
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {
            "database": db_check,
            "redis": redis_check,
        },
    }

    if not db_healthy:
        return JSONResponse(content=response_data, status_code=503)

    return response_data


@router.get("/detailed")
async def detailed_health_check(session: AsyncSession = Depends(get_session)):
    """Detailed health check."""
    db_check = await check_database(session)
    redis_check = await check_redis()

    db_healthy = db_check.get("status") == "healthy"
    redis_healthy = redis_check.get("status") == "healthy"

    if db_healthy and redis_healthy:
        overall = "healthy"
    elif db_healthy:
        overall = "degraded"
    else:
        overall = "unhealthy"

    uptime_seconds = (datetime.now(UTC) - START_TIME).total_seconds()

    return {
        "status": overall,
        "timestamp": datetime.now(UTC).isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(uptime_seconds, 2),
        "checks": {
            "database": db_check,
            "redis": redis_check,
        },
        "config": {
            "debug": settings.DEBUG,
            "sentry_enabled": bool(settings.SENTRY_DSN),
            "log_level": settings.LOG_LEVEL,
        },
    }


@router.post("/test-alert")
async def test_alert(severity: str = "info"):
    """Test alerting system (dev only)."""
    if settings.ENVIRONMENT == "production":
        return {"error": "Not available in production"}

    from core.alerting import AlertSeverity, send_alert

    sev_map = {
        "info": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "error": AlertSeverity.ERROR,
        "critical": AlertSeverity.CRITICAL,
    }

    sev = sev_map.get(severity, AlertSeverity.INFO)

    results = await send_alert(
        title="Test Alert",
        message="This is a test alert from SSP health check endpoint.",
        severity=sev,
        fields={
            "Environment": settings.ENVIRONMENT,
            "Severity": severity,
        },
    )

    return {
        "status": "sent",
        "results": results,
        "note": "Check Slack/email if configured",
    }
