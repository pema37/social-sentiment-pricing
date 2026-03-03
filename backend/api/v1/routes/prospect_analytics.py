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

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, DateTime, String, Text, func, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from sqlmodel import SQLModel, Field as SQLField

from db.session import get_session
from core.deps import get_current_user
from core.rate_limit import limiter
from core.logging import get_logger
from models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/prospect/analytics", tags=["Prospect Analytics"])


# ── Model ─────────────────────────────────────────────────────

class ProspectAuditEvent(SQLModel, table=True):
    """Tracks prospect audit funnel events."""
    __tablename__ = "prospect_audit_events"

    id: uuid.UUID = SQLField(
        default_factory=uuid.uuid4,
        sa_column=Column(PG_UUID(as_uuid=True), primary_key=True),
    )
    event_type: str = SQLField(
        sa_column=Column(String(50), nullable=False, index=True),
    )
    store_url: Optional[str] = SQLField(
        default=None,
        sa_column=Column(String(500), nullable=True),
    )
    email: Optional[str] = SQLField(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    input_mode: Optional[str] = SQLField(
        default=None,
        sa_column=Column(String(10), nullable=True),
    )
    products_found: Optional[int] = SQLField(default=None)
    estimated_impact: Optional[str] = SQLField(
        default=None,
        sa_column=Column(String(50), nullable=True),
    )
    ip_hash: Optional[str] = SQLField(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    user_agent: Optional[str] = SQLField(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    created_at: datetime = SQLField(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )


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
    event_type: str = Field(description="One of: page_view, audit_started, audit_completed, email_submitted, pdf_downloaded, demo_clicked")
    store_url: Optional[str] = None
    email: Optional[str] = None
    input_mode: Optional[str] = Field(default=None, description="'url' or 'csv'")
    products_found: Optional[int] = None
    estimated_impact: Optional[str] = None


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

    # Hash IP for privacy (don't store raw IPs)
    import hashlib
    client_ip = req.client.host if req.client else "unknown"
    ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:16]

    user_agent = req.headers.get("user-agent", "")[:500]

    event = ProspectAuditEvent(
        event_type=request.event_type,
        store_url=request.store_url,
        email=request.email,
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
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async def count_events(event_type: str) -> int:
        result = await session.execute(
            select(func.count(ProspectAuditEvent.id))
            .where(ProspectAuditEvent.event_type == event_type)
            .where(ProspectAuditEvent.created_at >= since)
        )
        return result.scalar_one()

    async def count_unique(column, event_type: str) -> int:
        result = await session.execute(
            select(func.count(func.distinct(column)))
            .where(ProspectAuditEvent.event_type == event_type)
            .where(ProspectAuditEvent.created_at >= since)
            .where(column.isnot(None))
        )
        return result.scalar_one()

    page_views = await count_events("page_view")
    started = await count_events("audit_started")
    completed = await count_events("audit_completed")
    emails = await count_events("email_submitted")
    pdfs = await count_events("pdf_downloaded")
    demos = await count_events("demo_clicked")

    unique_stores = await count_unique(ProspectAuditEvent.store_url, "audit_started")
    unique_emails = await count_unique(ProspectAuditEvent.email, "email_submitted")

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



