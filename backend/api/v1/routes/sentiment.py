# backend/api/v1/routes/sentiment.py

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select
from celery.result import AsyncResult  

from backend.db.session import get_session
from backend.models import Sentiment, Product, SocialMention
from backend.schemas.sentiment import (
    SentimentAnalyzeRequest,
    SentimentResponse,
    SentimentBulkRequest,
    SentimentSummary,
    SocialMentionResponse,
)
from backend.schemas.common import PaginatedResponse, PaginationParams
from backend.services.sentiment_analyzer import SentimentAnalyzer
from backend.core.security import get_current_user
from backend.models import User

# Import Celery tasks
from backend.workers.tasks.ingestion_tasks import fetch_for_product, process_pending_mentions

router = APIRouter(prefix="/sentiment", tags=["Sentiment Analysis"])


# =============================================================================
# SENTIMENT ANALYSIS ENDPOINTS (sync - immediate response)
# =============================================================================

@router.post("/analyze", response_model=SentimentResponse)
async def analyze_text(
    request: SentimentAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Analyze sentiment of provided text."""
    analyzer = SentimentAnalyzer()
    result = await analyzer.analyze(request.text)
    
    return SentimentResponse(
        text=request.text,
        sentiment_score=result.score,
        sentiment_label=result.label,
        confidence=result.confidence,
        emotions=result.emotions,
    )


@router.post("/analyze/{product_id}", response_model=SentimentResponse)
async def analyze_and_save(
    product_id: UUID,
    request: SentimentAnalyzeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Analyze sentiment and save to database linked to a product."""
    # Verify product exists
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    analyzer = SentimentAnalyzer()
    analysis = await analyzer.analyze(request.text)
    
    # Save to database
    sentiment_record = Sentiment(
        product_id=product_id,
        source=request.source or "manual",
        raw_text=request.text,
        compound_score=analysis.score,
        positive_score=analysis.emotions["positive"],
        negative_score=analysis.emotions["negative"],
        neutral_score=analysis.emotions["neutral"],
        author=request.author,
        url=request.url,
    )
    session.add(sentiment_record)
    await session.commit()
    await session.refresh(sentiment_record)
    
    return SentimentResponse(
        sentiment_id=sentiment_record.id,
        text=request.text,
        sentiment_score=analysis.score,
        sentiment_label=analysis.label,
        confidence=analysis.confidence,
        emotions=analysis.emotions,
    )


@router.post("/analyze/{product_id}/bulk")
async def analyze_bulk(
    product_id: UUID,
    request: SentimentBulkRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Analyze multiple texts and save all to database."""
    # Verify product exists
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    analyzer = SentimentAnalyzer()
    results = []
    
    for item in request.items:
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
        await session.flush()  # Get the ID
        
        results.append({
            "sentiment_id": str(sentiment_record.id),
            "text": item.text,
            "sentiment_score": analysis.score,
            "sentiment_label": analysis.label,
            "confidence": analysis.confidence,
        })
    
    await session.commit()
    return {"results": results, "count": len(results)}


# =============================================================================
# SENTIMENT RETRIEVAL ENDPOINTS
# =============================================================================

@router.get("/{sentiment_id}", response_model=SentimentResponse)
async def get_sentiment(
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
    product_id: UUID,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get sentiment history for a product."""
    # Build base query
    query = select(Sentiment).where(Sentiment.product_id == product_id)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()
    
    # Paginate
    query = query.order_by(Sentiment.analyzed_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    
    result = await session.execute(query)
    records = list(result.scalars().all())
    
    # Convert to response objects
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
    
    # Count by label
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
async def delete_sentiment(
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
    product_id: UUID,
    processed: Optional[bool] = Query(default=None),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get social mentions for a product."""
    # Build base query
    query = select(SocialMention).where(SocialMention.product_id == product_id)
    
    if processed is not None:
        query = query.where(SocialMention.processed == processed)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()
    
    # Paginate
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


# =============================================================================
# BACKGROUND TASK ENDPOINTS (async via Celery - returns task_id)
# =============================================================================

@router.post("/fetch/{product_id}")
async def fetch_product_mentions(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Queue a background task to fetch social mentions for a product.
    Returns a task_id to check status.
    """
    # Verify product exists
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Queue the task with .delay() - returns immediately
    task = fetch_for_product.delay(str(product_id))
    
    return {
        "status": "queued",
        "task_id": task.id,
        "product_id": str(product_id),
        "message": "Fetch task has been queued. Use task_id to check status.",
        "check_status_url": f"/api/v1/sentiment/tasks/{task.id}",
    }


@router.post("/process")
async def process_mentions(
    batch_size: int = 100,
    current_user: User = Depends(get_current_user),
):
    """
    Queue a background task to process pending mentions through sentiment analysis.
    Returns a task_id to check status.
    """
    # Queue the task with .delay() - returns immediately
    task = process_pending_mentions.delay(batch_size)
    
    return {
        "status": "queued",
        "task_id": task.id,
        "batch_size": batch_size,
        "message": "Process task has been queued. Use task_id to check status.",
        "check_status_url": f"/api/v1/sentiment/tasks/{task.id}",
    }


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check the status of a background task.
    
    States:
    - PENDING: Task is waiting to be picked up
    - STARTED: Task has started (requires track_started=True on task)
    - LOADING_PRODUCT, FETCHING, SAVING, PROCESSING: Custom progress states
    - SUCCESS: Task completed successfully
    - FAILURE: Task failed
    """
    result = AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": result.status,
    }
    
    if result.status == "PENDING":
        response["message"] = "Task is waiting to be picked up by a worker"
    
    elif result.status == "STARTED":
        response["message"] = "Task has started"
        if result.info:
            response["progress"] = result.info
    
    elif result.status in ["LOADING_PRODUCT", "FETCHING", "SAVING", "PROCESSING", "LOADING"]:
        response["message"] = f"Task is {result.status.lower()}"
        if result.info:
            response["progress"] = result.info
    
    elif result.status == "SUCCESS":
        response["message"] = "Task completed successfully"
        response["result"] = result.result
    
    elif result.status == "FAILURE":
        response["message"] = "Task failed"
        response["error"] = str(result.result) if result.result else "Unknown error"
    
    return response
