# backend/main.py
"""
ActualPrice API - Main Application Entry Point

PATCHED (2025-01-28): Fixed Bug #3 - Rate limit now returns HTTP 429
- Moved RateLimitExceeded handler BEFORE generic Exception handler
- Using custom handler that explicitly returns 429 with Retry-After header

NEW (2025-01-29): Added Visual Pricing Intelligence demo for Gemini 3 Hackathon
NEW (2025-01-30): Added Crisis Detection, Launch Detection, Market Trends Visual demos
FIXED (2025-01-30): Added products_import router - CSV import was returning 404
NEW (2026-02-18): Phase 5 — Intelligence Environment dashboard routes
FIXED (2026-02-19): Made x402 and autonomous pipeline imports conditional
FIXED (2026-03-29): AP-031 — removed bare os.getenv() call, use settings.PAY_TO_ADDRESS
FIXED (2026-03-29): AP-032 — WebSocket heartbeat started in lifespan to prune
                    stale connections every 30s.
"""

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError

from core.config import settings
from core.logging import configure_logging, get_logger
from core.sentry import configure_sentry
from core.rate_limit import limiter, rate_limit_exceeded_handler
from core.middleware import RequestLoggingMiddleware
from core.exception_handlers import (
    http_exception_handler,
    unhandled_exception_handler,
    database_exception_handler,
)

# ── Optional: x402 import ─────────────────────────────────
try:
    from fastapi_x402 import init_x402
    HAS_X402 = True
except ImportError:
    HAS_X402 = False

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
    trust_scoring_router,
)
from api.v1.routes.support import router as support_router
from api.v1.routes.market_trends import router as market_trends_router
from api.v1.routes.trend_analysis import router as trend_analysis_router
from api.v1.routes.diagnostic import router as diagnostic_router
from api.v1.routes.products_import import router as products_import_router
from api.v1.routes.product_sync import router as product_sync_router, import_router as product_sync_import_router

# Intelligence Environment — standalone at /api/v1/outcomes
from api.v1.routes.pricing.outcomes import router as outcomes_router

# Intelligence Environment — Phase 5 dashboard at /api/v1/intelligence
from api.v1.routes.intelligence import router as intelligence_router

# Gemini 3 Hackathon Demo Routes
from api.v1.routes.visual_pricing import router as visual_pricing_router
from api.v1.routes.crisis_detection import router as crisis_detection_router
from api.v1.routes.launch_detection import router as launch_detection_router
from api.v1.routes.market_trends_visual import router as market_trends_visual_router
from api.v1.routes.market_intelligence import router as market_intelligence_router

# ── Optional: x402 Agent API ──────────────────────────────
try:
    from api.v1.routes.x402_agent_api import router as x402_agent_router
    HAS_X402_ROUTER = True
except ImportError:
    HAS_X402_ROUTER = False

# ── Optional: Autonomous pipeline ─────────────────────────
try:
    from api.v1.routes.autonomous_pipeline import router as autonomous_pipeline_router
    HAS_AUTONOMOUS = True
except ImportError:
    HAS_AUTONOMOUS = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info(
        "Application starting",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

    # AP-032: Start WebSocket heartbeat as a background task.
    # Pings all active connections every 30s and removes stale ones
    # (dead browser tabs, network drops, mobile sleep) so they don't
    # accumulate unboundedly in active_connections.
    from core.websocket import start_heartbeat
    heartbeat_task = asyncio.create_task(start_heartbeat())

    yield

    # Clean shutdown: cancel the heartbeat and wait for it to finish.
    heartbeat_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await heartbeat_task

    logger.info("Application shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

# ── Optional: Initialize x402 payment middleware ──────────
# AP-031: Use settings.PAY_TO_ADDRESS instead of bare os.getenv().
if HAS_X402 and settings.PAY_TO_ADDRESS:
    init_x402(app, network="base-sepolia")

# ───────────────────── Exception Handlers ───────────────────── #
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(SQLAlchemyError, database_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# ───────────────────── Middleware ───────────────────── #
app.add_middleware(RequestLoggingMiddleware)

cors_origins = settings.cors_origins_list
if "*" in cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
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

# ───────────────────── Routes ───────────────────── #
app.include_router(health_router)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(products_import_router, prefix="/api/v1")
app.include_router(product_sync_router, prefix="/api/v1")
app.include_router(product_sync_import_router, prefix="/api/v1")
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
app.include_router(trend_analysis_router, prefix="/api/v1")
app.include_router(trust_scoring_router, prefix="/api/v1")
app.include_router(diagnostic_router, prefix="/api/v1")

# Intelligence Environment — outcomes served at /api/v1/outcomes/*
app.include_router(outcomes_router, prefix="/api/v1/outcomes", tags=["outcomes"])

# Intelligence Environment — Phase 5 dashboard at /api/v1/intelligence/*
app.include_router(intelligence_router, prefix="/api/v1")

# Gemini 3 Hackathon Demo Routes
app.include_router(visual_pricing_router, prefix="/api/v1")
app.include_router(crisis_detection_router, prefix="/api/v1")
app.include_router(launch_detection_router, prefix="/api/v1")
app.include_router(market_trends_visual_router, prefix="/api/v1")
app.include_router(market_intelligence_router, prefix="/api/v1")

# ── Optional: x402 Agent API Routes ───────────────────────
if HAS_X402_ROUTER:
    app.include_router(x402_agent_router)  # /api/v1/agent/*

# ── Optional: Autonomous pipeline Routes ──────────────────
if HAS_AUTONOMOUS:
    app.include_router(autonomous_pipeline_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "x402_enabled": HAS_X402_ROUTER,
    }



