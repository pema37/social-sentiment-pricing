# backend/api/v1/routes/products.py

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_session
from models import User, Product, Sentiment
from schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductRead,
    PriceSuggestion,
)
from schemas.common import PaginatedResponse, PaginationParams
from api.v1.routes.auth import get_current_user
from services.sentiment_analyzer import sentiment_analyzer
from services.pricing_engine import pricing_engine
from core.rate_limit import limiter, WRITE_RATE_LIMIT, ANALYSIS_RATE_LIMIT, BULK_RATE_LIMIT

router = APIRouter(prefix="/products", tags=["products"])


# ───────────────────────────── Import Schemas ───────────────────────────── #

class ImportProductRow(BaseModel):
    """Single product row from CSV import."""
    name: str = Field(..., min_length=1, max_length=255)
    sku: Optional[str] = Field(default=None, max_length=100)
    base_price: Decimal = Field(..., gt=0)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=100)
    image_url: Optional[str] = None
    stock_quantity: Optional[int] = Field(default=None, ge=0)

    @field_validator('base_price', mode='before')
    @classmethod
    def parse_price(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            try:
                return Decimal(v.replace(',', '').replace('$', '').strip())
            except InvalidOperation:
                raise ValueError('Invalid price format')
        return v


class ImportProductsRequest(BaseModel):
    """Request body for bulk product import."""
    products: List[ImportProductRow] = Field(..., min_length=1, max_length=1000)


class ImportProductsResponse(BaseModel):
    """Response for bulk product import."""
    created: int
    failed: int
    errors: List[str]


# ───────────────────────────── CRUD Endpoints ───────────────────────────── #

@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_product(
    request: Request,
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
    request: Request,
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
    request: Request,
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
@limiter.limit(WRITE_RATE_LIMIT)
async def update_product(
    request: Request,
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
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_product(
    request: Request,
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


# ───────────────────────────── Bulk Import ───────────────────────────── #

@router.post(
    "/import",
    response_model=ImportProductsResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(BULK_RATE_LIMIT)
async def import_products(
    request: Request,
    payload: ImportProductsRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Import multiple products from CSV data.
    
    Accepts an array of product objects. Each product must have:
    - name (required)
    - base_price (required, must be > 0)
    
    Optional fields: sku, description, category, image_url, stock_quantity
    
    Compatible with WooCommerce and Shopify CSV exports.
    """
    created = 0
    failed = 0
    errors: List[str] = []

    for idx, row in enumerate(payload.products):
        try:
            product = Product(
                user_id=current_user.id,
                name=row.name.strip(),
                sku=row.sku.strip() if row.sku else None,
                description=row.description.strip() if row.description else None,
                category=row.category.strip() if row.category else None,
                image_url=row.image_url.strip() if row.image_url else None,
                base_price=row.base_price,
                current_price=row.base_price,
                is_active=True,
                auto_pricing_enabled=False,
                keywords=[],
            )
            session.add(product)
            created += 1
            
        except Exception as e:
            failed += 1
            errors.append(f"Row {idx + 1} ({row.name}): {str(e)}")

    # Commit all successful products
    if created > 0:
        try:
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save products: {str(e)}",
            )

    return ImportProductsResponse(
        created=created,
        failed=failed,
        errors=errors[:10],  # Limit errors to prevent huge responses
    )


# ───────────────────────────── Price Suggestion ───────────────────────────── #

@router.get("/{product_id}/price-suggestion", response_model=PriceSuggestion)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def get_price_suggestion(
    request: Request,
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
