"""
Retrospective Loss Audit API Routes (Authenticated)

Endpoints:
  POST /api/v1/audit/retrospective            — Generate + persist a new audit
  GET  /api/v1/audit/retrospective/latest      — Get cached or generate fresh
  GET  /api/v1/audit/retrospective/{audit_id}  — Retrieve a specific past audit
  GET  /api/v1/audit/retrospective/history      — List past audits
  POST /api/v1/audit/retrospective/pdf         — Generate & download as PDF
"""

import uuid

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from core.deps import get_current_user
from models.user import User
from services.retrospective_audit_service import RetrospectiveAuditService
from services.audit_persistence_service import AuditPersistenceService
from services.audit_pdf_generator import generate_audit_pdf
from schemas.retrospective_audit import (
    AuditRequest,
    RetrospectiveAuditResponse,
    AuditListItem,
    AuditListResponse,
)

router = APIRouter(prefix="/audit", tags=["Retrospective Audit"])


@router.post("/retrospective", response_model=RetrospectiveAuditResponse)
async def generate_retrospective_audit(
    request: AuditRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a new retrospective loss audit and persist it.
    """
    service = RetrospectiveAuditService(session, str(current_user.id))
    audit = await service.generate_audit(request)

    # Persist for future retrieval
    if audit.summary.total_products_analyzed > 0:
        persistence = AuditPersistenceService(session, str(current_user.id))
        await persistence.save_audit(audit)
        await session.commit()

    return audit


@router.get("/retrospective/latest", response_model=RetrospectiveAuditResponse)
async def get_latest_audit(
    lookback_days: int = Query(default=90, ge=7, le=365),
    force_refresh: bool = Query(default=False, description="Skip cache and regenerate"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get the latest audit for this user.

    Returns cached version if available (< 24h old).
    Pass force_refresh=true to regenerate.
    """
    persistence = AuditPersistenceService(session, str(current_user.id))

    # Try cached version first (unless force refresh)
    if not force_refresh:
        cached = await persistence.get_latest(lookback_days=lookback_days)
        if cached:
            from datetime import datetime, timezone, timedelta
            age = datetime.now(timezone.utc) - cached.created_at
            if age < timedelta(hours=24):
                return cached

    # Generate fresh
    request = AuditRequest(lookback_days=lookback_days)
    service = RetrospectiveAuditService(session, str(current_user.id))
    audit = await service.generate_audit(request)

    # Persist
    if audit.summary.total_products_analyzed > 0:
        await persistence.save_audit(audit)
        await session.commit()

    return audit


@router.get("/retrospective/history", response_model=AuditListResponse)
async def list_past_audits(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List past audits for this user."""
    persistence = AuditPersistenceService(session, str(current_user.id))
    items, total = await persistence.list_audits(limit=limit, offset=offset)
    return AuditListResponse(items=items, total=total)


@router.get("/retrospective/{audit_id}", response_model=RetrospectiveAuditResponse)
async def get_audit_by_id(
    audit_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a specific past audit by ID."""
    persistence = AuditPersistenceService(session, str(current_user.id))
    audit = await persistence.get_by_id(audit_id)

    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    return audit


@router.post("/retrospective/pdf")
async def generate_retrospective_pdf(
    request: AuditRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Generate a retrospective loss audit and return it as a downloadable PDF.
    """
    service = RetrospectiveAuditService(session, str(current_user.id))
    audit = await service.generate_audit(request)

    pdf_bytes = generate_audit_pdf(audit)

    filename = f"pricing-audit-{audit.summary.lookback_days}d-{audit.created_at.strftime('%Y%m%d')}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )



