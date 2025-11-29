# backend/api/v1/routes/sentiment.py

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from backend.db.session import get_session
from backend.models import User, Product, Sentiment
from backend.schemas.sentiment import (
    SentimentAnalyzeRequest,
    SentimentBulkRequest,
    SentimentRead,
    SentimentScores,
    SentimentAnalyzeResponse,
    SentimentSummary,
)
from backend.api.v1.routes.auth import get_current_user
from backend.services.sentiment_analyzer import sentiment_analyzer

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


# ───────────────────────────── Analyze Endpoints ───────────────────────────── #

@router.post("/analyze", response_model=SentimentAnalyzeResponse)
def analyze_text(
    payload: SentimentAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Analyze sentiment of any text.
    Does NOT save to database - use for testing/preview.
    """
    result = sentiment_analyzer.analyze(payload.text)

    return SentimentAnalyzeResponse(
        text=payload.text,
        scores=SentimentScores(
            compound=result["compound"],
            positive=result["positive"],
            negative=result["negative"],
            neutral=result["neutral"],
        ),
        label=result["label"],
        saved=False,
    )


@router.post(
    "/analyze/{product_id}",
    response_model=SentimentAnalyzeResponse,
    status_code=status.HTTP_201_CREATED,
)
def analyze_and_save(
    product_id: str,
    payload: SentimentAnalyzeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze sentiment and save to database for a specific product.
    """
    # Verify product exists and belongs to user
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

    # Analyze the text
    result = sentiment_analyzer.analyze(payload.text)

    # Save to database
    sentiment = Sentiment(
        product_id=product_id,
        source=payload.source,
        raw_text=payload.text,
        compound_score=result["compound"],
        positive_score=result["positive"],
        negative_score=result["negative"],
        neutral_score=result["neutral"],
        author=payload.author,
        url=payload.url,
    )

    session.add(sentiment)
    session.commit()
    session.refresh(sentiment)

    return SentimentAnalyzeResponse(
        text=payload.text,
        scores=SentimentScores(
            compound=result["compound"],
            positive=result["positive"],
            negative=result["negative"],
            neutral=result["neutral"],
        ),
        label=result["label"],
        saved=True,
        sentiment_id=sentiment.id,
    )


@router.post(
    "/analyze/{product_id}/bulk",
    response_model=List[SentimentAnalyzeResponse],
    status_code=status.HTTP_201_CREATED,
)
def analyze_bulk(
    product_id: str,
    payload: SentimentBulkRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze and save multiple texts at once for a product.
    """
    # Verify product exists and belongs to user
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

    responses = []

    for item in payload.items:
        # Analyze
        result = sentiment_analyzer.analyze(item.text)

        # Save
        sentiment = Sentiment(
            product_id=product_id,
            source=item.source,
            raw_text=item.text,
            compound_score=result["compound"],
            positive_score=result["positive"],
            negative_score=result["negative"],
            neutral_score=result["neutral"],
            author=item.author,
            url=item.url,
        )

        session.add(sentiment)
        session.flush()  # Get ID without committing

        responses.append(
            SentimentAnalyzeResponse(
                text=item.text,
                scores=SentimentScores(
                    compound=result["compound"],
                    positive=result["positive"],
                    negative=result["negative"],
                    neutral=result["neutral"],
                ),
                label=result["label"],
                saved=True,
                sentiment_id=sentiment.id,
            )
        )

    session.commit()

    return responses


# ───────────────────────────── Read Endpoints ───────────────────────────── #

@router.get("/product/{product_id}", response_model=List[SentimentRead])
def list_sentiments(
    product_id: str,
    limit: int = Query(default=50, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get all sentiment records for a product."""
    # Verify product exists and belongs to user
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

    statement = (
        select(Sentiment)
        .where(Sentiment.product_id == product_id)
        .order_by(Sentiment.analyzed_at.desc())
        .limit(limit)
    )
    sentiments = session.exec(statement).all()

    return sentiments


@router.get("/product/{product_id}/summary", response_model=SentimentSummary)
def get_sentiment_summary(
    product_id: str,
    days: int = Query(default=7, ge=1, le=90),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated sentiment summary for a product."""
    # Verify product exists and belongs to user
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

    # Get sentiments from the specified period
    period_start = datetime.utcnow() - timedelta(days=days)
    period_end = datetime.utcnow()

    statement = (
        select(Sentiment)
        .where(Sentiment.product_id == product_id)
        .where(Sentiment.analyzed_at >= period_start)
    )
    sentiments = session.exec(statement).all()

    # Calculate summary
    if not sentiments:
        return SentimentSummary(
            product_id=product_id,
            total_mentions=0,
            average_compound=Decimal("0"),
            positive_count=0,
            negative_count=0,
            neutral_count=0,
            trend="stable",
            period_start=period_start,
            period_end=period_end,
        )

    # Build sentiment data for aggregation
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

    # Determine trend based on recent vs older sentiments
    mid_point = len(sentiments) // 2
    if mid_point > 0:
        recent = sentiments[:mid_point]
        older = sentiments[mid_point:]

        recent_avg = sum(s.compound_score for s in recent) / len(recent)
        older_avg = sum(s.compound_score for s in older) / len(older)

        if recent_avg > older_avg + Decimal("0.1"):
            trend = "rising"
        elif recent_avg < older_avg - Decimal("0.1"):
            trend = "falling"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return SentimentSummary(
        product_id=product_id,
        total_mentions=aggregate["total_count"],
        average_compound=aggregate["average_compound"],
        positive_count=aggregate["positive_count"],
        negative_count=aggregate["negative_count"],
        neutral_count=aggregate["neutral_count"],
        trend=trend,
        period_start=period_start,
        period_end=period_end,
    )


@router.delete("/{sentiment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sentiment(
    sentiment_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a sentiment record."""
    sentiment = session.get(Sentiment, sentiment_id)

    if not sentiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sentiment not found",
        )

    # Verify the sentiment belongs to a product owned by the user
    product = session.get(Product, sentiment.product_id)

    if not product or product.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this sentiment",
        )

    session.delete(sentiment)
    session.commit()

    return None

