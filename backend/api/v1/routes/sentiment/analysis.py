# backend/api/v1/routes/sentiment/analysis.py
"""Sentiment analysis endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_session
from core.security import get_current_user
from core.rate_limit import limiter, ANALYSIS_RATE_LIMIT, BULK_RATE_LIMIT
from models import Sentiment, Product, User
from schemas.sentiment import (
    SentimentAnalyzeRequest,
    SentimentResponse,
    SentimentBulkRequest,
)
from services.sentiment_analyzer import SentimentAnalyzer

router = APIRouter()


@router.post("/analyze", response_model=SentimentResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def analyze_text(
    request: Request,
    payload: SentimentAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Analyze sentiment of provided text."""
    analyzer = SentimentAnalyzer()
    result = await analyzer.analyze(payload.text)
    
    return SentimentResponse(
        text=payload.text,
        sentiment_score=result.score,
        sentiment_label=result.label,
        confidence=result.confidence,
        emotions=result.emotions,
    )


@router.post("/analyze/{product_id}", response_model=SentimentResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def analyze_and_save(
    request: Request,
    product_id: UUID,
    payload: SentimentAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Analyze sentiment and save to database linked to a product."""
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    analyzer = SentimentAnalyzer()
    analysis = await analyzer.analyze(payload.text)
    
    sentiment_record = Sentiment(
        product_id=product_id,
        source=payload.source or "manual",
        raw_text=payload.text,
        compound_score=analysis.score,
        positive_score=analysis.emotions["positive"],
        negative_score=analysis.emotions["negative"],
        neutral_score=analysis.emotions["neutral"],
        author=payload.author,
        url=payload.url,
    )
    session.add(sentiment_record)
    await session.commit()
    await session.refresh(sentiment_record)
    
    return SentimentResponse(
        sentiment_id=sentiment_record.id,
        text=payload.text,
        sentiment_score=analysis.score,
        sentiment_label=analysis.label,
        confidence=analysis.confidence,
        emotions=analysis.emotions,
    )


@router.post("/analyze/{product_id}/bulk")
@limiter.limit(BULK_RATE_LIMIT)
async def analyze_bulk(
    request: Request,
    product_id: UUID,
    payload: SentimentBulkRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Analyze multiple texts and save all to database."""
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    analyzer = SentimentAnalyzer()
    results = []
    
    for item in payload.items:
        analysis = await analyzer.analyze(item.text)
        
        sentiment_record = Sentiment(
            product_id=product_id,
            organization_id=product.organization_id,
            sentiment_score=analysis.score,
            sentiment_label=analysis.label,
            confidence=analysis.confidence,
            emotions=analysis.emotions,
        )
        session.add(sentiment_record)
        await session.flush()
        
        results.append({
            "sentiment_id": str(sentiment_record.id),
            "text": item.text,
            "sentiment_score": analysis.score,
            "sentiment_label": analysis.label,
            "confidence": analysis.confidence,
        })
    
    await session.commit()
    return {"results": results, "count": len(results)}
