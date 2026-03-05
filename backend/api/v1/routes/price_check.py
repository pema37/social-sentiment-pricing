"""
Price Check SSE endpoint — public, unauthenticated, rate-limited.

GET /api/v1/audit/price-check/stream?store_url=...&email=...&category=...

Streams Server-Sent Events as the Scout → Analyst → Strategist pipeline
runs. Each event is a JSON object with {agent, status, message, data}.

The final event has agent="complete" and data=full PriceCheckReport.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from db.session import get_session
from services.audit.audit_orchestrator import run_price_check

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["price-check"])

# ── Simple in-memory rate limiter ─────────────────────────────────────
# For production, replace with Redis-backed rate limiting from core/rate_limit.py

_rate_limit_store: dict[str, list[float]] = {}
RATE_LIMIT_MAX = 10  # max requests
RATE_LIMIT_WINDOW = 3600  # per hour (seconds)


def _check_rate_limit(ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    import time

    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    if ip not in _rate_limit_store:
        _rate_limit_store[ip] = []

    # Prune old entries
    _rate_limit_store[ip] = [t for t in _rate_limit_store[ip] if t > window_start]

    if len(_rate_limit_store[ip]) >= RATE_LIMIT_MAX:
        return False

    _rate_limit_store[ip].append(now)
    return True


# ── Lead storage ──────────────────────────────────────────────────────

async def _store_lead(email: str, store_url: str, store_name: str = "") -> None:
    """
    Store the Price Check lead in the prospect_audit_events table.

    Best-effort — failures are logged but don't break the scan.
    """
    try:
        async for db in get_session():
            await db.execute(
                text(
                    """
                    INSERT INTO prospect_audit_events
                        (email, store_url, store_name, event_type, created_at)
                    VALUES
                        (:email, :store_url, :store_name, 'price_check_started', :now)
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "email": email,
                    "store_url": store_url,
                    "store_name": store_name,
                    "now": datetime.now(timezone.utc),
                },
            )
            await db.commit()
            logger.info("Stored price check lead: %s / %s", email, store_url)
    except Exception as e:
        logger.warning("Failed to store lead: %s", e)


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
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
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
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
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
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # Store lead (best-effort, don't block the scan)
    try:
        await _store_lead(email.strip(), store_url.strip())
    except Exception:
        pass

    # Stream the pipeline
    async def event_stream():
        try:
            async for event in run_price_check(
                store_url=store_url.strip(),
                email=email.strip(),
                category=category.strip() if category else None,
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info("Client disconnected during price check")
                    return

                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            logger.exception("Price check stream error")
            error_event = {
                "agent": "error",
                "status": "error",
                "message": f"An unexpected error occurred: {str(e)}",
                "data": None,
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )




