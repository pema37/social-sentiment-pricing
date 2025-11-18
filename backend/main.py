from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.routes.auth import router as auth_router

app = FastAPI(
    title="Social Sentiment Pricing API",
    version="0.1.0",
)

# CORS – for now allow everything (we’ll tighten later)
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


# Auth endpoints
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
