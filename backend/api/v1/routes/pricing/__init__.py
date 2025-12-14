# backend/api/v1/routes/pricing/__init__.py
"""
Pricing API - Modular router combining all pricing endpoints.
"""

from fastapi import APIRouter

from .rules import router as rules_router
from .recommendations import router as recommendations_router
from .settings import router as settings_router
from .simulation import router as simulation_router
from .outcomes import router as outcomes_router

router = APIRouter(prefix="/pricing", tags=["pricing"])

# Include all sub-routers
router.include_router(rules_router)
router.include_router(recommendations_router)
router.include_router(settings_router)
router.include_router(simulation_router)
router.include_router(outcomes_router)
