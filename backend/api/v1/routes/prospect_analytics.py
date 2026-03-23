"""
Prospect Audit Analytics

Lightweight event tracking for the public audit funnel.
Tracks: page_view → audit_started → audit_completed → email_submitted → pdf_downloaded

Events are stored in a simple DB table. No third-party dependencies.
The admin metrics endpoint gives you conversion rates at a glance.

Endpoints:
  POST /api/v1/prospect/analytics/event    — Track an event (public, no auth)
  GET  /api/v1/prospect/analytics/metrics   — Get funnel metrics (auth required)
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from core.logging import get_logger
from core.rate_limit import limiter
from db.session import get_session
from models.prospect_audit_event import ProspectAuditEvent
from models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/prospect/analytics", tags=["Prospect Analytics"])


# ── Schemas ───────────────────────────────────────────────────

VALID_EVENTS = {
    "page_view",
    "audit_started",
    "audit_completed",
    "email_submitted",
    "pdf_downloaded",
    "demo_clicked",
}


class TrackEventRequest(BaseModel):
    event_type: str = Field(
        description="One of: page_view, audit_started, audit_completed, email_submitted, pdf_downloaded, demo_clicked"
    )
    store_url: str | None = None
    email: str | None = None
    input_mode: str | None = Field(default=None, description="'url' or 'csv'")
    products_found: int | None = None
    estimated_impact: str | None = None


class TrackEventResponse(BaseModel):
    ok: bool


class FunnelMetrics(BaseModel):
    period_days: int
    page_views: int
    audits_started: int
    audits_completed: int
    emails_submitted: int
    pdfs_downloaded: int
    demos_clicked: int
    start_rate: str = Field(description="audits_started / page_views")
    completion_rate: str = Field(description="audits_completed / audits_started")
    email_conversion: str = Field(description="emails_submitted / audits_completed")
    pdf_conversion: str = Field(description="pdfs_downloaded / emails_submitted")
    unique_stores: int
    unique_emails: int


# ── Endpoints ─────────────────────────────────────────────────


@router.post("/event", response_model=TrackEventResponse)
@limiter.limit("30/minute")
async def track_event(
    request: TrackEventRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    Track a prospect audit funnel event. Public, no auth required.
    Rate limited to 30/minute per IP.
    """
    if request.event_type not in VALID_EVENTS:
        return TrackEventResponse(ok=False)

    # Hash IP and email for privacy (don't store raw PII)
    import hashlib

    client_ip = req.client.host if req.client else "unknown"
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]

    # Hash email the same way as IP — never store raw email PII
    email_hash = None
    if request.email:
        email_hash = hashlib.sha256(request.email.lower().strip().encode()).hexdigest()[:16]

    user_agent = req.headers.get("user-agent", "")[:500]

    event = ProspectAuditEvent(
        event_type=request.event_type,
        store_url=request.store_url,
        email=email_hash,
        input_mode=request.input_mode,
        products_found=request.products_found,
        estimated_impact=request.estimated_impact,
        ip_hash=ip_hash,
        user_agent=user_agent,
    )

    session.add(event)
    await session.commit()

    logger.info(
        f"Prospect event tracked: {request.event_type}",
        store_url=request.store_url,
        input_mode=request.input_mode,
    )

    return TrackEventResponse(ok=True)


@router.get("/metrics", response_model=FunnelMetrics)
async def get_funnel_metrics(
    days: int = Query(default=30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get prospect audit funnel metrics for the last N days.
    Auth required — this is for your admin dashboard.
    """
    since = datetime.now(UTC) - timedelta(days=days)

    # Single aggregation query instead of 8 sequential round-trips
    result = await session.execute(
        select(
            ProspectAuditEvent.event_type,
            func.count(ProspectAuditEvent.id),
            func.count(func.distinct(ProspectAuditEvent.store_url)),
            func.count(func.distinct(ProspectAuditEvent.email)),
        )
        .where(ProspectAuditEvent.created_at >= since)
        .group_by(ProspectAuditEvent.event_type)
    )
    rows = {row[0]: row for row in result.all()}

    def get_count(event_type: str) -> int:
        return rows[event_type][1] if event_type in rows else 0

    page_views = get_count("page_view")
    started = get_count("audit_started")
    completed = get_count("audit_completed")
    emails = get_count("email_submitted")
    pdfs = get_count("pdf_downloaded")
    demos = get_count("demo_clicked")

    unique_stores = rows["audit_started"][2] if "audit_started" in rows else 0
    unique_emails = rows["email_submitted"][3] if "email_submitted" in rows else 0

    def rate(num: int, denom: int) -> str:
        if denom == 0:
            return "0%"
        return f"{(num / denom * 100):.1f}%"

    return FunnelMetrics(
        period_days=days,
        page_views=page_views,
        audits_started=started,
        audits_completed=completed,
        emails_submitted=emails,
        pdfs_downloaded=pdfs,
        demos_clicked=demos,
        start_rate=rate(started, page_views),
        completion_rate=rate(completed, started),
        email_conversion=rate(emails, completed),
        pdf_conversion=rate(pdfs, emails),
        unique_stores=unique_stores,
        unique_emails=unique_emails,
    )
