# backend/api/v1/routes/sentiment/__init__.py
"""
Sentiment API - Modular router combining all sentiment endpoints.
"""

from fastapi import APIRouter

from .analysis import router as analysis_router
from .retrieval import router as retrieval_router
from .tasks import router as tasks_router

router = APIRouter(prefix="/sentiment", tags=["Sentiment Analysis"])

router.include_router(analysis_router)
router.include_router(retrieval_router)
router.include_router(tasks_router)
