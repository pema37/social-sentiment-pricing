# backend/core/rate_limit.py
"""
Rate limiting configuration for API endpoints.
Uses slowapi with Redis backend for distributed rate limiting.

FIX (2026-01-24): Added explicit type annotations for Limiter to fix Pylance warnings.
FIX (2026-03-29): AP-033 — Close Redis test connection after ping.
Previously the test Redis client `r` was created, pinged, and then abandoned
without calling r.close(). Each app startup leaked one connection from the
connection pool. Fixed: call r.close() in a finally block after the ping.
"""

import logging
from collections.abc import Callable
from typing import Any, TypeVar, cast

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core.config import settings

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def get_client_ip(request: Request) -> str:
    """
    Get client IP address, handling proxies securely.

    Uses the rightmost IP in X-Forwarded-For (appended by the nearest
    trusted proxy, e.g. Railway) rather than the leftmost (which the
    client can spoof). Falls back to the direct connection IP.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
        if ips:
            return ips[-1]
    return get_remote_address(request)


def _create_limiter() -> Limiter:
    """
    Create rate limiter with Redis if available, otherwise memory.
    Tests the Redis connection before using it.
    """
    redis_url = settings.REDIS_URL

    if redis_url and "localhost" not in redis_url and "127.0.0.1" not in redis_url:
        try:
            import redis

            # AP-033: Use a context variable so we can close it in finally.
            r = redis.from_url(redis_url, socket_connect_timeout=2)
            try:
                r.ping()
            finally:
                # AP-033: Always close the test connection — previously leaked.
                # Without this, each app restart consumed one connection from
                # the pool and never returned it.
                r.close()

            logger.info("Rate limiter initialized with Redis backend")
            return Limiter(
                key_func=get_client_ip,
                storage_uri=redis_url,
                strategy="fixed-window",
                default_limits=["100/minute"],
            )
        except Exception as e:
            logger.warning(
                "Redis connection failed for rate limiter, falling back to in-memory storage. "
                "Rate limiting will not be shared across workers. Error: %s",
                e,
            )

    logger.warning(
        "Rate limiter initialized with in-memory backend — "
        "rate limits are per-worker and reset on restart"
    )
    return Limiter(
        key_func=get_client_ip,
        storage_uri="memory://",
        strategy="fixed-window",
        default_limits=["100/minute"],
    )


limiter: Limiter = _create_limiter()


def rate_limit(limit_string: str) -> Callable[[F], F]:
    """
    Typed rate limit decorator.

    Usage:
        @rate_limit(WRITE_RATE_LIMIT)
        async def my_endpoint(request: Request, ...):
            ...
    """

    def decorator(func: F) -> F:
        return cast("F", limiter.limit(limit_string)(func))

    return decorator


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."},
        headers={"Retry-After": "60"},
    )


# ───────────────────── Rate Limit Tiers ───────────────────── #

AUTH_RATE_LIMIT: str = "5/minute"
REGISTER_RATE_LIMIT: str = "3/minute"
PASSWORD_RESET_RATE_LIMIT: str = "3/minute"

WRITE_RATE_LIMIT: str = "30/minute"
BULK_RATE_LIMIT: str = "10/minute"

READ_RATE_LIMIT: str = "100/minute"

ANALYSIS_RATE_LIMIT: str = "20/minute"
EXPORT_RATE_LIMIT: str = "5/minute"

WEBHOOK_RATE_LIMIT: str = "200/minute"



