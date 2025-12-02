# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.core.config import settings
from backend.api.v1.routes.auth import router as auth_router
from backend.api.v1.routes.health import router as health_router
from backend.api.v1.routes.users import router as users_router
from backend.api.v1.routes.products import router as products_router
from backend.api.v1.routes.sentiment import router as sentiment_router
from backend.api.v1.routes.competitors import router as competitors_router
from backend.api.v1.routes.integrations import router as integrations_router
from backend.api.v1.routes.webhooks import router as webhooks_router
from backend.api.v1.routes.pricing import router as pricing_router  

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["root"])
def read_root():
    return {
        "message": "SSP backend is running",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }

# Versioned API base: /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(sentiment_router, prefix="/api/v1")
app.include_router(competitors_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(pricing_router, prefix="/api/v1")  

