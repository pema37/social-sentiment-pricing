# backend/api/v1/routes/alerts/management.py
"""Alert management endpoints (list, acknowledge, resolve)."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import WRITE_RATE_LIMIT, limiter
from db.session import get_session
from models.alert import Alert, AlertSeverity, AlertStatus, AlertType
from models.user import User
from schemas.alert import AlertRead, AlertStats
from schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# STATIC ROUTES
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/", response_model=PaginatedResponse[AlertRead])
async def list_alerts(
    request: Request,
    status_filter: AlertStatus | None = Query(None, alias="status"),
    severity: AlertSeverity | None = None,
    alert_type: AlertType | None = None,
    product_id: UUID | None = None,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List alerts for the current user with filtering and pagination."""
    query = select(Alert).where(Alert.user_id == current_user.id)

    if status_filter:
        query = query.where(Alert.status == status_filter)
    if severity:
        query = query.where(Alert.severity == severity)
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)
    if product_id:
        query = query.where(Alert.product_id == product_id)

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    query = query.order_by(Alert.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)

    result = await session.execute(query)
    alerts = list(result.scalars().all())

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=alerts,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/stats", response_model=AlertStats)
async def get_alert_stats(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get alert statistics for the dashboard."""
    unread_result = await session.execute(
        select(func.count(Alert.id)).where(
            Alert.user_id == current_user.id,
            Alert.status == AlertStatus.PENDING,
        )
    )
    unread_count = unread_result.scalar() or 0

    severity_counts: dict[str, int] = {}
    sev_result = await session.execute(
        select(Alert.severity, func.count(Alert.id))
        .where(
            Alert.user_id == current_user.id,
            Alert.status == AlertStatus.PENDING,
        )
        .group_by(Alert.severity)
    )
    for sev, count in sev_result.all():
        sev_value = sev.value if hasattr(sev, "value") else str(sev)
        severity_counts[sev_value] = count

    type_counts: dict[str, int] = {}
    type_result = await session.execute(
        select(Alert.alert_type, func.count(Alert.id))
        .where(
            Alert.user_id == current_user.id,
            Alert.status == AlertStatus.PENDING,
        )
        .group_by(Alert.alert_type)
    )
    for at, count in type_result.all():
        at_value = at.value if hasattr(at, "value") else str(at)
        if count > 0:
            type_counts[at_value] = count

    cutoff = datetime.now(UTC) - timedelta(hours=24)
    recent_result = await session.execute(
        select(func.count(Alert.id)).where(
            Alert.user_id == current_user.id,
            Alert.created_at >= cutoff,
        )
    )
    recent_count = recent_result.scalar() or 0

    return AlertStats(
        total_unread=unread_count,
        by_severity=severity_counts,
        by_type=type_counts,
        recent_24h=recent_count,
    )


@router.get("/unread/count")
async def get_unread_count(
    request: Request,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get just the unread alert count (lightweight endpoint for polling)."""
    result = await session.execute(
        select(func.count(Alert.id)).where(
            Alert.user_id == current_user.id,
            Alert.status == AlertStatus.PENDING,
        )
    )
    count = result.scalar() or 0
    return {"unread_count": count}


@router.post("/acknowledge-all", status_code=status.HTTP_200_OK)
@limiter.limit(WRITE_RATE_LIMIT)
async def acknowledge_all_alerts(
    request: Request,
    severity: AlertSeverity | None = None,
    alert_type: AlertType | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge all pending alerts (optionally filtered)."""
    query = select(Alert).where(
        Alert.user_id == current_user.id,
        Alert.status == AlertStatus.PENDING,
    )

    if severity:
        query = query.where(Alert.severity == severity)
    if alert_type:
        query = query.where(Alert.alert_type == alert_type)

    result = await session.execute(query)
    alerts = list(result.scalars().all())
    now = datetime.now(UTC)

    for alert in alerts:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = now
        alert.acknowledged_by = current_user.id
        session.add(alert)

    await session.commit()

    return {"acknowledged_count": len(alerts)}


# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC ROUTES (must come after all static routes)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{alert_id}", response_model=AlertRead)
async def get_alert(
    request: Request,
    alert_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific alert."""
    result = await session.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    alert = result.scalars().first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertRead)
@limiter.limit(WRITE_RATE_LIMIT)
async def acknowledge_alert(
    request: Request,
    alert_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge an alert."""
    result = await session.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    alert = result.scalars().first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status != AlertStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Cannot acknowledge alert with status: {alert.status.value}")

    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.now(UTC)
    alert.acknowledged_by = current_user.id

    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertRead)
@limiter.limit(WRITE_RATE_LIMIT)
async def resolve_alert(
    request: Request,
    alert_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Resolve an alert."""
    result = await session.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    alert = result.scalars().first()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status == AlertStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="Alert is already resolved")

    alert.status = AlertStatus.RESOLVED
    alert.resolved_at = datetime.now(UTC)

    if not alert.acknowledged_at:
        alert.acknowledged_at = datetime.now(UTC)
        alert.acknowledged_by = current_user.id

    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert
