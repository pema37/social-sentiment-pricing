# backend/api/v1/routes/products.py
"""
Products API Router
===================
Handles all product CRUD operations, bulk import, and AI price suggestions.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import List, Optional
from uuid import UUID
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_session
from models import User, Product, Sentiment
from models.price_history import PriceHistory
from models.sentiment import Sentiment
from models.social_mention import SocialMention
from models.competitor_product import CompetitorProduct
from models.price_recommendation import PriceRecommendation
from models.recommendation_outcome import RecommendationOutcome
from models.pricing_rule import PricingRule
from models.alert import Alert
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
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# IMPORT SCHEMAS
# Used for bulk CSV import functionality
# ═══════════════════════════════════════════════════════════════════════════════

class ImportProductRow(BaseModel):
    """
    Single product row from CSV import.
    Compatible with WooCommerce and Shopify CSV exports.
    """
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
        """Parse price from various formats: $19.99, 19,99, 19.99"""
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            try:
                return Decimal(v.replace(',', '').replace('$', '').strip())
            except InvalidOperation:
                raise ValueError('Invalid price format')
        return v


class ImportProductsRequest(BaseModel):
    """Request body for bulk product import. Max 1000 products per request."""
    products: List[ImportProductRow] = Field(..., min_length=1, max_length=1000)


class ImportProductsResponse(BaseModel):
    """Response for bulk product import showing success/failure counts."""
    created: int
    failed: int
    errors: List[str]


# ═══════════════════════════════════════════════════════════════════════════════
# CRUD ENDPOINTS
# Basic Create, Read, Update, Delete operations for products
# ═══════════════════════════════════════════════════════════════════════════════

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
    """
    Create a new product.
    
    - Sets current_price equal to base_price initially
    - Associates product with the authenticated user
    - Returns the created product with generated ID
    """
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
    """
    List all products for the current user with pagination.
    
    - Only returns products owned by the authenticated user
    - Supports page and page_size query parameters
    - Returns total count and total pages for pagination UI
    """
    # Count total products for this user
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
    """
    Get a specific product by ID.
    
    - Returns 404 if product doesn't exist
    - Returns 403 if user doesn't own the product
    """
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
    """
    Update a product (partial update).
    
    - Only updates fields that are provided in the request
    - Automatically updates the updated_at timestamp
    - Returns 404 if product doesn't exist
    - Returns 403 if user doesn't own the product
    """
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

    # Only update fields that were actually provided
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
    """
    Delete a product and ALL related data.
    
    This is a cascading delete that removes:
    - Recommendation outcomes (performance tracking)
    - Price recommendations (AI suggestions)
    - Pricing rules (user-defined automation rules)
    - Alerts (notifications)
    - Price history (historical prices)
    - Sentiment records (aggregated sentiment scores)
    - Social mentions (raw social media data)
    - Competitor product links (competitor mappings)
    
    Returns 404 if product doesn't exist.
    Returns 403 if user doesn't own the product.
    Returns 204 No Content on success.
    """
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

    try:
        # ═══════════════════════════════════════════════════════════════════
        # DELETE ALL RELATED RECORDS BEFORE DELETING PRODUCT
        # All these tables have foreign key references to products.id
        # We must delete them first to avoid FK constraint violations
        # ═══════════════════════════════════════════════════════════════════
        
        # Recommendation outcomes - tracks performance after price changes
        await session.execute(
            delete(RecommendationOutcome).where(RecommendationOutcome.product_id == product_id)
        )
        
        # Price recommendations - AI-generated pricing suggestions
        await session.execute(
            delete(PriceRecommendation).where(PriceRecommendation.product_id == product_id)
        )
        
        # Pricing rules - user-defined rules for automatic pricing
        await session.execute(
            delete(PricingRule).where(PricingRule.product_id == product_id)
        )
        
        # Alerts - notifications about price/sentiment changes
        await session.execute(
            delete(Alert).where(Alert.product_id == product_id)
        )
        
        # Price history - historical price change records
        await session.execute(
            delete(PriceHistory).where(PriceHistory.product_id == product_id)
        )
        
        # Sentiment records - aggregated sentiment scores
        await session.execute(
            delete(Sentiment).where(Sentiment.product_id == product_id)
        )
        
        # Social mentions - raw social media posts/comments
        await session.execute(
            delete(SocialMention).where(SocialMention.product_id == product_id)
        )
        
        # Competitor product links - mappings to competitor products
        await session.execute(
            delete(CompetitorProduct).where(CompetitorProduct.product_id == product_id)
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # NOW SAFE TO DELETE THE PRODUCT ITSELF
        # ═══════════════════════════════════════════════════════════════════
        await session.delete(product)
        await session.commit()
        
        logger.info(f"Successfully deleted product {product_id} and all related data")

    except Exception as e:
        await session.rollback()
        logger.error(f"Failed to delete product {product_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete product: {str(e)}",
        )

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# BULK IMPORT
# Import multiple products from CSV data (WooCommerce/Shopify compatible)
# ═══════════════════════════════════════════════════════════════════════════════

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
    
    Returns count of created/failed products and first 10 error messages.
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

    # Commit all successful products in one transaction
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


# ═══════════════════════════════════════════════════════════════════════════════
# AI PRICE SUGGESTION
# Get AI-powered price recommendations based on sentiment analysis
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/{product_id}/price-suggestion", response_model=PriceSuggestion)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def get_price_suggestion(
    request: Request,
    product_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get AI-powered price suggestion based on sentiment analysis.
    
    Analyzes all sentiment records for the product and calculates:
    - Average sentiment score
    - Mention volume
    - Suggested price based on sentiment multiplier
    - Confidence score
    - Reasoning for the suggestion
    
    Returns 404 if product doesn't exist.
    Returns 403 if user doesn't own the product.
    """
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

    # Fetch all sentiment records for this product
    statement = select(Sentiment).where(Sentiment.product_id == product_id)
    result = await session.execute(statement)
    sentiments = result.scalars().all()

    if sentiments:
        # Calculate aggregate sentiment from all records
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
        # No sentiment data - use neutral defaults
        sentiment_score = Decimal("0")
        mention_volume = 0

    # Generate price suggestion using pricing engine
    suggestion = pricing_engine.calculate_suggestion(
        product=product,
        sentiment_score=sentiment_score,
        mention_volume=mention_volume,
    )

    return suggestion

