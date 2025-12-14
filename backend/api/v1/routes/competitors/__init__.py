# backend/api/v1/routes/competitors/__init__.py
"""
Competitors API - Modular router combining all competitor endpoints.
"""

from fastapi import APIRouter

from .crud import router as crud_router
from .products import router as products_router
from .scraping import router as scraping_router
from .analysis import router as analysis_router

router = APIRouter(prefix="/competitors", tags=["competitors"])

# Order matters: static routes before dynamic routes
router.include_router(products_router)   # /products/* routes first
router.include_router(analysis_router)   # /compare/*, /alerts routes
router.include_router(crud_router)       # Base CRUD (includes /{competitor_id})
router.include_router(scraping_router)   # Scraping routes
