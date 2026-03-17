# backend/core/exception_handlers.py
"""
Global exception handlers with alerting for critical errors.
"""

import traceback

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from core.alerting import alert_critical, alert_error
from core.config import settings
from core.logging import get_correlation_id, get_logger
from core.sentry import capture_exception

logger = get_logger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    # Log 5xx errors
    if exc.status_code >= 500:
        logger.error(
            "HTTP error",
            status_code=exc.status_code,
            detail=exc.detail,
            path=request.url.path,
        )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "correlation_id": get_correlation_id(),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Handle unhandled exceptions.
    Logs error, captures in Sentry, and sends alerts for critical errors.
    """
    correlation_id = get_correlation_id()

    # Log the full error
    logger.error(
        "Unhandled exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        traceback=traceback.format_exc(),
    )

    # Capture in Sentry
    capture_exception(exc, path=request.url.path, correlation_id=correlation_id)

    # Send alert for production errors
    if settings.ENVIRONMENT == "production":
        await alert_error(
            title=f"Unhandled Exception: {type(exc).__name__}",
            message=f"Error: {str(exc)[:200]}",
            fields={
                "Path": request.url.path,
                "Method": request.method,
                "Correlation ID": correlation_id,
            },
        )

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "correlation_id": correlation_id,
        },
    )


async def database_exception_handler(request: Request, exc: Exception):
    """Handle database exceptions with critical alerting."""
    correlation_id = get_correlation_id()

    logger.critical(
        "Database error",
        error=str(exc),
        path=request.url.path,
    )

    capture_exception(exc, path=request.url.path, correlation_id=correlation_id)

    # Database errors are critical
    if settings.ENVIRONMENT == "production":
        await alert_critical(
            title="Database Error",
            message=f"Database operation failed: {str(exc)[:200]}",
            fields={
                "Path": request.url.path,
                "Correlation ID": correlation_id,
            },
        )

    return JSONResponse(
        status_code=503,
        content={
            "error": str(exc),
            "correlation_id": correlation_id,
        },
    )
