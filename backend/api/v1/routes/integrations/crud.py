# backend/api/v1/routes/integrations/crud.py
"""Integration CRUD endpoints."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT
from db.session import get_session
from models.user import User
from models.integration import Integration, IntegrationStatus
from schemas.integration import (
    IntegrationUpdate,
    IntegrationResponse,
    IntegrationListResponse,
)
from services.integration import WebhookRegistrationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=IntegrationListResponse)
async def list_integrations(
    request: Request,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all integrations for current user."""
    stmt = select(Integration).where(
        Integration.user_id == current_user.id
    ).order_by(Integration.created_at.desc())
    
    result = await db.execute(stmt)
    integrations = list(result.scalars().all())
    
    return IntegrationListResponse(
        integrations=[IntegrationResponse.model_validate(i) for i in integrations],
        total=len(integrations),
    )


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific integration."""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    return IntegrationResponse.model_validate(integration)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def update_integration(
    request: Request,
    integration_id: UUID,
    data: IntegrationUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update integration settings."""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    if data.store_name is not None:
        integration.store_name = data.store_name
    if data.status is not None:
        integration.status = data.status
    if data.settings is not None:
        integration.settings = data.settings
    
    integration.updated_at = datetime.utcnow()
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    
    return IntegrationResponse.model_validate(integration)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_RATE_LIMIT)
async def disconnect_integration(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Disconnect an integration (soft delete with webhook cleanup)."""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    if integration.status == IntegrationStatus.ACTIVE:
        try:
            webhook_service = WebhookRegistrationService(db)
            await webhook_service.unregister_webhooks(integration.id)
            logger.info(f"Webhooks unregistered for integration {integration_id}")
        except Exception as e:
            logger.warning(f"Failed to unregister webhooks: {e}")
    
    integration.status = IntegrationStatus.DISCONNECTED
    integration.updated_at = datetime.utcnow()
    db.add(integration)
    await db.commit()
    
    logger.info(f"Integration {integration_id} disconnected by user {current_user.id}")
