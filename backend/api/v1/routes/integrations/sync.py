# backend/api/v1/routes/integrations/sync.py
"""
Sync operation endpoints - WITH PROGRESS TRACKING.

Updated to include:
- GET /{integration_id}/sync/progress - Detailed progress with user-friendly messaging
- GET /sync/status/all - Status across all user's integrations

FIX (2026-03-29): trigger_sync now dispatches to Celery sync_integration_products
task via the sync queue instead of FastAPI BackgroundTasks. This ensures the sync
runs in a Celery worker with proper error handling, retries, and status reset.

FIX (2026-03-29): AP-005 BUG 303.01 — trigger_sync now creates an IntegrationSyncLog
before dispatching to Celery. Without a log record, recover_stuck_syncs falls to a
fragile else branch that silently skips integrations that have previously synced
successfully. The Celery task closes the log via _close_open_sync_log() in all
terminal paths (success, failure, chord error, orchestrator safety net).
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import BULK_RATE_LIMIT, WRITE_RATE_LIMIT, limiter
from db.session import async_session, get_session
from models.integration import Integration, IntegrationStatus, IntegrationSyncLog
from models.user import User
from schemas.common import PaginatedResponse, PaginationParams
from schemas.integration import (
    SyncLogResponse,
    SyncStatusResponse,
    SyncTriggerRequest,
)
from services.integration import PricePushService, SyncService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{integration_id}/sync", response_model=SyncStatusResponse)
@limiter.limit(BULK_RATE_LIMIT)
async def trigger_sync(
    request: Request,
    integration_id: UUID,
    sync_request: SyncTriggerRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger a product sync from the e-commerce platform.

    The sync runs in a Celery worker via the sync queue.
    Poll GET /{integration_id}/sync/progress for real-time updates.
    """
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if integration.status not in (IntegrationStatus.ACTIVE, IntegrationStatus.ERROR):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integration is not active")

    if integration.sync_status == "syncing":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sync already in progress")

    now = datetime.now(UTC)

    # Mark syncing immediately so the UI starts polling
    integration.sync_status = "syncing"
    db.add(integration)

    # AP-005 BUG 303.01: Create IntegrationSyncLog here so recover_stuck_syncs
    # has a reliable anchor to detect and recover stuck syncs.
    # Without a log record, recover_stuck_syncs falls to a fragile else branch
    # that only recovers when there is no recent completed log — it silently
    # skips integrations that have successfully synced before.
    # The Celery task closes this log (success=True/False, completed_at) via
    # _close_open_sync_log() in _mark_sync_complete and _sync_single_pass.
    sync_log = IntegrationSyncLog(
        integration_id=integration.id,
        sync_type="full",
        started_at=now,
    )
    db.add(sync_log)
    await db.commit()

    # Dispatch to Celery sync queue — proper retries, error handling, status reset
    from workers.tasks.sync_tasks import sync_integration_products

    sync_integration_products.apply_async(
        args=[str(integration_id), str(current_user.id)],
        queue="sync",
    )

    logger.info(
        f"Sync dispatched to Celery for integration {integration_id} "
        f"by user {current_user.id}"
    )

    return SyncStatusResponse(
        integration_id=integration.id,
        sync_status=integration.sync_status,
        last_sync_at=integration.last_sync_at,
        products_synced=integration.products_synced,
    )


# ============================================
# PROGRESS TRACKING ENDPOINTS
# ============================================


