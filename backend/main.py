# backend/main.py
"""
Social Sentiment Pricing API - Main Application Entry Point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from core.logging import configure_logging, get_logger
from core.sentry import configure_sentry
from core.rate_limit import limiter
from core.middleware import RequestLoggingMiddleware
from core.exception_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    database_exception_handler,
)

# Configure logging first
configure_logging()
logger = get_logger(__name__)

# Configure Sentry
configure_sentry()

# Import routers after logging is configured
from api.v1.routes import (
    auth_router,
    users_router,
    products_router,
    pricing_router,
    sentiment_router,
    competitors_router,
    alerts_router,
    integrations_router,
    analytics_router,
    webhooks_router,
    websocket_router,
    health_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info(
        "Application starting",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
    yield
    logger.info("Application shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-ID"],
)

# Health check routes (no prefix)
app.include_router(health_router)

# API routes
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(pricing_router, prefix="/api/v1")
app.include_router(sentiment_router, prefix="/api/v1")
app.include_router(competitors_router, prefix="/api/v1")
app.include_router(alerts_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }
