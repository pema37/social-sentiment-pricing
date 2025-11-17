from fastapi import FastAPI
from backend.api.v1.routes.auth import router as auth_router

app = FastAPI(title="Social Sentiment Pricing API")

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
