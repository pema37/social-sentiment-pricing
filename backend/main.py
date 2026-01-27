# backend/main.py
"""
Social Sentiment Pricing API - Main Application Entry Point
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler # pyright: ignore[reportMissingImports]
from slowapi.errors import RateLimitExceeded # pyright: ignore[reportMissingImports]
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
    payments_router,
    trust_scoring_router,  # NEW: Bot/Manipulation detection
)
from api.v1.routes.support import router as support_router 
from api.v1.routes.market_trends import router as market_trends_router
from api.v1.routes.trend_analysis import router as trend_analysis_router
from api.v1.routes.diagnostic import router as diagnostic_router  # ADDED: Multi-platform diagnostic


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
    redirect_slashes=False,  
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
cors_origins = settings.cors_origins_list
# Handle wildcard - if "*" is in origins, allow all
if "*" in cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,  # Cannot use credentials with wildcard
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=r"https://.*\.vercel\.app", 
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
app.include_router(payments_router, prefix="/api/v1")
app.include_router(support_router, prefix="/api/v1")  
app.include_router(market_trends_router, prefix="/api/v1")
app.include_router(trend_analysis_router, prefix="/api/v1")  # AI Trend Analysis
app.include_router(trust_scoring_router, prefix="/api/v1")  # NEW: /api/v1/trust/*
app.include_router(diagnostic_router, prefix="/api/v1")  # ADDED: Multi-platform diagnostic


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


