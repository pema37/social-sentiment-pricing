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
    "AdjustedSentimentStats",
    "AlertAcknowledge",
    # Alert (Phase 6)
    "AlertConfigurationCreate",
    "AlertConfigurationRead",
    "AlertConfigurationUpdate",
    "AlertCreate",
    "AlertListResponse",
    "AlertRead",
    "AlertResolve",
    "AlertStats",
    # NEW: Trust Scoring / Bot Detection
    "AuthorScoreRequest",
    "AuthorScoreResponse",
    "AutoLinkResultSchema",
    "BatchAuthorScoreRequest",
    "BatchAuthorScoreResponse",
    "BatchContentAnalysisRequest",
    "BatchContentAnalysisResponse",
    "BulkMatchRequest",
    "BulkMatchResponse",
    "BulkMatchResultSchema",
    "CacheClearResponse",
    "CampaignDetectionRequest",
    "CampaignDetectionResponse",
    "CampaignSignalResponse",
    "CompetitorAlert",
    # Competitor (Phase 2)
    "CompetitorCreate",
    "CompetitorListResponse",
    "CompetitorPriceComparison",
    "CompetitorPriceHistoryListResponse",
    "CompetitorPriceHistoryResponse",
    "CompetitorProductCreate",
    "CompetitorProductListResponse",
    "CompetitorProductResponse",
    "CompetitorProductUpdate",
    "CompetitorProductWithDetails",
    "CompetitorResponse",
    # Competitor Matching
    "CompetitorSearchRequest",
    "CompetitorSearchResponse",
    "CompetitorTrendAnalysis",
    "CompetitorUpdate",
    "ComponentScores",
    "ContentAnalysisRequest",
    "ContentAnalysisResponse",
    "ForgotPasswordRequest",
    # Health
    "HealthResponse",
    "LoginRequest",
    "MatchedProductSchema",
    "MatchingErrorResponse",
    "MentionInput",
    "PriceSuggestion",
    # Product
    "ProductCreate",
    "ProductMatchRequest",
    "ProductRead",
    "ProductUpdate",
    "ProviderInfoSchema",
    "ProvidersListResponse",
    "QualityMetrics",
    "QuickSpamCheckRequest",
    "QuickSpamCheckResponse",
    "QuickTrustCheckRequest",
    "QuickTrustCheckResponse",
    "RawSentimentStats",
    "RegisterRequest",
    "ResetPasswordRequest",
    "RiskFlagEnum",
    # Sentiment
    "SentimentAnalyzeRequest",
    "SentimentAnalyzeResponse",
    "SentimentBulkRequest",
    "SentimentRead",
    "SentimentScores",
    "SentimentSummary",
    "SpamIndicators",
    # Auth
    "TokenResponse",
    "TrustLevelEnum",
    "TrustScoringStatsResponse",
    # User
    "UserCreate",
    "UserRead",
    "UserResponse",
    "UserUpdateMe",
    "WeightedSentimentRequest",
    "WeightedSentimentResponse",
]
