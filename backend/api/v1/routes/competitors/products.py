# backend/api/v1/routes/competitors/products.py
"""Competitor Product CRUD endpoints."""

import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from api.v1.routes.auth import get_current_user
from db.session import get_session
from core.rate_limit import limiter, WRITE_RATE_LIMIT
from models.user import User
from models.product import Product
from models.competitor import Competitor
from models.competitor_product import CompetitorProduct
from models.competitor_price_history import CompetitorPriceHistory
from schemas.competitor import (
    CompetitorProductCreate,
    CompetitorProductUpdate,
    CompetitorProductResponse,
    CompetitorProductWithDetails,
)
from schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


@router.post("/products/", response_model=CompetitorProductResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_competitor_product(
    request: Request,
    product_in: CompetitorProductCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Link a competitor product to your product."""
    # Verify product belongs to user
    result = await db.execute(
        select(Product)
        .where(Product.id == product_in.product_id)
        .where(Product.user_id == current_user.id)
    )
    product = result.scalars().first()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Verify competitor belongs to user
    result = await db.execute(
        select(Competitor)
        .where(Competitor.id == product_in.competitor_id)
        .where(Competitor.user_id == current_user.id)
    )
    competitor = result.scalars().first()
    
    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")
    
    competitor_product = CompetitorProduct(
        product_id=product_in.product_id,
        competitor_id=product_in.competitor_id,
        competitor_product_name=product_in.competitor_product_name,
        competitor_product_url=product_in.competitor_product_url,
        competitor_sku=product_in.competitor_sku,
        current_price=product_in.current_price,
        currency=product_in.currency,
        match_confidence=product_in.match_confidence,
        notes=product_in.notes,
        is_active=product_in.is_active,
    )
    db.add(competitor_product)
    await db.commit()
    await db.refresh(competitor_product)
    return competitor_product


@router.get("/products/", response_model=PaginatedResponse[CompetitorProductResponse])
async def list_competitor_products(
    request: Request,
    product_id: Optional[uuid_lib.UUID] = None,
    competitor_id: Optional[uuid_lib.UUID] = None,
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List competitor product mappings."""
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
    
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    
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


@router.get("/products/{competitor_product_id}", response_model=CompetitorProductWithDetails)
async def get_competitor_product(
    request: Request,
    competitor_product_id: uuid_lib.UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a competitor product with full details."""
    result = await db.execute(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    )
    cp = result.scalars().first()
    
    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    
    prod_result = await db.execute(select(Product).where(Product.id == cp.product_id))
    product = prod_result.scalars().first()
    
    comp_result = await db.execute(select(Competitor).where(Competitor.id == cp.competitor_id))
    competitor = comp_result.scalars().first()
    
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
@limiter.limit(WRITE_RATE_LIMIT)
async def update_competitor_product(
    request: Request,
    competitor_product_id: uuid_lib.UUID,
    product_in: CompetitorProductUpdate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a competitor product mapping."""
    result = await db.execute(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    )
    cp = result.scalars().first()
    
    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    
    update_data = product_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cp, field, value)
    
    cp.updated_at = datetime.utcnow()
    db.add(cp)
    await db.commit()
    await db.refresh(cp)
    return cp


@router.delete("/products/{competitor_product_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_competitor_product(
    request: Request,
    competitor_product_id: uuid_lib.UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a competitor product mapping."""
    result = await db.execute(
        select(CompetitorProduct)
        .join(Product)
        .where(CompetitorProduct.id == competitor_product_id)
        .where(Product.user_id == current_user.id)
    )
    cp = result.scalars().first()
    
    if not cp:
        raise HTTPException(status_code=404, detail="Competitor product not found")
    
    hist_result = await db.execute(
        select(CompetitorPriceHistory)
        .where(CompetitorPriceHistory.competitor_product_id == cp.id)
    )
    histories = hist_result.scalars().all()
    for h in histories:
        await db.delete(h)
    
    await db.delete(cp)
    await db.commit()
