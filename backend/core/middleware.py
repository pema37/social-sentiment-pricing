# backend/core/middleware.py
"""
Middleware for request tracing and monitoring.
"""

import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from core.logging import get_logger, set_correlation_id

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    - Assigns correlation IDs to requests
    - Logs request/response details
    - Tracks request duration
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        set_correlation_id(correlation_id)

        # Start timing
        start_time = time.perf_counter()

        # Get request details
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # Log request
        logger.info(
            "Request started",
            method=method,
            path=path,
            client_ip=client_ip,
        )

        # Process request
        try:
            response = await call_next(request)
        except Exception as e:
            # Log error and re-raise
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Request failed",
                method=method,
                path=path,
                duration_ms=round(duration_ms, 2),
                error=str(e),
            )
            raise

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        # Log response (skip health checks to reduce noise)
        if not any(p in path for p in ["/health", "/ready", "/live"]):
            log_level = "info" if response.status_code < 400 else "warning"
            getattr(logger, log_level)(
                "Request completed",
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

        return response


class UserContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to set user context for logging and error tracking.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # User context is set after authentication in the route handlers
        # This middleware just ensures clean state
        response = await call_next(request)
        return response
