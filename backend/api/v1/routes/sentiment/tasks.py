# backend/api/v1/routes/sentiment/tasks.py
"""Background task endpoints (Celery)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from celery.result import AsyncResult

from db.session import get_session
from core.security import get_current_user
from core.rate_limit import limiter, BULK_RATE_LIMIT
from models import Product, User
from workers.tasks.ingestion_tasks import fetch_for_product, process_pending_mentions

router = APIRouter()


@router.post("/fetch/{product_id}")
@limiter.limit(BULK_RATE_LIMIT)
async def fetch_product_mentions(
    request: Request,
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Queue a background task to fetch social mentions for a product.
    Returns a task_id to check status.
    """
    result = await session.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    task = fetch_for_product.delay(str(product_id))
    
    return {
        "status": "queued",
        "task_id": task.id,
        "product_id": str(product_id),
        "message": "Fetch task has been queued. Use task_id to check status.",
        "check_status_url": f"/api/v1/sentiment/tasks/{task.id}",
    }


@router.post("/process")
@limiter.limit(BULK_RATE_LIMIT)
async def process_mentions(
    request: Request,
    batch_size: int = 100,
    current_user: User = Depends(get_current_user),
):
    """
    Queue a background task to process pending mentions through sentiment analysis.
    Returns a task_id to check status.
    """
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
    request: Request,
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Check the status of a background task.
    
    States:
    - PENDING: Task is waiting to be picked up
    - STARTED: Task has started
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
