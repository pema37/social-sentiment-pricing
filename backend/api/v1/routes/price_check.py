"""
Price Check SSE endpoint — public, unauthenticated, rate-limited.

GET /api/v1/audit/price-check/stream?store_url=...&email=...&category=...

Streams Server-Sent Events as the Scout → Analyst → Strategist pipeline
runs. Each event is a JSON object with {agent, status, message, data}.

The final event has agent="complete" and data=full PriceCheckReport.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from db.session import get_session
from services.audit.audit_orchestrator import run_price_check

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["price-check"])

# ── CORS allowlist ────────────────────────────────────────────────────

AUDIT_ALLOWED_ORIGINS = {
    "https://getactualprice.com",
    "https://www.getactualprice.com",
    "https://ssp-staging.vercel.app",
    "https://ssp-staging-f3zwnp7el-msakou-bcitcas-projects.vercel.app",
    "http://localhost:4321",  # Astro dev
    "http://localhost:3000",  # Next.js dev
}


def _cors_origin(request: Request) -> str:
    """
    Return the correct Access-Control-Allow-Origin value.
    If the request origin is in the allowlist, echo it back.
    Otherwise return the primary production origin.
    """
    origin = request.headers.get("origin", "")
    if origin in AUDIT_ALLOWED_ORIGINS:
        return origin
    return "https://getactualprice.com"


# ── Distributed rate limiter (Redis-backed) ──────────────────────────

RATE_LIMIT_MAX = 10  # max requests
RATE_LIMIT_WINDOW = 3600  # per hour (seconds)

_redis_client = None


def _get_redis():
    """Lazy-init a Redis client for rate limiting."""
    global _redis_client
    if _redis_client is None:
        import redis

        from core.config import settings

        try:
            _redis_client = redis.from_url(
                settings.REDIS_URL, socket_connect_timeout=2, decode_responses=True
            )
            _redis_client.ping()
        except Exception:
            logger.warning("Redis unavailable for rate limiting, falling back to in-memory")
            _redis_client = None
    return _redis_client


# In-memory fallback (single-process only, used when Redis is unavailable)
_rate_limit_store: dict[str, list[float]] = {}


def _check_rate_limit(ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    import time

    r = _get_redis()
    if r is not None:
        try:
            key = f"price_check_rl:{ip}"
            current = r.incr(key)
            if current == 1:
                r.expire(key, RATE_LIMIT_WINDOW)
            return current <= RATE_LIMIT_MAX
        except Exception:
            logger.warning("Redis rate limit check failed, falling back to in-memory")

    # Fallback: in-memory (per-process, best-effort)
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    if ip not in _rate_limit_store:
        _rate_limit_store[ip] = []

    _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if t > window_start]

    if len(_rate_limit_store[ip]) >= RATE_LIMIT_MAX:
        return False

    _rate_limit_store[ip].append(now)
    return True


# ── Lead storage ──────────────────────────────────────────────────────


async def _store_lead(
    email: str,
    store_url: str,
    store_name: str = "",
    category: str | None = None,
    ip_hash: str | None = None,
) -> None:
    """
    Store the Price Check lead in the audit_requests table.
    Best-effort — failures are logged but don't break the scan.
    """
    try:
        async for db in get_session():
            await db.execute(
                text(
                    """
                    INSERT INTO audit_requests
                        (email, store_url, store_name, category, ip_hash, created_at)
                    VALUES
                        (:email, :store_url, :store_name, :category, :ip_hash, :now)
                    """
                ),
                {
                    "email": email,
                    "store_url": store_url,
                    "store_name": store_name,
                    "category": category,
                    "ip_hash": ip_hash,
                    "now": datetime.now(UTC),
                },
            )
            await db.commit()
            logger.info("Stored price check lead: %s / %s", email, store_url)
    except Exception as e:
        logger.warning("Failed to store lead: %s", e)


async def _update_lead_report(
    email: str,
    store_url: str,
    report: dict,
) -> None:
    """
    Update the audit_requests row with the completed report data.
    Best-effort — failures are logged but don't break anything.
    """
    try:
        async for db in get_session():
            await db.execute(
                text(
                    """
                    UPDATE audit_requests
                    SET
                        store_name               = :store_name,
                        products_scanned         = :products_scanned,
                        competitors_found        = :competitors_found,
                        estimated_monthly_impact = :monthly_impact,
                        estimated_annual_impact  = :annual_impact,
                        confidence               = :confidence,
                        report_data              = :report_data
                    WHERE email = :email
                      AND store_url = :store_url
                      AND report_data IS NULL
                    """
                ),
                {
                    "store_name": report.get("store_name", ""),
                    "products_scanned": report.get("products_scanned"),
                    "competitors_found": report.get("competitors_found"),
                    "monthly_impact": report.get("estimated_monthly_impact"),
                    "annual_impact": report.get("estimated_annual_impact"),
                    "confidence": report.get("confidence"),
                    "report_data": json.dumps(report),
                    "email": email,
                    "store_url": store_url,
                },
            )
            await db.commit()
            logger.info("Updated report data for: %s / %s", email, store_url)
    except Exception as e:
        logger.warning("Failed to update lead report: %s", e)


# ── SSE streaming endpoint ────────────────────────────────────────────


@router.get("/price-check/stream")
async def price_check_stream(
    request: Request,
    store_url: str = Query(..., description="Shopify or WooCommerce store URL"),
    email: str = Query(..., description="Lead capture email"),
    category: str | None = Query(None, description="Optional product category"),
):
    """
    Stream a Price Check scan via Server-Sent Events.
    The frontend connects with EventSource and receives JSON events
    as each agent completes its work.
    """
    allowed_origin = _cors_origin(request)

    sse_headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Access-Control-Allow-Origin": allowed_origin,
        "Vary": "Origin",
    }

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not _check_rate_limit(client_ip):

        async def rate_limited():
            event = {
                "agent": "error",
                "status": "error",
                "message": "Rate limit exceeded. Please try again in an hour.",
                "data": None,
            }
            yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            rate_limited(),
            media_type="text/event-stream",
            headers=sse_headers,
        )

    # Input validation
    if not store_url or not store_url.strip():

        async def missing_url():
            event = {
                "agent": "error",
                "status": "error",
                "message": "Store URL is required.",
                "data": None,
            }
            yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            missing_url(),
            media_type="text/event-stream",
            headers=sse_headers,
        )

    if not email or not email.strip():

        async def missing_email():
            event = {
                "agent": "error",
                "status": "error",
                "message": "Email is required.",
                "data": None,
            }
            yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            missing_email(),
            media_type="text/event-stream",
            headers=sse_headers,
        )

    # Store lead on scan start (best-effort)
    with contextlib.suppress(Exception):
        await _store_lead(
            email=email.strip(),
            store_url=store_url.strip(),
            category=category.strip() if category else None,
            ip_hash=client_ip,
        )

    # Stream the pipeline
    async def event_stream():
        try:
            async for event in run_price_check(
                store_url=store_url.strip(),
                email=email.strip(),
                category=category.strip() if category else None,
            ):
                if await request.is_disconnected():
                    logger.info("Client disconnected during price check")
                    return

                # On completion, backfill full report data
                if event.get("agent") == "complete" and event.get("status") == "done" and event.get("data"):
                    with contextlib.suppress(Exception):
                        await _update_lead_report(
                            email=email.strip(),
                            store_url=store_url.strip(),
                            report=event["data"],
                        )

                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.exception("Price check stream error")
            error_event = {
                "agent": "error",
                "status": "error",
                "message": f"An unexpected error occurred: {e!s}",
                "data": None,
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=sse_headers,
    )
