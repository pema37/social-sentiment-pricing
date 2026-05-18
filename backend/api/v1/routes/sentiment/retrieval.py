# backend/api/v1/routes/sentiment/retrieval.py
"""Sentiment retrieval endpoints."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import WRITE_RATE_LIMIT, limiter
from db.session import get_session
from models import Sentiment, SocialMention, User
from models.product import Product
from schemas.common import PaginatedResponse, PaginationParams
from schemas.sentiment import (
    SentimentResponse,
    SentimentSummary,
    SocialMentionResponse,
)

router = APIRouter()


def _compound_to_label(compound: Decimal) -> str:
    """Map a VADER compound score to a sentiment label using standard thresholds."""
    if compound >= Decimal("0.05"):
        return "positive"
    if compound <= Decimal("-0.05"):
        return "negative"
    return "neutral"


async def _verify_product_ownership(
    product_id: UUID, user_id: UUID, session: AsyncSession
) -> Product:
    """Verify the product belongs to the current user."""
    result = await session.execute(
        select(Product).where(Product.id == product_id, Product.user_id == user_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/{sentiment_id}", response_model=SentimentResponse)
async def get_sentiment(
    request: Request,
    sentiment_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific sentiment record by ID."""
    result = await session.execute(
        select(Sentiment)
        .join(Product, Sentiment.product_id == Product.id)
        .where(Sentiment.id == sentiment_id, Product.user_id == current_user.id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Sentiment record not found")

    return SentimentResponse.model_validate(record, from_attributes=True)


@router.get("/product/{product_id}", response_model=PaginatedResponse[SentimentResponse])
async def get_product_sentiments(
    request: Request,
    product_id: UUID,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get sentiment history for a product."""
    await _verify_product_ownership(product_id, current_user.id, session)

    query = select(Sentiment).where(Sentiment.product_id == product_id)

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    query = query.order_by(Sentiment.analyzed_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)

    result = await session.execute(query)
    records = list(result.scalars().all())

    items = [
        SentimentResponse.model_validate(r, from_attributes=True)
        for r in records
    ]

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/product/{product_id}/summary", response_model=SentimentSummary)
async def get_product_sentiment_summary(
    request: Request,
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get aggregated sentiment summary for a product."""
    await _verify_product_ownership(product_id, current_user.id, session)

    result = await session.execute(select(Sentiment).where(Sentiment.product_id == product_id))
    records = list(result.scalars().all())

    if not records:
        raise HTTPException(status_code=404, detail="No sentiment data found")

    scores = [r.compound_score for r in records]
    avg_score = sum(scores) / len(scores)

    label_counts: dict[str, int] = {"positive": 0, "negative": 0, "neutral": 0}
    for r in records:
        label_counts[_compound_to_label(r.compound_score)] += 1

    return SentimentSummary(
        product_id=product_id,
        total_records=len(records),
        average_compound=avg_score,
        average_score=avg_score,
        positive_count=label_counts["positive"],
        negative_count=label_counts["negative"],
        neutral_count=label_counts["neutral"],
        label_distribution=label_counts,
    )


@router.delete("/{sentiment_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_sentiment(
    request: Request,
    sentiment_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a sentiment record."""
    result = await session.execute(
        select(Sentiment)
        .join(Product, Sentiment.product_id == Product.id)
        .where(Sentiment.id == sentiment_id, Product.user_id == current_user.id)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(status_code=404, detail="Sentiment record not found")

    await session.delete(record)
    await session.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/mentions/{product_id}", response_model=PaginatedResponse[SocialMentionResponse])
async def get_product_mentions(
    request: Request,
    product_id: UUID,
    processed: bool | None = Query(default=None),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get social mentions for a product."""
    await _verify_product_ownership(product_id, current_user.id, session)

    query = select(SocialMention).where(
        SocialMention.product_id == product_id,
        SocialMention.user_id == current_user.id,
    )

    if processed is not None:
        query = query.where(SocialMention.processed == processed)

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    query = query.order_by(SocialMention.collected_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)

    result = await session.execute(query)
    items = list(result.scalars().all())

    total_pages = (total + pagination.page_size - 1) // pagination.page_size

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )



