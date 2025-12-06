# api/v1/routes/analytics.py
"""
Analytics API routes for dashboard metrics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.core.security import get_current_user
from backend.models.user import User
from backend.services.analytics.analytics_service import AnalyticsService
from backend.schemas.analytics import (
    DashboardOverview,
    ProductSummary,
    RecommendationStats,
    AlertAnalytics,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardOverview)
async def get_dashboard_overview(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get main dashboard overview metrics."""
    service = AnalyticsService(session, str(current_user.id))
    return await service.get_dashboard_overview()


@router.get("/products", response_model=list[ProductSummary])
async def get_product_summaries(
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get product summary cards for dashboard."""
    service = AnalyticsService(session, str(current_user.id))
    return await service.get_product_summaries(limit=limit)


@router.get("/recommendations/stats", response_model=RecommendationStats)
async def get_recommendation_stats(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get recommendation performance statistics."""
    service = AnalyticsService(session, str(current_user.id))
    return await service.get_recommendation_stats(days=days)


@router.get("/alerts/stats", response_model=AlertAnalytics)
async def get_alert_analytics(
    days: int = Query(7, ge=1, le=90),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get alert statistics."""
    service = AnalyticsService(session, str(current_user.id))
    return await service.get_alert_analytics(days=days)
