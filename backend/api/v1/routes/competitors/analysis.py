# backend/api/v1/routes/competitors/analysis.py
"""Competitor analysis and comparison endpoints."""

import uuid as uuid_lib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from api.v1.routes.auth import get_current_user
from db.session import get_session
from models.user import User
from models.product import Product
from models.competitor import Competitor
from models.competitor_product import CompetitorProduct
from models.competitor_price_history import CompetitorPriceHistory
from schemas.competitor import CompetitorPriceComparison, CompetitorAlert

router = APIRouter()


@router.get("/compare/{product_id}", response_model=CompetitorPriceComparison)
async def compare_prices(
    request: Request,
    product_id: uuid_lib.UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Compare your product price against all tracked competitors."""
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .where(Product.user_id == current_user.id)
    )
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    cp_result = await db.execute(
        select(CompetitorProduct)
        .where(CompetitorProduct.product_id == product_id)
        .where(CompetitorProduct.is_active == True)
        .where(CompetitorProduct.current_price.is_not(None))
    )
    competitor_products = cp_result.scalars().all()
    
    if not competitor_products:
        return CompetitorPriceComparison(
            product_id=product_id,
            product_name=product.name,
            your_price=product.current_price,
            competitor_prices=[],
            your_position="no_data",
            recommendation="Add competitor product links to enable price comparison.",
        )
    
    competitor_prices = []
    for cp in competitor_products:
        comp_result = await db.execute(
            select(Competitor).where(Competitor.id == cp.competitor_id)
        )
        competitor = comp_result.scalars().first()
        
        diff = product.current_price - cp.current_price
        competitor_prices.append({
            "competitor_name": competitor.name,
            "price": cp.current_price,
            "url": cp.competitor_product_url,
            "difference": diff,
            "difference_percent": (diff / cp.current_price * 100).quantize(Decimal("0.01")) if cp.current_price else None,
            "last_updated": cp.last_price_update,
        })
    
    prices = [cp.current_price for cp in competitor_products]
    lowest = min(prices)
    highest = max(prices)
    average = sum(prices) / len(prices)
    
    if product.current_price <= lowest:
        position = "lowest"
    elif product.current_price >= highest:
        position = "highest"
    else:
        position = "middle"
    
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
    request: Request,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get recent significant competitor price changes."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    result = await db.execute(
        select(CompetitorPriceHistory)
        .join(CompetitorProduct)
        .join(Product)
        .where(Product.user_id == current_user.id)
        .where(CompetitorPriceHistory.observed_at >= cutoff)
        .where(
            (CompetitorPriceHistory.change_type == "promotion") |
            (CompetitorPriceHistory.change_type == "restock") |
            (func.abs(CompetitorPriceHistory.change_percent) > 5)
        )
        .order_by(CompetitorPriceHistory.observed_at.desc())
    )
    histories = result.scalars().all()
    
    alerts = []
    for h in histories:
        cp_result = await db.execute(
            select(CompetitorProduct).where(CompetitorProduct.id == h.competitor_product_id)
        )
        cp = cp_result.scalars().first()
        
        comp_result = await db.execute(
            select(Competitor).where(Competitor.id == cp.competitor_id)
        )
        competitor = comp_result.scalars().first()
        
        prod_result = await db.execute(
            select(Product).where(Product.id == cp.product_id)
        )
        product = prod_result.scalars().first()
        
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
