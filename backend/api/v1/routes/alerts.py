# backend/api/v1/routes/alerts.py
"""Alert management API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from db.session import get_session
from core.security import get_current_user
from models.user import User
from models.alert import (
    Alert,
    AlertConfiguration,
    AlertType,
    AlertSeverity,
    AlertStatus,
)
from schemas.alert import (
    AlertConfigurationCreate,
    AlertConfigurationUpdate,
    AlertConfigurationRead,
    AlertRead,
    AlertStats,
)
from schemas.common import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ============== Alert Configuration Endpoints ==============

@router.post("/configurations", response_model=AlertConfigurationRead)
async def create_alert_configuration(
    config: AlertConfigurationCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new alert configuration."""
    db_config = AlertConfiguration(
        user_id=current_user.id,
        name=config.name,
        description=config.description,
        alert_type=config.alert_type,
        is_active=config.is_active,
        product_ids=config.product_ids,
        conditions=config.conditions,
        channels=[c.value for c in config.channels],
        channel_settings=config.channel_settings,
        cooldown_minutes=config.cooldown_minutes,
        max_per_day=config.max_per_day,
    )
    session.add(db_config)
    await session.commit()
    await session.refresh(db_config)
    return db_config


@router.get("/configurations", response_model=List[AlertConfigurationRead])
async def list_alert_configurations(
    alert_type: Optional[AlertType] = None,
    is_active: Optional[bool] = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all alert configurations for the current user."""
    query = select(AlertConfiguration).where(
        AlertConfiguration.user_id == current_user.id
    )
    
    if alert_type:
        query = query.where(AlertConfiguration.alert_type == alert_type)
    if is_active is not None:
        query = query.where(AlertConfiguration.is_active == is_active)
    
    query = query.order_by(AlertConfiguration.created_at.desc())
    result = await session.execute(query)
    configs = list(result.scalars().all())
    return configs


@router.get("/configurations/{config_id}", response_model=AlertConfigurationRead)
async def get_alert_configuration(
    config_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific alert configuration."""
    result = await session.execute(
        select(AlertConfiguration).where(
            AlertConfiguration.id == config_id,
            AlertConfiguration.user_id == current_user.id,
        )
    )
    config = result.scalars().first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Alert configuration not found")
    return config


@router.patch("/configurations/{config_id}", response_model=AlertConfigurationRead)
async def update_alert_configuration(
    config_id: UUID,
    updates: AlertConfigurationUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update an alert configuration."""
    result = await session.execute(
        select(AlertConfiguration).where(
            AlertConfiguration.id == config_id,
            AlertConfiguration.user_id == current_user.id,
        )
    )
    config = result.scalars().first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Alert configuration not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    
    # Convert channel enums to strings if present
    if "channels" in update_data and update_data["channels"]:
        update_data["channels"] = [c.value for c in update_data["channels"]]
    
    for field, value in update_data.items():
        setattr(config, field, value)
    
    config.updated_at = datetime.utcnow()
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/configurations/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_configuration(
    config_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete an alert configuration."""
    result = await session.execute(
        select(AlertConfiguration).where(
            AlertConfiguration.id == config_id,
            AlertConfiguration.user_id == current_user.id,
        )
    )
    config = result.scalars().first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Alert configuration not found")
    
    await session.delete(config)
    await session.commit()


# ============== Alert Endpoints ==============

@router.get("", response_model=PaginatedResponse[AlertRead])
async def list_alerts(
    status_filter: Optional[AlertStatus] = Query(None, alias="status"),
    severity: Optional[AlertSeverity] = None,
    alert_type: Optional[AlertType] = None,
    product_id: Optional[UUID] = None,
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
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0
    
    # Apply pagination and ordering
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
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get alert statistics for the dashboard."""
    # Unread count (PENDING status)
    unread_result = await session.execute(
        select(func.count(Alert.id)).where(
            Alert.user_id == current_user.id,
            Alert.status == AlertStatus.PENDING,
        )
    )
    unread_count = unread_result.scalar() or 0
    
    # Count by severity (unread only) - defensive iteration
    severity_counts: dict[str, int] = {}
    for sev in AlertSeverity:
        try:
            sev_value = sev.value if hasattr(sev, 'value') else str(sev)
            sev_result = await session.execute(
                select(func.count(Alert.id)).where(
                    Alert.user_id == current_user.id,
                    Alert.status == AlertStatus.PENDING,
                    Alert.severity == sev,
                )
            )
            count = sev_result.scalar() or 0
            severity_counts[sev_value] = count
        except Exception:
            # Skip problematic severity values
            continue
    
    # Count by type (unread only) - defensive iteration
    type_counts: dict[str, int] = {}
    for at in AlertType:
        try:
            at_value = at.value if hasattr(at, 'value') else str(at)
            type_result = await session.execute(
                select(func.count(Alert.id)).where(
                    Alert.user_id == current_user.id,
                    Alert.status == AlertStatus.PENDING,
                    Alert.alert_type == at,
                )
            )
            count = type_result.scalar() or 0
            if count > 0:  # Only include types with alerts
                type_counts[at_value] = count
        except Exception:
            # Skip problematic type values
            continue
    
    # Recent 24h count
    cutoff = datetime.utcnow() - timedelta(hours=24)
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


@router.get("/{alert_id}", response_model=AlertRead)
async def get_alert(
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
async def acknowledge_alert(
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
        raise HTTPException(
            status_code=400,
            detail=f"Cannot acknowledge alert with status: {alert.status.value}"
        )
    
    alert.status = AlertStatus.ACKNOWLEDGED
    alert.acknowledged_at = datetime.utcnow()
    alert.acknowledged_by = current_user.id
    
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertRead)
async def resolve_alert(
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
    alert.resolved_at = datetime.utcnow()
    
    # If not already acknowledged, mark as acknowledged too
    if not alert.acknowledged_at:
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = current_user.id
    
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


@router.post("/acknowledge-all", status_code=status.HTTP_200_OK)
async def acknowledge_all_alerts(
    severity: Optional[AlertSeverity] = None,
    alert_type: Optional[AlertType] = None,
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
    now = datetime.utcnow()
    
    for alert in alerts:
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = now
        alert.acknowledged_by = current_user.id
        session.add(alert)
    
    await session.commit()
    
    return {"acknowledged_count": len(alerts)}