@router.get("/{integration_id}/sync/progress")
async def get_sync_progress(
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed sync progress with user-friendly messaging.

    Frontend should poll this every 2-3 seconds while is_syncing == true.

    Key response fields:
    - is_syncing: Whether to show progress UI
    - progress_percent: For progress bar (null if unknown)
    - status_message: Human-readable status to display
    - can_refresh_safely: ALWAYS true - reassures users!
    """
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Get the latest sync log for progress details
    log_stmt = (
        select(IntegrationSyncLog)
        .where(IntegrationSyncLog.integration_id == integration_id)
        .order_by(IntegrationSyncLog.started_at.desc())
        .limit(1)
    )
    log_result = await db.execute(log_stmt)
    latest_log = log_result.scalars().first()

    is_syncing = integration.sync_status == "syncing"

    # Calculate progress
    products_processed = 0
    products_total = None
    progress_percent = None
    current_phase = "idle"
    elapsed_seconds = None
    started_at = None

    if is_syncing and latest_log:
        started_at = latest_log.started_at
        products_processed = (latest_log.products_created or 0) + (latest_log.products_updated or 0)

        if started_at:
            elapsed_seconds = (datetime.now(UTC) - started_at).total_seconds()

        if integration.products_synced and integration.products_synced > 0:
            products_total = integration.products_synced
            if products_total > 0:
                progress_percent = min(100, (products_processed / products_total) * 100)

        if products_processed == 0:
            current_phase = "fetching"
        elif progress_percent and progress_percent >= 95:
            current_phase = "finalizing"
        else:
            current_phase = "processing"

    status_message = _get_status_message(
        sync_status=integration.sync_status,
        products_processed=products_processed,
        products_total=products_total,
        current_phase=current_phase,
        error_message=integration.error_message,
    )

    products_created = 0
    products_updated = 0
    products_deleted = 0

    if latest_log and latest_log.success:
        products_created = latest_log.products_created or 0
        products_updated = latest_log.products_updated or 0
        products_deleted = latest_log.products_deleted or 0

    return {
        "integration_id": str(integration.id),
        "platform": integration.platform.value,
        "store_name": integration.store_name or integration.store_url,
        "sync_status": integration.sync_status,
        "is_syncing": is_syncing,
        "products_processed": products_processed,
        "products_total": products_total,
        "progress_percent": round(progress_percent, 1) if progress_percent else None,
        "current_phase": current_phase,
        "started_at": started_at.isoformat() if started_at else None,
        "elapsed_seconds": round(elapsed_seconds, 1) if elapsed_seconds else None,
        "last_sync_at": integration.last_sync_at.isoformat() if integration.last_sync_at else None,
        "products_synced": integration.products_synced,
        "products_created": products_created,
        "products_updated": products_updated,
        "products_deleted": products_deleted,
        "error_message": integration.error_message if integration.sync_status == "error" else None,
        "status_message": status_message,
        "can_refresh_safely": True,
    }


@router.get("/sync/status/all")
async def get_all_sync_status(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get sync status for ALL user's integrations.

    Frontend should poll this every 3 seconds if any_syncing is true.
    """
    stmt = select(Integration).where(Integration.user_id == current_user.id)
    result = await db.execute(stmt)
    integrations = list(result.scalars().all())

    statuses = []
    any_syncing = False

    for integration in integrations:
        is_syncing = integration.sync_status == "syncing"
        if is_syncing:
            any_syncing = True

        statuses.append(
            {
                "integration_id": str(integration.id),
                "platform": integration.platform.value,
                "store_name": integration.store_name or integration.store_url,
                "sync_status": integration.sync_status,
                "is_syncing": is_syncing,
                "products_synced": integration.products_synced,
                "last_sync_at": integration.last_sync_at.isoformat() if integration.last_sync_at else None,
                "status": integration.status.value,
            }
        )

    return {
        "integrations": statuses,
        "any_syncing": any_syncing,
        "total_integrations": len(integrations),
        "message": "Sync in progress..." if any_syncing else "All syncs complete",
    }


def _get_status_message(
    sync_status: str,
    products_processed: int,
    products_total: int | None,
    current_phase: str,
    error_message: str | None,
) -> str:
    """Generate user-friendly status message."""
    if sync_status == "error":
        return f"Sync failed: {error_message or 'Unknown error'}"

    if sync_status in ("idle", "completed"):
        return "Ready to sync"

    if sync_status == "syncing":
        if current_phase == "fetching":
            return "Connecting to store and fetching products..."
        elif current_phase == "finalizing":
            return "Almost done! Finalizing sync..."
        elif products_total:
            return f"Syncing products... {products_processed} of {products_total}"
        else:
            return f"Syncing products... {products_processed} processed"

    return "Unknown status"


# ============================================
# EXISTING ENDPOINTS
# ============================================


@router.post("/{integration_id}/push-prices")
@limiter.limit(WRITE_RATE_LIMIT)
async def push_prices_to_platform(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Push all pending price changes to the e-commerce platform."""
    price_push_service = PricePushService(db)

    try:
        result = await price_push_service.push_all_pending_prices(
            integration_id=integration_id,
            user_id=current_user.id,
        )

        logger.info(
            f"Price push for integration {integration_id}: "
            f"pushed={result['pushed']}, failed={result['failed']}, skipped={result['skipped']}"
        )

        return result

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{integration_id}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get current sync status (basic version - use /sync/progress for detailed)."""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    query = select(IntegrationSyncLog).where(IntegrationSyncLog.integration_id == integration_id)

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


@router.post("/{integration_id}/sync/recover")
@limiter.limit(WRITE_RATE_LIMIT)
async def recover_stuck_sync(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Recover an integration stuck in 'syncing' status.

    Called by the frontend when sync polling times out after 5 minutes.
    Resets the integration sync_status to 'error' so the user can retry.
    """
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if integration.sync_status != "syncing":
        return {
            "recovered": False,
            "message": f"Integration is not stuck (status: {integration.sync_status})",
            "sync_status": integration.sync_status,
        }

    sync_service = SyncService(db)
    recovered = await sync_service.recover_stuck_syncs(user_id=current_user.id)

    return {
        "recovered": recovered > 0,
        "message": f"Recovered {recovered} stuck sync(s)" if recovered > 0 else "No stuck syncs found to recover",
        "sync_status": "error" if recovered > 0 else integration.sync_status,
    }




