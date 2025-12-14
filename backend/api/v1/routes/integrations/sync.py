# backend/api/v1/routes/integrations/sync.py
"""Sync operation endpoints."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import limiter, BULK_RATE_LIMIT
from db.session import get_session, async_session
from models.user import User
from models.integration import Integration, IntegrationSyncLog, IntegrationStatus
from schemas.integration import (
    SyncTriggerRequest,
    SyncStatusResponse,
    SyncLogResponse,
)
from schemas.common import PaginatedResponse, PaginationParams
from services.integration import SyncService

logger = logging.getLogger(__name__)

router = APIRouter()


async def run_sync_background(
    integration_id: UUID,
    sync_type: str,
    user_id: UUID,
):
    """Background task wrapper for running product sync."""
    async with async_session() as db:
        try:
            sync_service = SyncService(db)
            sync_log = await sync_service.run_sync(
                integration_id=integration_id,
                sync_type=sync_type,
                user_id=user_id,
            )
            logger.info(
                f"Sync completed for integration {integration_id}: "
                f"created={sync_log.products_created}, "
                f"updated={sync_log.products_updated}, "
                f"deleted={sync_log.products_deleted}"
            )
        except Exception as e:
            logger.exception(f"Background sync failed for integration {integration_id}: {e}")


@router.post("/{integration_id}/sync", response_model=SyncStatusResponse)
@limiter.limit(BULK_RATE_LIMIT)
async def trigger_sync(
    request: Request,
    integration_id: UUID,
    sync_request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Trigger a product sync from the e-commerce platform."""
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
    
    if integration.status != IntegrationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration is not active"
        )
    
    if integration.sync_status == "syncing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sync already in progress"
        )
    
    integration.sync_status = "syncing"
    db.add(integration)
    await db.commit()
    
    background_tasks.add_task(
        run_sync_background,
        integration_id=integration_id,
        sync_type=sync_request.sync_type,
        user_id=current_user.id,
    )
    
    logger.info(f"Sync triggered for integration {integration_id} by user {current_user.id}")
    
    return SyncStatusResponse(
        integration_id=integration.id,
        sync_status=integration.sync_status,
        last_sync_at=integration.last_sync_at,
        products_synced=integration.products_synced,
    )


@router.get("/{integration_id}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get current sync status."""
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
    
    return SyncStatusResponse(
        integration_id=integration.id,
        sync_status=integration.sync_status,
        last_sync_at=integration.last_sync_at,
        products_synced=integration.products_synced,
    )


@router.get("/{integration_id}/sync/logs", response_model=PaginatedResponse[SyncLogResponse])
async def get_sync_logs(
    request: Request,
    integration_id: UUID,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get sync history for an integration."""
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
    
    query = select(IntegrationSyncLog).where(
        IntegrationSyncLog.integration_id == integration_id
    )
    
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    
    query = query.order_by(IntegrationSyncLog.started_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    logs = list(result.scalars().all())
    
    items = [SyncLogResponse.model_validate(log) for log in logs]
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )
