# backend/api/v1/routes/products.py

from datetime import datetime, timezone
from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.db.session import get_session
from backend.models import User, Product, Sentiment
from backend.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductRead,
    PriceSuggestion,
)
from backend.schemas.common import PaginatedResponse, PaginationParams
from backend.api.v1.routes.auth import get_current_user
from backend.services.sentiment_analyzer import sentiment_analyzer
from backend.services.pricing_engine import pricing_engine

router = APIRouter(prefix="/products", tags=["products"])


# ───────────────────────────── CRUD Endpoints ───────────────────────────── #

@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new product."""
    product = Product(
        user_id=current_user.id,
        name=payload.name,
        sku=payload.sku,
        description=payload.description,
        category=payload.category,
        image_url=payload.image_url,
        is_active=payload.is_active,
        base_price=payload.base_price,
        current_price=payload.base_price,
        cost=payload.cost,
        min_price=payload.min_price,
        max_price=payload.max_price,
        sentiment_multiplier=payload.sentiment_multiplier,
        auto_pricing_enabled=payload.auto_pricing_enabled,
        keywords=payload.keywords,
    )

    session.add(product)
    await session.commit()
    await session.refresh(product)

    return product


@router.get("", response_model=PaginatedResponse[ProductRead])
async def list_products(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all products for the current user with pagination."""
    # Count total
    count_stmt = select(Product).where(Product.user_id == current_user.id)
    count_result = await session.execute(count_stmt)
    total = len(count_result.scalars().all())
    
    # Get paginated items
    statement = (
        select(Product)
        .where(Product.user_id == current_user.id)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    result = await session.execute(statement)
    products = result.scalars().all()
    
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    
    return PaginatedResponse(
        items=products,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific product by ID."""
    product = await session.get(Product, product_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    if product.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this product",
        )

    return product


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a product."""
    product = await session.get(Product, product_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    if product.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this product",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    product.updated_at = datetime.now(timezone.utc)

    session.add(product)
    await session.commit()
    await session.refresh(product)

    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a product."""
    product = await session.get(Product, product_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    if product.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this product",
        )

    await session.delete(product)
    await session.commit()

    return None


# ───────────────────────────── Price Suggestion ───────────────────────────── #

@router.get("/{product_id}/price-suggestion", response_model=PriceSuggestion)
async def get_price_suggestion(
    product_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get AI-powered price suggestion based on sentiment analysis."""
    product = await session.get(Product, product_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    if product.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this product",
        )

    statement = select(Sentiment).where(Sentiment.product_id == product_id)
    result = await session.execute(statement)
    sentiments = result.scalars().all()

    if sentiments:
        sentiment_data = [
            {
                "compound": s.compound_score,
                "label": "positive" if s.compound_score > Decimal("0.05")
                         else "negative" if s.compound_score < Decimal("-0.05")
                         else "neutral"
            }
            for s in sentiments
        ]
        aggregate = sentiment_analyzer.calculate_aggregate(sentiment_data)
        sentiment_score = aggregate["average_compound"]
        mention_volume = aggregate["total_count"]
    else:
        sentiment_score = Decimal("0")
        mention_volume = 0

    suggestion = pricing_engine.calculate_suggestion(
        product=product,
        sentiment_score=sentiment_score,
        mention_volume=mention_volume,
    )

    return suggestion
