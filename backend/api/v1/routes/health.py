# backend/api/v1/routes/health.py
"""
Health check endpoints for monitoring and orchestration.
"""

from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from db.session import get_session
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])

START_TIME = datetime.utcnow()


async def check_database(session: AsyncSession) -> Dict[str, Any]:
    """Check database connectivity."""
    try:
        start = datetime.utcnow()
        await session.execute(text("SELECT 1"))
        latency_ms = (datetime.utcnow() - start).total_seconds() * 1000
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


def check_redis_sync() -> Dict[str, Any]:
    """Check Redis connectivity (sync version)."""
    try:
        import redis
        start = datetime.utcnow()
        r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        r.ping()
        r.close()
        latency_ms = (datetime.utcnow() - start).total_seconds() * 1000
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

    uptime_seconds = (datetime.utcnow() - START_TIME).total_seconds()

    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
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
    redis_check = check_redis_sync()
    
    db_healthy = db_check.get("status") == "healthy"
    
    response_data = {
        "status": "ready" if db_healthy else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
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
    redis_check = check_redis_sync()
    
    db_healthy = db_check.get("status") == "healthy"
    redis_healthy = redis_check.get("status") == "healthy"
    
    if db_healthy and redis_healthy:
        overall = "healthy"
    elif db_healthy:
        overall = "degraded"
    else:
        overall = "unhealthy"
    
    uptime_seconds = (datetime.utcnow() - START_TIME).total_seconds()
    
    return {
        "status": overall,
        "timestamp": datetime.utcnow().isoformat(),
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
    
    from core.alerting import send_alert, AlertSeverity
    
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
