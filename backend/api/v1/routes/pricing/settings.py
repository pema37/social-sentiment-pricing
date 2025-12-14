# backend/api/v1/routes/pricing/settings.py
"""
Pricing settings endpoints.
"""

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
    """Update pricing settings."""
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
