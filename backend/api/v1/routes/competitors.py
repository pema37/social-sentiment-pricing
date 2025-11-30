# backend/api/v1/routes/competitors.py

"""
Competitor Tracking API Routes

Endpoints for managing competitors, their products, and price analysis.
"""

import uuid as uuid_lib
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlmodel import Session, select, func

from backend.api.v1.routes.auth import get_current_user
from backend.db.session import get_session
from backend.models.user import User
from backend.models.product import Product
from backend.models.competitor import Competitor
from backend.models.competitor_product import CompetitorProduct
from backend.models.competitor_price_history import CompetitorPriceHistory
from backend.schemas.competitor import (
    CompetitorCreate,
    CompetitorUpdate,
    CompetitorResponse,
    CompetitorListResponse,
    CompetitorProductCreate,
    CompetitorProductUpdate,
    CompetitorProductResponse,
    CompetitorProductWithDetails,
    CompetitorProductListResponse,
    CompetitorPriceHistoryResponse,
    CompetitorPriceHistoryListResponse,
    CompetitorPriceComparison,
    CompetitorAlert,
    CompetitorTrendAnalysis,
)
from backend.services.competitor_scraper import competitor_scraper, ScrapeResult
from backend.services.pricing_engine import pricing_engine, CompetitorPriceData


router = APIRouter(prefix="/competitors", tags=["competitors"])


# ============================================================
# Competitor CRUD
# ============================================================

