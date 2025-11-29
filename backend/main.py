# backend/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.routes.auth import router as auth_router
from backend.api.v1.routes.health import router as health_router
from backend.api.v1.routes.products import router as products_router
from backend.api.v1.routes.sentiment import router as sentiment_router

app = FastAPI(
    title="Social Sentiment Pricing API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "SSP backend is running"}


# Versioned API base: /api/v1
app.include_router(auth_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(sentiment_router, prefix="/api/v1")
