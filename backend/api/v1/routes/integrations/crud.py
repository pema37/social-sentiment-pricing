# backend/api/v1/routes/integrations/crud.py
"""
Integration CRUD endpoints.

FIX (2026-01-24): The DELETE endpoint now performs a HARD DELETE when the
integration is already disconnected. Previously it only did a soft delete
(changing status to DISCONNECTED), so clicking "Delete" on a disconnected
integration did nothing visible - the record remained in the database and UI.

FIX (2026-01-27): Also delete IntegrationSyncLog records before deleting
the integration to avoid foreign key constraint violations.

FIX (2026-01-27): PATCH now supports credential updates for WooCommerce
(consumer_key + consumer_secret) to allow reconnection without deleting.

Now:
- Active/Paused integrations → Soft delete (status = DISCONNECTED)
- Already Disconnected integrations → Hard delete (removed from database)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import select

from core.deps import get_current_user
from core.encryption import encrypt_token
from core.rate_limit import WRITE_RATE_LIMIT, rate_limit
from db.session import get_session
from models.integration import (
    EcommercePlatform,
    Integration,
    IntegrationStatus,
    IntegrationSyncLog,
    ProductIntegrationLink,
)
from schemas.integration import (
    IntegrationListResponse,
    IntegrationResponse,
    IntegrationUpdate,
)
from services.integration import WebhookRegistrationService, WooCommerceService

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=IntegrationListResponse)
async def list_integrations(
    request: Request,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntegrationListResponse:
    """List all integrations for current user."""
    stmt = select(Integration).where(Integration.user_id == current_user.id)

    result = await db.execute(stmt)
    integrations_list = list(result.scalars().all())

    # Sort in Python to avoid SQLAlchemy type issues with .desc()
    integrations_sorted = sorted(
        integrations_list, key=lambda x: x.created_at if x.created_at else datetime.min, reverse=True
    )

    return IntegrationListResponse(
        integrations=[IntegrationResponse.model_validate(i) for i in integrations_sorted],
        total=len(integrations_sorted),
    )


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntegrationResponse:
    """Get a specific integration."""
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    return IntegrationResponse.model_validate(integration)


@router.patch("/{integration_id}", response_model=IntegrationResponse)
@rate_limit(WRITE_RATE_LIMIT)
async def update_integration(
    request: Request,
    integration_id: UUID,
    data: IntegrationUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IntegrationResponse:
    """
    Update integration settings.

    FIX (2026-01-27): Now supports credential updates for WooCommerce.
    If consumer_key and consumer_secret are provided, will:
    1. Verify the new credentials against the store
    2. Update the encrypted credentials
    3. Clear any error messages
    4. Set status to ACTIVE
    """
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # Handle basic field updates
    if data.store_name is not None:
        integration.store_name = data.store_name
    if data.status is not None:
        integration.status = IntegrationStatus(data.status.value)
    if data.settings is not None:
        integration.settings = data.settings

    # ═══════════════════════════════════════════════════════════════════════════
    # FIX (2026-01-27): Handle WooCommerce credential updates
    # ═══════════════════════════════════════════════════════════════════════════
    if data.consumer_key and data.consumer_secret:
        # Only WooCommerce supports API key updates
        if integration.platform != EcommercePlatform.WOOCOMMERCE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credential updates are only supported for WooCommerce integrations",
            )

        # Verify new credentials before saving
        credentials = f"{data.consumer_key}:{data.consumer_secret}"
        service = WooCommerceService()

        is_valid = await service.verify_credentials(
            store_url=integration.store_url,
            access_token=credentials,
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid API credentials. Please verify your consumer key and secret.",
            )

        # Credentials are valid - update them
        integration.access_token_encrypted = encrypt_token(credentials)
        integration.error_message = None  # Clear old errors
        integration.status = IntegrationStatus.ACTIVE

        logger.info(f"WooCommerce credentials updated for integration {integration_id}")

    integration.updated_at = datetime.now(UTC)
    db.add(integration)
    await db.commit()
    await db.refresh(integration)

    return IntegrationResponse.model_validate(integration)


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
@rate_limit(WRITE_RATE_LIMIT)
async def disconnect_integration(
    request: Request,
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Disconnect or delete an integration.

    Behavior:
    - ACTIVE/PAUSED integrations: Soft delete (status → DISCONNECTED)
      - Unregisters webhooks from the platform
      - Keeps the record for potential reconnection

    - DISCONNECTED integrations: Hard delete (removed from database)
      - Deletes all associated sync logs
      - Deletes all associated product links
      - Permanently removes the integration record

    FIX (2026-01-24): Previously this only did soft delete, so clicking "Delete"
    on an already-disconnected integration did nothing. Now it actually removes it.

    FIX (2026-01-27): Now also deletes IntegrationSyncLog records to avoid
    foreign key constraint violations.
    """
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    # ═══════════════════════════════════════════════════════════════════════════
    # FIX: If already disconnected, perform HARD DELETE
    # ═══════════════════════════════════════════════════════════════════════════
    if integration.status == IntegrationStatus.DISCONNECTED:
        # FIX (2026-01-27): Delete sync logs first (foreign key constraint)
        sync_logs_stmt = select(IntegrationSyncLog).where(IntegrationSyncLog.integration_id == integration_id)
        sync_logs_result = await db.execute(sync_logs_stmt)
        sync_logs = list(sync_logs_result.scalars().all())

        for log in sync_logs:
            db.delete(log)

        # Delete associated product links (foreign key constraint)
        links_stmt = select(ProductIntegrationLink).where(ProductIntegrationLink.integration_id == integration_id)
        links_result = await db.execute(links_stmt)
        links = list(links_result.scalars().all())

        for link in links:
            db.delete(link)

        # Now delete the integration itself
        db.delete(integration)
        await db.commit()

        logger.info(
            f"Integration {integration_id} permanently deleted by user {current_user.id} "
            f"(removed {len(sync_logs)} sync logs, {len(links)} product links)"
        )
        return

    # ═══════════════════════════════════════════════════════════════════════════
    # ACTIVE/PAUSED: Soft delete - unregister webhooks and mark as disconnected
    # ═══════════════════════════════════════════════════════════════════════════
    if integration.status == IntegrationStatus.ACTIVE:
        try:
            webhook_service = WebhookRegistrationService(db)
            await webhook_service.unregister_webhooks(integration.id)
            logger.info(f"Webhooks unregistered for integration {integration_id}")
        except Exception as e:
            logger.warning(f"Failed to unregister webhooks: {e}")

    integration.status = IntegrationStatus.DISCONNECTED
    integration.updated_at = datetime.now(UTC)
    db.add(integration)
    await db.commit()

    logger.info(f"Integration {integration_id} disconnected by user {current_user.id}")