@router.post("", response_model=CompetitorResponse, status_code=status.HTTP_201_CREATED)
async def create_competitor(
    competitor_in: CompetitorCreate,
    db: Session = Depends(get_session),
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
    db.commit()
    db.refresh(competitor)
    return competitor


@router.get("", response_model=CompetitorListResponse)
async def list_competitors(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all competitors for the current user."""
    query = select(Competitor).where(Competitor.user_id == current_user.id)
    
    if is_active is not None:
        query = query.where(Competitor.is_active == is_active)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = db.exec(count_query).one()
    
    # Paginate
    query = query.offset((page - 1) * size).limit(size)
    competitors = db.exec(query).all()
    
    return CompetitorListResponse(
        items=competitors,
        total=total,
        page=page,
        size=size,
    )


@router.get("/{competitor_id}", response_model=CompetitorResponse)
async def get_competitor(
    competitor_id: uuid_lib.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific competitor."""
    competitor = db.exec(
        select(Competitor)
        .where(Competitor.id == competitor_id)
        .where(Competitor.user_id == current_user.id)
    ).first()
    
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    return competitor


@router.patch("/{competitor_id}", response_model=CompetitorResponse)
async def update_competitor(
    competitor_id: uuid_lib.UUID,
    competitor_in: CompetitorUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a competitor."""
    competitor = db.exec(
        select(Competitor)
        .where(Competitor.id == competitor_id)
        .where(Competitor.user_id == current_user.id)
    ).first()
    
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    update_data = competitor_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(competitor, field, value)
    
    competitor.updated_at = datetime.now(timezone.utc)
    db.add(competitor)
    db.commit()
    db.refresh(competitor)
    return competitor


@router.delete("/{competitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor(
    competitor_id: uuid_lib.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a competitor and all associated data."""
    competitor = db.exec(
        select(Competitor)
        .where(Competitor.id == competitor_id)
        .where(Competitor.user_id == current_user.id)
    ).first()
    
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    # Delete associated competitor products and their history
    competitor_products = db.exec(
        select(CompetitorProduct).where(CompetitorProduct.competitor_id == competitor_id)
    ).all()
    
    for cp in competitor_products:
        # Delete price history
        db.exec(
            select(CompetitorPriceHistory)
            .where(CompetitorPriceHistory.competitor_product_id == cp.id)
        )
        histories = db.exec(
            select(CompetitorPriceHistory)
            .where(CompetitorPriceHistory.competitor_product_id == cp.id)
        ).all()
        for h in histories:
            db.delete(h)
        db.delete(cp)
    
    db.delete(competitor)
    db.commit()


# ============================================================
# Competitor Product CRUD
# ============================================================

@router.post("/products", response_model=CompetitorProductResponse, status_code=status.HTTP_201_CREATED)
async def create_competitor_product(
    product_in: CompetitorProductCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Link a competitor product to your product."""
    # Verify product belongs to user
    product = db.exec(
        select(Product)
        .where(Product.id == product_in.product_id)
        .where(Product.user_id == current_user.id)
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Verify competitor belongs to user
    competitor = db.exec(
        select(Competitor)
        .where(Competitor.id == product_in.competitor_id)
        .where(Competitor.user_id == current_user.id)
    ).first()
    
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    competitor_product = CompetitorProduct(
        product_id=product_in.product_id,
        competitor_id=product_in.competitor_id,
        competitor_product_name=product_in.competitor_product_name,
        competitor_product_url=product_in.competitor_product_url,
        competitor_sku=product_in.competitor_sku,
        currency=product_in.currency,
        match_confidence=product_in.match_confidence,
        notes=product_in.notes,
        is_active=product_in.is_active,
    )
    db.add(competitor_product)
    db.commit()
    db.refresh(competitor_product)
    return competitor_product


@router.get("/products", response_model=CompetitorProductListResponse)
async def list_competitor_products(
    product_id: Optional[uuid_lib.UUID] = None,
    competitor_id: Optional[uuid_lib.UUID] = None,
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List competitor product mappings."""
    # Build query with user access check through joins
    query = (
        select(CompetitorProduct)
        .join(Product)
        .where(Product.user_id == current_user.id)
    )
    
    if product_id:
        query = query.where(CompetitorProduct.product_id == product_id)
    if competitor_id:
        query = query.where(CompetitorProduct.competitor_id == competitor_id)
    if is_active is not None:
        query = query.where(CompetitorProduct.is_active == is_active)
    
    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = db.exec(count_query).one()
    
    # Paginate
    query = query.offset((page - 1) * size).limit(size)
    items = db.exec(query).all()
    
    return CompetitorProductListResponse(
        items=items,
        total=total,
        page=page,
        size=size,
    )


@router.get("/products/{competitor_product_id}", response_model=CompetitorProductWithDetails)
async def get_competitor_product(
    competitor_product_id: uuid_lib.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a competitor product with full details."""
    cp = db.exec(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    ).first()
    
    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    
    # Fetch related entities
    product = db.exec(select(Product).where(Product.id == cp.product_id)).first()
    competitor = db.exec(select(Competitor).where(Competitor.id == cp.competitor_id)).first()
    
    # Calculate price difference
    price_diff = None
    price_diff_percent = None
    if cp.current_price and product.current_price:
        price_diff = product.current_price - cp.current_price
        if cp.current_price > 0:
            price_diff_percent = (price_diff / cp.current_price * 100).quantize(Decimal("0.01"))
    
    return CompetitorProductWithDetails(
        **cp.model_dump(),
        competitor_name=competitor.name,
        your_product_name=product.name,
        your_current_price=product.current_price,
        price_difference=price_diff,
        price_difference_percent=price_diff_percent,
    )


@router.patch("/products/{competitor_product_id}", response_model=CompetitorProductResponse)
async def update_competitor_product(
    competitor_product_id: uuid_lib.UUID,
    product_in: CompetitorProductUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a competitor product mapping."""
    cp = db.exec(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    ).first()
    
    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    
    update_data = product_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cp, field, value)
    
    cp.updated_at = datetime.now(timezone.utc)
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


@router.delete("/products/{competitor_product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor_product(
    competitor_product_id: uuid_lib.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a competitor product mapping."""
    cp = db.exec(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    ).first()
    
    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    
    # Delete price history
    histories = db.exec(
        select(CompetitorPriceHistory)
        .where(CompetitorPriceHistory.competitor_product_id == cp.id)
    ).all()
    for h in histories:
        db.delete(h)
    
    db.delete(cp)
    db.commit()


# ============================================================
# Price Scraping & History
# ============================================================

@router.post("/products/{competitor_product_id}/scrape", response_model=CompetitorPriceHistoryResponse)
async def scrape_competitor_price(
    competitor_product_id: uuid_lib.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a price scrape for a competitor product."""
    # Get competitor product with access check
    cp = db.exec(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    ).first()
    
    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    
    # Get competitor for scraping config
    competitor = db.exec(
        select(Competitor).where(Competitor.id == cp.competitor_id)
    ).first()
    
    # Perform scrape
    result = await competitor_scraper.scrape_price(cp, competitor)
    
    if not result.success:
        # Update competitor error tracking
        competitor.consecutive_failures += 1
        competitor.last_error = result.error
        db.add(competitor)
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Scrape failed: {result.error}"
        )
    
    # Reset error tracking on success
    competitor.consecutive_failures = 0
    competitor.last_error = None
    competitor.last_scraped_at = datetime.now(timezone.utc)
    
    # Create history record if price changed
    history = competitor_scraper.create_price_history_record(cp, result)
    
    if history:
        db.add(history)
        
        # Update competitor product with new price
        cp.current_price = result.price
        cp.last_price_update = result.scraped_at
        cp.price_available = result.is_available
        cp.updated_at = datetime.now(timezone.utc)
        db.add(cp)
    
    db.add(competitor)
    db.commit()
    
    if history:
        db.refresh(history)
        return history
    
    # Return a "no change" response
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
        is_available=result.is_available,
        observed_at=result.scraped_at,
    )


@router.get("/products/{competitor_product_id}/history", response_model=CompetitorPriceHistoryListResponse)
async def get_price_history(
    competitor_product_id: uuid_lib.UUID,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get price history for a competitor product."""
    # Access check
    cp = db.exec(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    ).first()
    
    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    history = db.exec(
        select(CompetitorPriceHistory)
        .where(CompetitorPriceHistory.competitor_product_id == competitor_product_id)
        .where(CompetitorPriceHistory.observed_at >= cutoff)
        .order_by(CompetitorPriceHistory.observed_at.desc())
    ).all()
    
    return CompetitorPriceHistoryListResponse(
        items=history,
        total=len(history),
    )


# ============================================================
# Analysis & Comparison
# ============================================================

@router.get("/compare/{product_id}", response_model=CompetitorPriceComparison)
async def compare_prices(
    product_id: uuid_lib.UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Compare your product price against all tracked competitors."""
    # Get product
    product = db.exec(
        select(Product)
        .where(Product.id == product_id)
        .where(Product.user_id == current_user.id)
    ).first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get all competitor products for this product
    competitor_products = db.exec(
        select(CompetitorProduct)
        .where(CompetitorProduct.product_id == product_id)
        .where(CompetitorProduct.is_active == True)
        .where(CompetitorProduct.current_price.is_not(None))
    ).all()
    
    if not competitor_products:
        return CompetitorPriceComparison(
            product_id=product_id,
            product_name=product.name,
            your_price=product.current_price,
            competitor_prices=[],
            your_position="no_data",
            recommendation="Add competitor product links to enable price comparison.",
        )
    
    # Build competitor price list
    competitor_prices = []
    for cp in competitor_products:
        competitor = db.exec(
            select(Competitor).where(Competitor.id == cp.competitor_id)
        ).first()
        
        diff = product.current_price - cp.current_price
        competitor_prices.append({
            "competitor_name": competitor.name,
            "price": cp.current_price,
            "url": cp.competitor_product_url,
            "difference": diff,
            "difference_percent": (diff / cp.current_price * 100).quantize(Decimal("0.01")) if cp.current_price else None,
            "last_updated": cp.last_price_update,
        })
    
    # Calculate stats
    prices = [cp.current_price for cp in competitor_products]
    lowest = min(prices)
    highest = max(prices)
    average = sum(prices) / len(prices)
    
    # Determine position
    if product.current_price <= lowest:
        position = "lowest"
    elif product.current_price >= highest:
        position = "highest"
    else:
        position = "middle"
    
    # Generate recommendation
    if position == "highest":
        recommendation = f"You're priced {((product.current_price - average) / average * 100):.1f}% above average. Consider lowering price to remain competitive."
    elif position == "lowest":
        recommendation = f"You're the price leader at {((average - product.current_price) / average * 100):.1f}% below average. Opportunity to increase margins."
    else:
        recommendation = "Competitively positioned. Monitor for competitor changes."
    
    return CompetitorPriceComparison(
        product_id=product_id,
        product_name=product.name,
        your_price=product.current_price,
        competitor_prices=competitor_prices,
        lowest_competitor_price=lowest,
        highest_competitor_price=highest,
        average_competitor_price=average.quantize(Decimal("0.01")),
        your_position=position,
        recommendation=recommendation,
    )


@router.get("/alerts", response_model=List[CompetitorAlert])
async def get_competitor_alerts(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get recent significant competitor price changes."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    # Get recent price changes for user's tracked competitors
    histories = db.exec(
        select(CompetitorPriceHistory)
        .join(CompetitorProduct)
        .join(Product)
        .where(Product.user_id == current_user.id)
        .where(CompetitorPriceHistory.observed_at >= cutoff)
        .where(
            (CompetitorPriceHistory.change_type == "promotion") |
            (CompetitorPriceHistory.change_type == "restock") |
            (func.abs(CompetitorPriceHistory.change_percent) > 5)  # >5% change
        )
        .order_by(CompetitorPriceHistory.observed_at.desc())
    ).all()
    
    alerts = []
    for h in histories:
        cp = db.exec(
            select(CompetitorProduct).where(CompetitorProduct.id == h.competitor_product_id)
        ).first()
        competitor = db.exec(
            select(Competitor).where(Competitor.id == cp.competitor_id)
        ).first()
        product = db.exec(
            select(Product).where(Product.id == cp.product_id)
        ).first()
        
        # Determine alert type
        if h.change_type == "promotion":
            alert_type = "price_drop"
            suggested_action = "Monitor closely. Consider matching if promotion persists."
        elif h.change_type == "restock":
            alert_type = "back_in_stock"
            suggested_action = "Competitor product back in stock. Review your inventory."
        elif h.change_percent and h.change_percent < 0:
            alert_type = "price_drop"
            suggested_action = "Evaluate if price adjustment needed to stay competitive."
        else:
            alert_type = "price_increase"
            suggested_action = "Opportunity to increase margins while remaining competitive."
        
        alerts.append(CompetitorAlert(
            alert_type=alert_type,
            competitor_name=competitor.name,
            competitor_product_name=cp.competitor_product_name,
            product_id=product.id,
            your_product_name=product.name,
            old_price=h.old_price,
            new_price=h.new_price,
            change_percent=h.change_percent,
            your_current_price=product.current_price,
            suggested_action=suggested_action,
            observed_at=h.observed_at,
        ))
    
    return alerts

