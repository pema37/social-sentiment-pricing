# backend/api/v1/routes/__init__.py

"""
API v1 Routes

All route modules for the v1 API.
"""

from backend.api.v1.routes.health import router as health_router
from backend.api.v1.routes.auth import router as auth_router
from backend.api.v1.routes.users import router as users_router
from backend.api.v1.routes.products import router as products_router
from backend.api.v1.routes.sentiment import router as sentiment_router

# Phase 2: Competitor Routes
from backend.api.v1.routes.competitors import router as competitors_router


__all__ = [
    "health_router",
    "auth_router",
    "users_router",
    "products_router",
    "sentiment_router",
    "competitors_router",
]

