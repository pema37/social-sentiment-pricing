# backend/schemas/__init__.py

"""
Pydantic Schemas for API validation.
"""

from schemas.user import (
    UserCreate,
    UserRead,
    UserUpdateMe,
)
from schemas.auth import (
    TokenResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductRead,
    PriceSuggestion,
)
from schemas.sentiment import (
    SentimentAnalyzeRequest,
    SentimentBulkRequest,
    SentimentScores,
    SentimentRead,
    SentimentAnalyzeResponse,
    SentimentSummary,
)
from schemas.health import HealthResponse

# Phase 2: Competitor Schemas
from schemas.competitor import (
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

# Phase 6: Alert Schemas
from schemas.alert import (
    AlertConfigurationCreate,
    AlertConfigurationUpdate,
    AlertConfigurationRead,
    AlertCreate,
    AlertRead,
    AlertAcknowledge,
    AlertResolve,
    AlertStats,
    AlertListResponse,
)

# Competitor Matching Schemas
from schemas.competitor_matching import (
    CompetitorSearchRequest,
    ProductMatchRequest,
    BulkMatchRequest,
    MatchedProductSchema,
    CompetitorSearchResponse,
    ProviderInfoSchema,
    ProvidersListResponse,
    BulkMatchResultSchema,
    BulkMatchResponse,
    AutoLinkResultSchema,
    CacheClearResponse,
    MatchingErrorResponse,
)

# NEW: Trust Scoring / Bot Detection Schemas
from schemas.trust_scoring import (
    # Author scoring
    AuthorScoreRequest,
    AuthorScoreResponse,
    BatchAuthorScoreRequest,
    BatchAuthorScoreResponse,
    ComponentScores,
    # Content analysis
    ContentAnalysisRequest,
    ContentAnalysisResponse,
    BatchContentAnalysisRequest,
    BatchContentAnalysisResponse,
    SpamIndicators,
    # Campaign detection
    CampaignDetectionRequest,
    CampaignDetectionResponse,
    CampaignSignalResponse,
    MentionInput,
    # Weighted sentiment
    WeightedSentimentRequest,
    WeightedSentimentResponse,
    RawSentimentStats,
    AdjustedSentimentStats,
    QualityMetrics,
    # Quick checks
    QuickSpamCheckRequest,
    QuickSpamCheckResponse,
    QuickTrustCheckRequest,
    QuickTrustCheckResponse,
    # Stats
    TrustScoringStatsResponse,
    # Enums
    TrustLevelEnum,
    RiskFlagEnum,
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
    # Alert (Phase 6)
    "AlertConfigurationCreate",
    "AlertConfigurationUpdate",
    "AlertConfigurationRead",
    "AlertCreate",
    "AlertRead",
    "AlertAcknowledge",
    "AlertResolve",
    "AlertStats",
    "AlertListResponse",
    # Competitor Matching
    "CompetitorSearchRequest",
    "ProductMatchRequest",
    "BulkMatchRequest",
    "MatchedProductSchema",
    "CompetitorSearchResponse",
    "ProviderInfoSchema",
    "ProvidersListResponse",
    "BulkMatchResultSchema",
    "BulkMatchResponse",
    "AutoLinkResultSchema",
    "CacheClearResponse",
    "MatchingErrorResponse",
    # NEW: Trust Scoring / Bot Detection
    "AuthorScoreRequest",
    "AuthorScoreResponse",
    "BatchAuthorScoreRequest",
    "BatchAuthorScoreResponse",
    "ComponentScores",
    "ContentAnalysisRequest",
    "ContentAnalysisResponse",
    "BatchContentAnalysisRequest",
    "BatchContentAnalysisResponse",
    "SpamIndicators",
    "CampaignDetectionRequest",
    "CampaignDetectionResponse",
    "CampaignSignalResponse",
    "MentionInput",
    "WeightedSentimentRequest",
    "WeightedSentimentResponse",
    "RawSentimentStats",
    "AdjustedSentimentStats",
    "QualityMetrics",
    "QuickSpamCheckRequest",
    "QuickSpamCheckResponse",
    "QuickTrustCheckRequest",
    "QuickTrustCheckResponse",
    "TrustScoringStatsResponse",
    "TrustLevelEnum",
    "RiskFlagEnum",
]



