# backend/api/v1/routes/products.py

from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from backend.db.session import get_session
from backend.models import User, Product, Sentiment
from backend.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductRead,
    PriceSuggestion,
)
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
def create_product(
    payload: ProductCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new product."""
    product = Product(
        user_id=current_user.id,
        name=payload.name,
        sku=payload.sku,
        description=payload.description,
        base_price=payload.base_price,
        current_price=payload.base_price,  # Start at base price
        min_price=payload.min_price,
        max_price=payload.max_price,
        sentiment_multiplier=payload.sentiment_multiplier,
        auto_pricing_enabled=payload.auto_pricing_enabled,
        keywords=payload.keywords,
    )

    session.add(product)
    session.commit()
    session.refresh(product)

    return product


@router.get("", response_model=List[ProductRead])
def list_products(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List all products for the current user."""
    statement = select(Product).where(Product.user_id == current_user.id)
    products = session.exec(statement).all()
    return products


@router.get("/{product_id}", response_model=ProductRead)
def get_product(
    product_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific product by ID."""
    product = session.get(Product, product_id)

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
def update_product(
    product_id: str,
    payload: ProductUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a product."""
    product = session.get(Product, product_id)

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

    # Update only provided fields
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)

    product.updated_at = datetime.utcnow()

    session.add(product)
    session.commit()
    session.refresh(product)

    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a product."""
    product = session.get(Product, product_id)

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

    session.delete(product)
    session.commit()

    return None


# ───────────────────────────── Price Suggestion ───────────────────────────── #

@router.get("/{product_id}/price-suggestion", response_model=PriceSuggestion)
def get_price_suggestion(
    product_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get AI-powered price suggestion based on sentiment analysis."""
    product = session.get(Product, product_id)

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

    # Get recent sentiments for this product
    statement = select(Sentiment).where(Sentiment.product_id == product_id)
    sentiments = session.exec(statement).all()

    # Calculate aggregate sentiment
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

    # Calculate price suggestion
    suggestion = pricing_engine.calculate_suggestion(
        product=product,
        sentiment_score=sentiment_score,
        mention_volume=mention_volume,
    )

    return suggestion


