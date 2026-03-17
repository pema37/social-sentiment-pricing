# backend/api/v1/routes/competitors/crud.py
"""Competitor CRUD endpoints."""

import uuid as uuid_lib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.v1.routes.auth import get_current_user
from core.rate_limit import WRITE_RATE_LIMIT, limiter
from db.session import get_session
from models.competitor import Competitor
from models.competitor_price_history import CompetitorPriceHistory
from models.competitor_product import CompetitorProduct
from models.user import User
from schemas.common import PaginatedResponse, PaginationParams
from schemas.competitor import CompetitorCreate, CompetitorResponse, CompetitorUpdate

router = APIRouter()


@router.post("/", response_model=CompetitorResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_competitor(
    request: Request,
    competitor_in: CompetitorCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new competitor to track."""
    competitor = Competitor(
        user_id=current_user.id,
        name=competitor_in.name,
        website=competitor_in.website,
        description=competitor_in.description,
        scraping_config=competitor_in.scraping_config,
        is_active=competitor_in.is_active,
        scrape_frequency_minutes=competitor_in.scrape_frequency_minutes,
    )
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)
    return competitor


@router.get("/", response_model=PaginatedResponse[CompetitorResponse])
async def list_competitors(
    request: Request,
    is_active: bool | None = None,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all competitors for the current user."""
    query = select(Competitor).where(Competitor.user_id == current_user.id)

    if is_active is not None:
        query = query.where(Competitor.is_active == is_active)

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    query = query.offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    competitors = list(result.scalars().all())

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=competitors,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(
    request: Request,
    competitor_id: uuid_lib.UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific competitor."""
    result = await db.execute(
        select(Competitor).where(Competitor.id == competitor_id).where(Competitor.user_id == current_user.id)
    )
    competitor = result.scalars().first()

    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    return competitor


@router.patch("/{competitor_id}", response_model=CompetitorResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def update_competitor(
    request: Request,
    competitor_id: uuid_lib.UUID,
    competitor_in: CompetitorUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a competitor."""
    result = await db.execute(
        select(Competitor).where(Competitor.id == competitor_id).where(Competitor.user_id == current_user.id)
    )
    competitor = result.scalars().first()

    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    update_data = competitor_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(competitor, field, value)

    competitor.updated_at = datetime.now(UTC)
    db.add(competitor)
    await db.commit()
    await db.refresh(competitor)
    return competitor


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_competitor(
    request: Request,
    competitor_id: uuid_lib.UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a competitor and all associated data."""
    result = await db.execute(
        select(Competitor).where(Competitor.id == competitor_id).where(Competitor.user_id == current_user.id)
    )
    competitor = result.scalars().first()

    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    cp_result = await db.execute(select(CompetitorProduct).where(CompetitorProduct.competitor_id == competitor_id))
    competitor_products = cp_result.scalars().all()

    for cp in competitor_products:
        hist_result = await db.execute(
            select(CompetitorPriceHistory).where(CompetitorPriceHistory.competitor_product_id == cp.id)
        )
        histories = hist_result.scalars().all()
        for h in histories:
            await db.delete(h)
        await db.delete(cp)

    await db.delete(competitor)
    await db.commit()
