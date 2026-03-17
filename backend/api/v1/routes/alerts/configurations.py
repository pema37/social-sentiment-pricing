# backend/api/v1/routes/alerts/configurations.py
"""Alert configuration CRUD endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import WRITE_RATE_LIMIT, limiter
from db.session import get_session
from models.alert import AlertConfiguration, AlertType
from models.user import User
from schemas.alert import (
    AlertConfigurationCreate,
    AlertConfigurationRead,
    AlertConfigurationUpdate,
)

router = APIRouter()


@router.post("/configurations", response_model=AlertConfigurationRead)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_alert_configuration(
    request: Request,
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


@router.get("/configurations", response_model=list[AlertConfigurationRead])
async def list_alert_configurations(
    request: Request,
    alert_type: AlertType | None = None,
    is_active: bool | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all alert configurations for the current user."""
    query = select(AlertConfiguration).where(AlertConfiguration.user_id == current_user.id)

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
    request: Request,
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
@limiter.limit(WRITE_RATE_LIMIT)
async def update_alert_configuration(
    request: Request,
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

    if update_data.get("channels"):
        update_data["channels"] = [c.value for c in update_data["channels"]]

    for field, value in update_data.items():
        setattr(config, field, value)

    config.updated_at = datetime.now(UTC)
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


@router.delete("/configurations/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_alert_configuration(
    request: Request,
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
