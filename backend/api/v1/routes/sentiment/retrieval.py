# backend/api/v1/routes/sentiment/retrieval.py
"""Sentiment retrieval endpoints."""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from db.session import get_session
from core.security import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT
from models import Sentiment, SocialMention, User
from schemas.sentiment import (
    SentimentResponse,
    SentimentSummary,
    SocialMentionResponse,
)
from schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


@router.get("/{sentiment_id}", response_model=SentimentResponse)
async def get_sentiment(
    request: Request,
    sentiment_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific sentiment record by ID."""
    result = await session.execute(
        select(Sentiment).where(Sentiment.id == sentiment_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Sentiment record not found")
    
    return SentimentResponse(
        sentiment_id=record.id,
        sentiment_score=record.sentiment_score,
        sentiment_label=record.sentiment_label,
        confidence=record.confidence,
        emotions=record.emotions,
    )


@router.get("/product/{product_id}", response_model=PaginatedResponse[SentimentResponse])
async def get_product_sentiments(
    request: Request,
    product_id: UUID,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get sentiment history for a product."""
    query = select(Sentiment).where(Sentiment.product_id == product_id)
    
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()
    
    query = query.order_by(Sentiment.analyzed_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    
    result = await session.execute(query)
    records = list(result.scalars().all())
    
    items = [
        SentimentResponse(
            sentiment_id=r.id,
            sentiment_score=r.sentiment_score,
            sentiment_label=r.sentiment_label,
            confidence=r.confidence,
            emotions=r.emotions,
        )
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
    result = await session.execute(
        select(Sentiment).where(Sentiment.product_id == product_id)
    )
    records = result.scalars().all()
    
    if not records:
        raise HTTPException(status_code=404, detail="No sentiment data found")
    
    scores = [r.sentiment_score for r in records]
    avg_score = sum(scores) / len(scores)
    
    label_counts = {}
    for r in records:
        label_counts[r.sentiment_label] = label_counts.get(r.sentiment_label, 0) + 1
    
    return SentimentSummary(
        product_id=product_id,
        total_records=len(records),
        average_score=avg_score,
        label_distribution=label_counts,
    )


@router.delete("/{sentiment_id}")
@limiter.limit(WRITE_RATE_LIMIT)
async def delete_sentiment(
    request: Request,
    sentiment_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete a sentiment record."""
    result = await session.execute(
        select(Sentiment).where(Sentiment.id == sentiment_id)
    )
    record = result.scalar_one_or_none()
    
    if not record:
        raise HTTPException(status_code=404, detail="Sentiment record not found")
    
    await session.delete(record)
    await session.commit()
    
    return {"status": "deleted", "sentiment_id": str(sentiment_id)}


@router.get("/mentions/{product_id}", response_model=PaginatedResponse[SocialMentionResponse])
async def get_product_mentions(
    request: Request,
    product_id: UUID,
    processed: Optional[bool] = Query(default=None),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get social mentions for a product."""
    query = select(SocialMention).where(SocialMention.product_id == product_id)
    
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
