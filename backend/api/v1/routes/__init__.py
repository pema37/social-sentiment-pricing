# backend/api/v1/routes/__init__.py

"""
API v1 Routes

All route modules for the v1 API.
"""

from api.v1.routes.health import router as health_router
from api.v1.routes.auth import router as auth_router
from api.v1.routes.users import router as users_router
from api.v1.routes.products import router as products_router
from api.v1.routes.sentiment import router as sentiment_router
from api.v1.routes.competitors import router as competitors_router
from api.v1.routes.alerts import router as alerts_router
from api.v1.routes.analytics import router as analytics_router
from api.v1.routes.integrations import router as integrations_router
from api.v1.routes.pricing import router as pricing_router
from api.v1.routes.webhooks import router as webhooks_router
from api.v1.routes.websockets import router as websocket_router
from api.v1.routes.payments import router as payments_router


__all__ = [
    "health_router",
    "auth_router",
    "users_router",
    "products_router",
    "sentiment_router",
    "competitors_router",
    "alerts_router",
    "analytics_router",
    "integrations_router",
    "pricing_router",
    "webhooks_router",
    "websocket_router",
    "payments_router",
]
