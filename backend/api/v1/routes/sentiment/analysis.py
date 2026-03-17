# backend/api/v1/routes/sentiment/analysis.py
"""Sentiment analysis endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import ANALYSIS_RATE_LIMIT, BULK_RATE_LIMIT, limiter
from db.session import get_session
from models import Product, Sentiment, User
from schemas.sentiment import (
    SentimentAnalyzeRequest,
    SentimentBulkRequest,
    SentimentResponse,
)

# Changed: Use hybrid analyzer (Gemini primary, OpenAI fallback) instead of OpenAI-only
from services.hybrid_sentiment_analyzer import hybrid_sentiment_analyzer
from services.sentiment_analyzer import SentimentAnalyzer

router = APIRouter()


async def get_sentiment_result(text: str, use_ai: bool = False):
    """Get sentiment using VADER, Gemini, or OpenAI (hybrid approach)."""
    if use_ai:
        # Use hybrid analyzer: Gemini (primary) → OpenAI (fallback) → VADER (baseline)
        result = await hybrid_sentiment_analyzer.analyze(text, use_ai=True)
        return {
            "score": float(result.compound),
            "label": result.label,
            "confidence": float(result.confidence),
            "emotions": {
                "positive": float(result.positive),
                "negative": float(result.negative),
                "neutral": float(result.neutral),
            },
            "topics": result.topics,
            "is_sarcastic": result.is_sarcastic,
            "ai_powered": "gemini" in result.sources_used or "openai" in result.sources_used,
            "sources_used": result.sources_used,
        }
    else:
        # VADER-only for speed (no AI)
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
            "sources_used": ["vader"],
        }


@router.post("/analyze", response_model=SentimentResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def analyze_text(
    request: Request,
    payload: SentimentAnalyzeRequest,
    use_ai: bool = Query(False, description="Use AI (Gemini/OpenAI) for enhanced analysis"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Analyze sentiment of provided text.

    Set use_ai=true to use AI-powered analysis (Gemini primary, OpenAI fallback)
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
    use_ai: bool = Query(False, description="Use AI (Gemini/OpenAI) for enhanced analysis"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Analyze sentiment and save to database linked to a product."""
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    analysis = await get_sentiment_result(payload.text, use_ai)

    # Determine source based on which AI was actually used
    sources = analysis.get("sources_used", [])
    if "gemini" in sources:
        source = "gemini"
    elif "openai" in sources:
        source = "openai"
    elif payload.source:
        source = payload.source
    else:
        source = "vader"

    sentiment_record = Sentiment(
        product_id=product_id,
        source=source,
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
    use_ai: bool = Query(False, description="Use AI (Gemini/OpenAI) for enhanced analysis"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Analyze multiple texts and save all to database."""
    result = await session.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    results = []

    for item in payload.items:
        analysis = await get_sentiment_result(item.text, use_ai)

        # Determine source
        sources = analysis.get("sources_used", [])
        if "gemini" in sources:
            source = "gemini"
        elif "openai" in sources:
            source = "openai"
        else:
            source = "vader"

        sentiment_record = Sentiment(
            product_id=product_id,
            source=source,
            raw_text=item.text,
            compound_score=analysis["score"],
            positive_score=analysis["emotions"]["positive"],
            negative_score=analysis["emotions"]["negative"],
            neutral_score=analysis["emotions"]["neutral"],
        )
        session.add(sentiment_record)
        await session.flush()

        results.append(
            {
                "sentiment_id": str(sentiment_record.id),
                "text": item.text,
                "sentiment_score": analysis["score"],
                "sentiment_label": analysis["label"],
                "confidence": analysis["confidence"],
                "ai_powered": analysis["ai_powered"],
                "sources_used": analysis.get("sources_used", []),
            }
        )

    await session.commit()
    return {"results": results, "count": len(results), "ai_powered": use_ai}


@router.get("/ai-status")
async def ai_status(current_user: User = Depends(get_current_user)):
    """Check if AI-powered sentiment analysis is available."""
    available_sources = hybrid_sentiment_analyzer.get_available_sources()

    # Determine primary provider
    if "gemini" in available_sources:
        primary_model = "gemini-2.0-flash-exp"
        primary_provider = "gemini"
    elif "openai" in available_sources:
        primary_model = "gpt-4o-mini"
        primary_provider = "openai"
    else:
        primary_model = "vader"
        primary_provider = "vader"

    return {
        "ai_available": "gemini" in available_sources or "openai" in available_sources,
        "available_sources": available_sources,
        "primary_provider": primary_provider,
        "primary_model": primary_model,
        "features": ["sarcasm_detection", "topic_extraction", "nuanced_analysis"]
        if primary_provider != "vader"
        else [],
        # Backward compatibility
        "openai_available": "openai" in available_sources,
        "gemini_available": "gemini" in available_sources,
    }
