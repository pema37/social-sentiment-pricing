# backend/api/v1/routes/pricing/recommendations.py
"""
Price recommendations and approval workflow endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from db.session import get_session
from core.deps import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT, ANALYSIS_RATE_LIMIT
from models.user import User
from models.product import Product
from models.price_recommendation import PriceRecommendation, RecommendationStatus
from services.pricing.recommendation_service import RecommendationService
from services.pricing.approval_service import ApprovalService
from schemas.common import PaginatedResponse, PaginationParams
from schemas.pricing import (
    PriceRecommendationResponse,
    RecommendationApprove,
    RecommendationReject,
)

router = APIRouter()


@router.post("/recommendations/generate/{product_id}", response_model=Optional[PriceRecommendationResponse])
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def generate_recommendation(
    request: Request,
    product_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger recommendation generation for a product."""
    product = await db.get(Product, product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")
    
    service = RecommendationService(db)
    recommendation = await service.generate_recommendation(product, current_user.id)
    return recommendation


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


@router.post("/recommendations/{recommendation_id}/approve", response_model=PriceRecommendationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def approve_recommendation(
    request: Request,
    recommendation_id: UUID,
    data: RecommendationApprove = None,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending recommendation."""
    service = ApprovalService(db)
    try:
        return await service.approve(recommendation_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recommendations/{recommendation_id}/reject", response_model=PriceRecommendationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def reject_recommendation(
    request: Request,
    recommendation_id: UUID,
    data: RecommendationReject,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Reject a pending recommendation."""
    service = ApprovalService(db)
    try:
        return await service.reject(recommendation_id, current_user.id, data.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recommendations/{recommendation_id}/apply", response_model=PriceRecommendationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def apply_recommendation(
    request: Request,
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Apply an approved recommendation (push price to e-commerce)."""
    service = ApprovalService(db)
    try:
        return await service.apply_price(recommendation_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    