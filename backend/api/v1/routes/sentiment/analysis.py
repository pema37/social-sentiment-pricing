# backend/api/v1/routes/sentiment/analysis.py
"""Sentiment analysis endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Query
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
from services.openai_sentiment import openai_sentiment_analyzer

router = APIRouter()


async def get_sentiment_result(text: str, use_ai: bool = False):
    """Get sentiment using VADER or OpenAI."""
    if use_ai and openai_sentiment_analyzer.is_available():
        result = await openai_sentiment_analyzer.analyze(text)
        return {
            "score": float(result["compound"]),
            "label": result["label"],
            "confidence": float(result["confidence"]),
            "emotions": {
                "positive": float(result["positive"]),
                "negative": float(result["negative"]),
                "neutral": float(result["neutral"]),
            },
            "topics": result.get("topics", []),
            "is_sarcastic": result.get("is_sarcastic", False),
            "ai_powered": True,
        }
    else:
        analyzer = SentimentAnalyzer()
        result = await analyzer.analyze(text)
        return {
            "score": result.score,
            "label": result.label,
            "confidence": result.confidence,
            "emotions": result.emotions,
            "topics": [],
            "is_sarcastic": False,
            "ai_powered": False,
        }


@router.post("/analyze", response_model=SentimentResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def analyze_text(
    request: Request,
    payload: SentimentAnalyzeRequest,
    use_ai: bool = Query(False, description="Use OpenAI GPT-4o-mini for analysis"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Analyze sentiment of provided text.
    
    Set use_ai=true to use OpenAI GPT-4o-mini for more accurate analysis
    including sarcasm detection, topic extraction, and nuanced understanding.
    """
    result = await get_sentiment_result(payload.text, use_ai)
    
    return SentimentResponse(
        text=payload.text,
        sentiment_score=result["score"],
        sentiment_label=result["label"],
        confidence=result["confidence"],
        emotions=result["emotions"],
        topics=result.get("topics", []),
        is_sarcastic=result.get("is_sarcastic", False),
        ai_powered=result.get("ai_powered", False),
    )


@router.post("/analyze/{product_id}", response_model=SentimentResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def analyze_and_save(
    request: Request,
    product_id: UUID,
    payload: SentimentAnalyzeRequest,
    use_ai: bool = Query(False, description="Use OpenAI GPT-4o-mini for analysis"),
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
    
    analysis = await get_sentiment_result(payload.text, use_ai)
    
    sentiment_record = Sentiment(
        product_id=product_id,
        source=payload.source or ("openai" if analysis["ai_powered"] else "manual"),
        raw_text=payload.text,
        compound_score=analysis["score"],
        positive_score=analysis["emotions"]["positive"],
        negative_score=analysis["emotions"]["negative"],
        neutral_score=analysis["emotions"]["neutral"],
        author=payload.author,
        url=payload.url,
    )
    session.add(sentiment_record)
    await session.commit()
    await session.refresh(sentiment_record)
    
    return SentimentResponse(
        sentiment_id=sentiment_record.id,
        text=payload.text,
        sentiment_score=analysis["score"],
        sentiment_label=analysis["label"],
        confidence=analysis["confidence"],
        emotions=analysis["emotions"],
        topics=analysis.get("topics", []),
        is_sarcastic=analysis.get("is_sarcastic", False),
        ai_powered=analysis.get("ai_powered", False),
    )


@router.post("/analyze/{product_id}/bulk")
@limiter.limit(BULK_RATE_LIMIT)
async def analyze_bulk(
    request: Request,
    product_id: UUID,
    payload: SentimentBulkRequest,
    use_ai: bool = Query(False, description="Use OpenAI GPT-4o-mini for analysis"),
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
    
    results = []
    
    for item in payload.items:
        analysis = await get_sentiment_result(item.text, use_ai)
        
        sentiment_record = Sentiment(
            product_id=product_id,
            source="openai" if analysis["ai_powered"] else "manual",
            raw_text=item.text,
            compound_score=analysis["score"],
            positive_score=analysis["emotions"]["positive"],
            negative_score=analysis["emotions"]["negative"],
            neutral_score=analysis["emotions"]["neutral"],
        )
        session.add(sentiment_record)
        await session.flush()
        
        results.append({
            "sentiment_id": str(sentiment_record.id),
            "text": item.text,
            "sentiment_score": analysis["score"],
            "sentiment_label": analysis["label"],
            "confidence": analysis["confidence"],
            "ai_powered": analysis["ai_powered"],
        })
    
    await session.commit()
    return {"results": results, "count": len(results), "ai_powered": use_ai}


@router.get("/ai-status")
async def ai_status(current_user: User = Depends(get_current_user)):
    """Check if AI-powered sentiment analysis is available."""
    return {
        "openai_available": openai_sentiment_analyzer.is_available(),
        "model": "gpt-4o-mini" if openai_sentiment_analyzer.is_available() else None,
        "features": ["sarcasm_detection", "topic_extraction", "nuanced_analysis"] if openai_sentiment_analyzer.is_available() else [],
    }
