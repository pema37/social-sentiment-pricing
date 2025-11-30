# backend/api/v1/__init__.py

"""
API v1 Router

Aggregates all v1 route modules into a single router.
"""

from fastapi import APIRouter

from backend.api.v1.routes import (
    health_router,
    auth_router,
    users_router,
    products_router,
    sentiment_router,
    competitors_router,
)

api_router = APIRouter()

# Register all routes
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(products_router)
api_router.include_router(sentiment_router)

# Phase 2: Competitor routes
api_router.include_router(competitors_router)

