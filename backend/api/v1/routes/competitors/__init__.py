# backend/api/v1/routes/competitors/__init__.py
"""
Competitors API - Modular router combining all competitor endpoints.
"""

from fastapi import APIRouter

from .analysis import router as analysis_router
from .crud import router as crud_router
from .matching import router as matching_router  # NEW: Auto-matching
from .products import router as products_router
from .scraping import router as scraping_router

router = APIRouter(prefix="/competitors", tags=["competitors"])

# Order matters: static routes before dynamic routes
router.include_router(matching_router)  # NEW: /match/* routes (auto URL matching)
router.include_router(products_router)  # /products/* routes
router.include_router(analysis_router)  # /compare/*, /alerts routes
router.include_router(crud_router)  # Base CRUD (includes /{competitor_id})
router.include_router(scraping_router)  # Scraping routes
