# backend/schemas/__init__.py

"""
Pydantic Schemas for API validation.
"""

# Phase 6: Alert Schemas
from schemas.alert import (
    AlertAcknowledge,
    AlertConfigurationCreate,
    AlertConfigurationRead,
    AlertConfigurationUpdate,
    AlertCreate,
    AlertListResponse,
    AlertRead,
    AlertResolve,
    AlertStats,
)
from schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)

# Phase 2: Competitor Schemas
from schemas.competitor import (
    CompetitorAlert,
    CompetitorCreate,
    CompetitorListResponse,
    CompetitorPriceComparison,
    CompetitorPriceHistoryListResponse,
    CompetitorPriceHistoryResponse,
    CompetitorProductCreate,
    CompetitorProductListResponse,
    CompetitorProductResponse,
    CompetitorProductUpdate,
    CompetitorProductWithDetails,
    CompetitorResponse,
    CompetitorTrendAnalysis,
    CompetitorUpdate,
)

# Competitor Matching Schemas
from schemas.competitor_matching import (
    AutoLinkResultSchema,
    BulkMatchRequest,
    BulkMatchResponse,
    BulkMatchResultSchema,
    CacheClearResponse,
    CompetitorSearchRequest,
    CompetitorSearchResponse,
    MatchedProductSchema,
    MatchingErrorResponse,
    ProductMatchRequest,
    ProviderInfoSchema,
    ProvidersListResponse,
)
from schemas.health import HealthResponse
from schemas.product import (
    PriceSuggestion,
    ProductCreate,
    ProductRead,
    ProductUpdate,
)
from schemas.sentiment import (
    SentimentAnalyzeRequest,
    SentimentAnalyzeResponse,
    SentimentBulkRequest,
    SentimentRead,
    SentimentScores,
    SentimentSummary,
)

# NEW: Trust Scoring / Bot Detection Schemas
from schemas.trust_scoring import (
    AdjustedSentimentStats,
    # Author scoring
    AuthorScoreRequest,
    AuthorScoreResponse,
    BatchAuthorScoreRequest,
    BatchAuthorScoreResponse,
    BatchContentAnalysisRequest,
    BatchContentAnalysisResponse,
    # Campaign detection
    CampaignDetectionRequest,
    CampaignDetectionResponse,
    CampaignSignalResponse,
    ComponentScores,
    # Content analysis
    ContentAnalysisRequest,
    ContentAnalysisResponse,
    MentionInput,
    QualityMetrics,
    # Quick checks
    QuickSpamCheckRequest,
    QuickSpamCheckResponse,
    QuickTrustCheckRequest,
    QuickTrustCheckResponse,
    RawSentimentStats,
    RiskFlagEnum,
    SpamIndicators,
    # Enums
    TrustLevelEnum,
    # Stats
    TrustScoringStatsResponse,
    # Weighted sentiment
    WeightedSentimentRequest,
    WeightedSentimentResponse,
)
from schemas.user import (
    UserCreate,
    UserRead,
    UserUpdateMe,
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
