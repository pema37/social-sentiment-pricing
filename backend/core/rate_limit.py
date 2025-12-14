# backend/core/rate_limit.py
"""
Rate limiting configuration for API endpoints.
Uses slowapi with Redis backend for distributed rate limiting.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from core.config import settings


def get_client_ip(request: Request) -> str:
    """
    Get client IP address, handling proxies.
    Checks X-Forwarded-For header first (for reverse proxies).
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Initialize limiter with Redis storage
# Falls back to in-memory if Redis unavailable
try:
    limiter = Limiter(
        key_func=get_client_ip,
        storage_uri=settings.REDIS_URL,
        strategy="fixed-window",
        default_limits=["100/minute"],  # Default for all endpoints
    )
    print("Rate limiter initialized with Redis backend")
except Exception as e:
    print(f"Redis unavailable for rate limiting, using in-memory: {e}")
    limiter = Limiter(
        key_func=get_client_ip,
        strategy="fixed-window",
        default_limits=["100/minute"],
    )


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
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
AUTH_RATE_LIMIT = "5/minute"
REGISTER_RATE_LIMIT = "3/minute"
PASSWORD_RESET_RATE_LIMIT = "3/minute"

# Write operations - moderate limits
WRITE_RATE_LIMIT = "30/minute"      # POST, PUT, PATCH, DELETE
BULK_RATE_LIMIT = "10/minute"       # Bulk operations, imports, syncs

# Read operations - lighter limits  
READ_RATE_LIMIT = "100/minute"      # GET requests (default)

# Expensive operations - strict limits
ANALYSIS_RATE_LIMIT = "20/minute"   # Sentiment analysis, AI calls
EXPORT_RATE_LIMIT = "5/minute"      # CSV exports, reports

# Webhooks - allow more (external services)
WEBHOOK_RATE_LIMIT = "200/minute"
