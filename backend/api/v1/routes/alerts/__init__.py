# backend/api/v1/routes/alerts/__init__.py
"""
Alerts API - Modular router combining all alert endpoints.
"""

from fastapi import APIRouter

from .configurations import router as configurations_router
from .crisis_detection import router as crisis_detection_router
from .management import router as management_router

router = APIRouter(prefix="/alerts", tags=["alerts"])

# Order matters! Static routes first, then dynamic routes
# 1. Configurations (static paths like /configurations)
router.include_router(configurations_router)

# 2. Crisis detection (static path /crisis-detection)
router.include_router(crisis_detection_router)

# 3. Management last (includes dynamic /{alert_id} routes)
router.include_router(management_router)

