# backend/api/v1/routes/pricing/_list_endpoints.py
"""
List, get, and stats endpoints for recommendations.
Read-only operations.
"""

from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta, UTC
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from db.session import get_session
from core.deps import get_current_user
from models.user import User
from models.price_recommendation import PriceRecommendation, RecommendationStatus
from schemas.common import PaginatedResponse, PaginationParams
from schemas.pricing import PriceRecommendationResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/recommendations/stats")
async def get_recommendation_stats(
    request: Request,
    days: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get recommendation statistics."""
    since = datetime.now(UTC) - timedelta(days=days)
    
    # Count by status
    stats = {}
    for rec_status in RecommendationStatus:
        stmt = (
            select(func.count(PriceRecommendation.id))
            .where(PriceRecommendation.user_id == current_user.id)
            .where(PriceRecommendation.status == rec_status)
            .where(PriceRecommendation.created_at >= since)
        )
        result = await db.execute(stmt)
        stats[rec_status.value] = result.scalar() or 0
    
    # Calculate totals
    total_generated = sum(stats.values())
    total_applied = stats.get("applied", 0)
    total_rejected = stats.get("rejected", 0)
    total_expired = stats.get("expired", 0)
    total_pending = stats.get("pending", 0)
    
    # Approval rate
    decided = total_applied + total_rejected
    approval_rate = (total_applied / decided * 100) if decided > 0 else 0
    
    # Average confidence
    stmt_conf = (
        select(func.avg(PriceRecommendation.confidence_score))
        .where(PriceRecommendation.user_id == current_user.id)
        .where(PriceRecommendation.created_at >= since)
    )
    result = await db.execute(stmt_conf)
    avg_confidence = result.scalar()
    
    # Average price change percent
    stmt_change = (
        select(func.avg(
            (PriceRecommendation.recommended_price - PriceRecommendation.current_price) 
            / PriceRecommendation.current_price * 100
        ))
        .where(PriceRecommendation.user_id == current_user.id)
        .where(PriceRecommendation.current_price > 0)
        .where(PriceRecommendation.created_at >= since)
    )
    result = await db.execute(stmt_change)
    avg_price_change = result.scalar()
    
    return {
        "total_generated": total_generated,
        "total_applied": total_applied,
        "total_rejected": total_rejected,
        "total_expired": total_expired,
        "total_pending": total_pending,
        "approval_rate": round(approval_rate, 1),
        "avg_confidence": round(float(avg_confidence), 2) if avg_confidence else None,
        "avg_price_change_percent": round(float(avg_price_change), 2) if avg_price_change else None,
    }


@router.get("/recommendations", response_model=PaginatedResponse[PriceRecommendationResponse])
async def list_recommendations(
    request: Request,
    status: Optional[RecommendationStatus] = Query(default=None),
    product_id: Optional[UUID] = Query(default=None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List price recommendations."""
    query = select(PriceRecommendation).where(
        PriceRecommendation.user_id == current_user.id
    )
    
    if status:
        query = query.where(PriceRecommendation.status == status)
    if product_id:
        query = query.where(PriceRecommendation.product_id == product_id)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    
    # Paginate
    query = query.order_by(PriceRecommendation.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    items = list(result.scalars().all())
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/recommendations/pending", response_model=PaginatedResponse[PriceRecommendationResponse])
async def list_pending_recommendations(
    request: Request,
    product_id: Optional[UUID] = Query(default=None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List pending recommendations (approval queue)."""
    query = select(PriceRecommendation).where(
        PriceRecommendation.user_id == current_user.id,
        PriceRecommendation.status == RecommendationStatus.PENDING,
    )
    
    if product_id:
        query = query.where(PriceRecommendation.product_id == product_id)
    
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    
    query = query.order_by(PriceRecommendation.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    items = list(result.scalars().all())
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/recommendations/{recommendation_id}", response_model=PriceRecommendationResponse)
async def get_recommendation(
    request: Request,
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific recommendation."""
    recommendation = await db.get(PriceRecommendation, recommendation_id)
    if not recommendation or recommendation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return recommendation




    