# backend/api/v1/routes/competitors/scraping.py
"""Price scraping and history endpoints."""

import uuid as uuid_lib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.v1.routes.auth import get_current_user
from core.rate_limit import BULK_RATE_LIMIT, limiter
from db.session import get_session
from models.competitor import Competitor
from models.competitor_price_history import CompetitorPriceHistory
from models.competitor_product import CompetitorProduct
from models.product import Product
from models.user import User
from schemas.competitor import (
    CompetitorPriceHistoryListResponse,
    CompetitorPriceHistoryResponse,
)
from services.competitor_scraper import competitor_scraper

router = APIRouter()


@router.post("/products/{competitor_product_id}/scrape", response_model=CompetitorPriceHistoryResponse)
@limiter.limit(BULK_RATE_LIMIT)
async def scrape_competitor_price(
    request: Request,
    competitor_product_id: uuid_lib.UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a price scrape for a competitor product."""
    result = await db.execute(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    )
    cp = result.scalars().first()

    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")

    comp_result = await db.execute(select(Competitor).where(Competitor.id == cp.competitor_id))
    competitor = comp_result.scalars().first()

    scrape_result = await competitor_scraper.scrape_price(cp, competitor)

    if not scrape_result.success:
        competitor.consecutive_failures += 1
        competitor.last_error = scrape_result.error
        db.add(competitor)
        await db.commit()
        raise HTTPException(status_code=502, detail=f"Scrape failed: {scrape_result.error}")

    competitor.consecutive_failures = 0
    competitor.last_error = None
    competitor.last_scraped_at = datetime.now(UTC)

    history = competitor_scraper.create_price_history_record(cp, scrape_result)

    if history:
        db.add(history)
        cp.current_price = scrape_result.price
        cp.last_price_update = scrape_result.scraped_at
        cp.price_available = scrape_result.is_available
        cp.updated_at = datetime.now(UTC)
        db.add(cp)

    db.add(competitor)
    await db.commit()

    if history:
        await db.refresh(history)
        return history

    return CompetitorPriceHistoryResponse(
        id=uuid_lib.uuid4(),
        competitor_product_id=cp.id,
        old_price=cp.current_price,
        new_price=cp.current_price or Decimal("0"),
        currency=cp.currency,
        change_amount=Decimal("0"),
        change_percent=Decimal("0"),
        change_type="no_change",
        detected_promotion=False,
        was_available=cp.price_available,
        is_available=scrape_result.is_available,
        observed_at=scrape_result.scraped_at,
    )


@router.get("/products/{competitor_product_id}/history", response_model=CompetitorPriceHistoryListResponse)
async def get_price_history(
    request: Request,
    competitor_product_id: uuid_lib.UUID,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get price history for a competitor product."""
    result = await db.execute(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    )
    cp = result.scalars().first()

    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")

    cutoff = datetime.now(UTC) - timedelta(days=days)

    hist_result = await db.execute(
        select(CompetitorPriceHistory)
        .where(CompetitorPriceHistory.competitor_product_id == competitor_product_id)
        .where(CompetitorPriceHistory.observed_at >= cutoff)
        .order_by(CompetitorPriceHistory.observed_at.desc())
    )
    history = hist_result.scalars().all()

    return CompetitorPriceHistoryListResponse(
        items=history,
        total=len(history),
    )
