# backend/schemas/__init__.py

"""
Pydantic Schemas for API validation.
"""

from backend.schemas.user import (
    UserCreate,
    UserRead,
    UserUpdateMe,
)
from backend.schemas.auth import (
    TokenResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from backend.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductRead,
    PriceSuggestion,
)
from backend.schemas.sentiment import (
    SentimentAnalyzeRequest,
    SentimentBulkRequest,
    SentimentScores,
    SentimentRead,
    SentimentAnalyzeResponse,
    SentimentSummary,
)
from backend.schemas.health import HealthResponse

# Phase 2: Competitor Schemas
from backend.schemas.competitor import (
    CompetitorCreate,
    CompetitorUpdate,
    CompetitorResponse,
    CompetitorListResponse,
    CompetitorProductCreate,
    CompetitorProductUpdate,
    CompetitorProductResponse,
    CompetitorProductWithDetails,
    CompetitorProductListResponse,
    CompetitorPriceHistoryResponse,
    CompetitorPriceHistoryListResponse,
    CompetitorPriceComparison,
    CompetitorAlert,
    CompetitorTrendAnalysis,
)


__all__ = [
    # User
    "UserCreate",
    "UserRead",
    "UserUpdateMe",
    # Auth
    "TokenResponse",
    "LoginRequest",
    "RegisterRequest",
    "UserResponse",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    # Product
    "ProductCreate",
    "ProductUpdate",
    "ProductRead",
    "PriceSuggestion",
    # Sentiment
    "SentimentAnalyzeRequest",
    "SentimentBulkRequest",
    "SentimentScores",
    "SentimentRead",
    "SentimentAnalyzeResponse",
    "SentimentSummary",
    # Health
    "HealthResponse",
    # Competitor (Phase 2)
    "CompetitorCreate",
    "CompetitorUpdate",
    "CompetitorResponse",
    "CompetitorListResponse",
    "CompetitorProductCreate",
    "CompetitorProductUpdate",
    "CompetitorProductResponse",
    "CompetitorProductWithDetails",
    "CompetitorProductListResponse",
    "CompetitorPriceHistoryResponse",
    "CompetitorPriceHistoryListResponse",
    "CompetitorPriceComparison",
    "CompetitorAlert",
    "CompetitorTrendAnalysis",
]

