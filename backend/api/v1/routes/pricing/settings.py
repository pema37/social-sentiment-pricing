# backend/api/v1/routes/pricing/settings.py
"""
Pricing settings endpoints.

FIX (2026-01-24): After updating settings, re-process pending recommendations
with the new thresholds. This ensures that when a user changes auto-approve
thresholds (e.g., from 10% to 75%), existing PENDING recommendations are
immediately evaluated against the new settings instead of staying stuck.
"""

import logging
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_session
from core.deps import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT
from models.user import User
from models.pricing_settings import PricingSettings
from services.pricing.approval_service import ApprovalService
from schemas.pricing import (
    PricingSettingsUpdate,
    PricingSettingsResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/settings", response_model=PricingSettingsResponse)
async def get_settings(
    request: Request,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get pricing settings for current user."""
    stmt = select(PricingSettings).where(PricingSettings.user_id == current_user.id)
    result = await db.execute(stmt)
    settings = result.scalars().first()
    
    if not settings:
        settings = PricingSettings(user_id=current_user.id)
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    
    return settings


@router.patch("/settings", response_model=PricingSettingsResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def update_settings(
    request: Request,
    data: PricingSettingsUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Update pricing settings.
    
    FIX: After saving new settings, automatically re-process any PENDING
    recommendations to check if they now qualify for auto-approval under
    the updated thresholds.
    """
    stmt = select(PricingSettings).where(PricingSettings.user_id == current_user.id)
    result = await db.execute(stmt)
    settings = result.scalars().first()
    
    if not settings:
        settings = PricingSettings(user_id=current_user.id)
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
    
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FIX: Re-process pending recommendations with new settings
    # 
    # When user updates thresholds (e.g., max_decrease from 10% to 75%),
    # existing PENDING recommendations should be re-evaluated immediately.
    # Without this, recommendations created before the settings change would
    # remain stuck as PENDING even though they now qualify for auto-approval.
    # ═══════════════════════════════════════════════════════════════════════════
    if settings.auto_approve_enabled:
        try:
            service = ApprovalService(db)
            applied = await service.process_auto_approvals(current_user.id)
            if applied:
                logger.info(
                    f"Auto-applied {len(applied)} recommendations after settings update "
                    f"for user {current_user.id}"
                )
        except Exception as e:
            # Log but don't fail the settings update - the settings were saved successfully
            logger.warning(
                f"Failed to process auto-approvals after settings update for user "
                f"{current_user.id}: {e}"
            )
    
    return settings


@router.get("/stats")
async def get_pricing_stats(
    request: Request,
    days: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get pricing statistics."""
    service = ApprovalService(db)
    return await service.get_approval_stats(current_user.id, days)




