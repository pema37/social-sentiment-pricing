# backend/api/v1/routes/alerts/__init__.py
"""
Alerts API - Modular router combining all alert endpoints.
"""

from fastapi import APIRouter

from .configurations import router as configurations_router
from .management import router as management_router

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Configurations first (static paths), then management (includes dynamic paths)
router.include_router(configurations_router)
router.include_router(management_router)
