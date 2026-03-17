# backend/core/rate_limit.py
"""
Rate limiting configuration for API endpoints.
Uses slowapi with Redis backend for distributed rate limiting.

FIX (2026-01-24): Added explicit type annotations for Limiter to fix Pylance warnings.
"""

from collections.abc import Callable
from typing import Any, TypeVar, cast

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core.config import settings

# Type variable for preserving function signatures
F = TypeVar("F", bound=Callable[..., Any])


def get_client_ip(request: Request) -> str:
    """
    Get client IP address, handling proxies.
    Checks X-Forwarded-For header first (for reverse proxies).
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _create_limiter() -> Limiter:
    """
    Create rate limiter with Redis if available, otherwise memory.
    Actually tests Redis connection before using it.
    """
    redis_url = settings.REDIS_URL

    # Check if Redis URL is configured and not localhost (won't work in production)
    if redis_url and "localhost" not in redis_url and "127.0.0.1" not in redis_url:
        try:
            # Test the connection before committing to Redis
            import redis

            r = redis.from_url(redis_url, socket_connect_timeout=2)
            r.ping()
            print("Rate limiter initialized with Redis backend")
            return Limiter(
                key_func=get_client_ip,
                storage_uri=redis_url,
                strategy="fixed-window",
                default_limits=["100/minute"],
            )
        except Exception as e:
            print(f"Redis connection failed, falling back to memory: {e}")

    # Fallback to in-memory storage
    print("Rate limiter initialized with in-memory backend")
    return Limiter(
        key_func=get_client_ip,
        storage_uri="memory://",
        strategy="fixed-window",
        default_limits=["100/minute"],
    )


# Initialize the limiter with explicit type
limiter: Limiter = _create_limiter()


def rate_limit(limit_string: str) -> Callable[[F], F]:
    """
    Typed rate limit decorator.

    Wraps slowapi's limiter.limit() with proper type hints.

    Usage:
        @rate_limit(WRITE_RATE_LIMIT)
        async def my_endpoint(request: Request, ...):
            ...
    """

    def decorator(func: F) -> F:
        # Apply slowapi's limiter and cast to preserve the function type
        return cast("F", limiter.limit(limit_string)(func))

    return decorator


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please try again later.",
        },
        headers={"Retry-After": "60"},
    )


# ───────────────────── Rate Limit Tiers ───────────────────── #

# Auth endpoints - strictest limits (prevent brute force)
AUTH_RATE_LIMIT: str = "5/minute"
REGISTER_RATE_LIMIT: str = "3/minute"
PASSWORD_RESET_RATE_LIMIT: str = "3/minute"

# Write operations - moderate limits
WRITE_RATE_LIMIT: str = "30/minute"  # POST, PUT, PATCH, DELETE
BULK_RATE_LIMIT: str = "10/minute"  # Bulk operations, imports, syncs

# Read operations - lighter limits
READ_RATE_LIMIT: str = "100/minute"  # GET requests (default)

# Expensive operations - strict limits
ANALYSIS_RATE_LIMIT: str = "20/minute"  # Sentiment analysis, AI calls
EXPORT_RATE_LIMIT: str = "5/minute"  # CSV exports, reports

# Webhooks - allow more (external services)
WEBHOOK_RATE_LIMIT: str = "200/minute"
