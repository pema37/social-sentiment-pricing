# backend/schemas/trust_scoring.py

"""
Pydantic schemas for Trust Scoring API endpoints.

Provides request/response models for:
- Author trust scoring
- Content analysis
- Campaign detection
- Weighted sentiment calculation
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────


class TrustLevelEnum(StrEnum):
    VERIFIED = "verified"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNTRUSTED = "untrusted"
    BLOCKED = "blocked"


class RiskFlagEnum(StrEnum):
    NEW_ACCOUNT = "new_account"
    LOW_FOLLOWERS = "low_followers"
    HIGH_POST_FREQUENCY = "high_post_frequency"
    REPETITIVE_CONTENT = "repetitive_content"
    COORDINATED_TIMING = "coordinated_timing"
    SUSPICIOUS_ENGAGEMENT = "suspicious_engagement"
    KEYWORD_STUFFING = "keyword_stuffing"
    LINK_SPAM = "link_spam"
    COPY_PASTE = "copy_paste"
    SENTIMENT_EXTREME = "sentiment_extreme"
    BOT_PATTERN = "bot_pattern"
    FAKE_ENGAGEMENT = "fake_engagement"


# ─────────────────────────────────────────────────────────────────────────────
# Author Scoring
# ─────────────────────────────────────────────────────────────────────────────


class AuthorScoreRequest(BaseModel):
    """Request to score an author's trustworthiness."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "author_id": "user_12345",
                "username": "techreviewer",
                "source": "twitter",
                "follower_count": 5420,
                "following_count": 312,
                "account_created_at": "2021-03-15T10:30:00Z",
                "is_verified": False,
            }
        }
    )
    author_id: str = Field(..., description="Unique author identifier")
    username: str = Field(..., description="Author's username")
    source: str = Field(..., description="Platform source (twitter, reddit, etc.)")
    follower_count: int | None = Field(None, ge=0, description="Number of followers")
    following_count: int | None = Field(None, ge=0, description="Number following")
    post_count: int | None = Field(None, ge=0, description="Total posts by author")
    account_created_at: datetime | None = Field(None, description="Account creation date")
    is_verified: bool = Field(False, description="Whether account is verified")


class ComponentScores(BaseModel):
    """Breakdown of trust score components."""

    account_age: float = Field(..., ge=0, le=1)
    followers: float = Field(..., ge=0, le=1)
    engagement: float = Field(..., ge=0, le=1)
    history: float = Field(..., ge=0, le=1)
    verification_bonus: float = Field(..., ge=0, le=1)


class AuthorScoreResponse(BaseModel):
    """Response with author trust assessment."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "author_id": "user_12345",
                "source": "twitter",
                "trust_score": 0.72,
                "trust_level": "high",
                "risk_flags": [],
                "risk_score": 0.1,
                "component_scores": {
                    "account_age": 0.85,
                    "followers": 0.65,
                    "engagement": 0.70,
                    "history": 0.50,
                    "verification_bonus": 0.0,
                },
                "confidence": 0.75,
                "calculated_at": "2026-01-16T12:00:00Z",
            }
        }
    )
    author_id: str
    source: str
    trust_score: float = Field(..., ge=0, le=1, description="Overall trust score")
    trust_level: TrustLevelEnum
    risk_flags: list[RiskFlagEnum] = Field(default_factory=list)
    risk_score: float = Field(..., ge=0, le=1, description="Risk assessment score")
    component_scores: ComponentScores
    confidence: float = Field(..., ge=0, le=1, description="Confidence in assessment")
    calculated_at: datetime


class BatchAuthorScoreRequest(BaseModel):
    """Request to score multiple authors."""

    authors: list[AuthorScoreRequest] = Field(..., max_length=100)


class BatchAuthorScoreResponse(BaseModel):
    """Response with multiple author scores."""

    scores: list[AuthorScoreResponse]
    total: int
    avg_trust_score: float


# ─────────────────────────────────────────────────────────────────────────────
# Content Analysis
# ─────────────────────────────────────────────────────────────────────────────


class ContentAnalysisRequest(BaseModel):
    """Request to analyze content for spam/manipulation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content_id": "post_abc123",
                "text": "Just tried this product and it's amazing! Highly recommend to everyone.",
                "author_username": "happycustomer",
            }
        }
    )
    content_id: str = Field(..., description="Unique content identifier")
    text: str = Field(..., min_length=1, max_length=10000, description="Content text")
    author_username: str | None = Field(None, description="Author's username")


class SpamIndicators(BaseModel):
    """Spam detection indicators."""

    excessive_hashtags: bool
    excessive_links: bool
    keyword_stuffing: bool
    all_caps: bool
    spam_phrases: bool


class ContentAnalysisResponse(BaseModel):
    """Response with content analysis results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content_id": "post_abc123",
                "word_count": 12,
                "is_duplicate": False,
                "duplicate_count": 0,
                "content_quality_score": 0.75,
                "originality_score": 1.0,
                "risk_flags": [],
                "spam_indicators": {
                    "excessive_hashtags": False,
                    "excessive_links": False,
                    "keyword_stuffing": False,
                    "all_caps": False,
                    "spam_phrases": False,
                },
                "is_spam": False,
            }
        }
    )
    content_id: str
    word_count: int
    is_duplicate: bool
    duplicate_count: int
    content_quality_score: float = Field(..., ge=0, le=1)
    originality_score: float = Field(..., ge=0, le=1)
    risk_flags: list[RiskFlagEnum]
    spam_indicators: SpamIndicators
    is_spam: bool = Field(..., description="Whether content is likely spam")


class BatchContentAnalysisRequest(BaseModel):
    """Request to analyze multiple content pieces."""

    contents: list[ContentAnalysisRequest] = Field(..., max_length=100)


class BatchContentAnalysisResponse(BaseModel):
    """Response with multiple content analyses."""

    analyses: list[ContentAnalysisResponse]
    total: int
    spam_count: int
    duplicate_count: int


# ─────────────────────────────────────────────────────────────────────────────
# Campaign Detection
# ─────────────────────────────────────────────────────────────────────────────


class MentionInput(BaseModel):
    """Input mention for campaign detection."""

    mention_id: str
    author_id: str
    content: str
    published_at: datetime
    sentiment_score: float | None = Field(None, ge=-1, le=1)
    source: str = "unknown"


class CampaignDetectionRequest(BaseModel):
    """Request to detect coordinated campaigns."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mentions": [
                    {
                        "mention_id": "m1",
                        "author_id": "a1",
                        "content": "Great product!",
                        "published_at": "2026-01-16T10:00:00Z",
                        "sentiment_score": 0.8,
                        "source": "twitter",
                    }
                ],
                "product_id": "prod_123",
                "time_window_hours": 24,
            }
        }
    )
    mentions: list[MentionInput] = Field(..., min_length=5, max_length=1000)
    product_id: str | None = None
    time_window_hours: int = Field(24, ge=1, le=168)


class CampaignSignalResponse(BaseModel):
    """A detected campaign signal."""

    signal_type: str
    strength: float = Field(..., ge=0, le=1)
    description: str


class CampaignDetectionResponse(BaseModel):
    """Response with campaign detection results."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "prod_123",
                "time_window_hours": 24,
                "is_campaign_detected": True,
                "campaign_confidence": 0.78,
                "signals": [
                    {
                        "signal_type": "timing_cluster",
                        "strength": 0.85,
                        "description": "Detected synchronized posting: 15 posts in tight clusters",
                    },
                    {
                        "signal_type": "content_similarity",
                        "strength": 0.72,
                        "description": "Found 8 pairs of highly similar content from different authors",
                    },
                ],
                "metrics": {
                    "posts_analyzed": 50,
                    "unique_authors": 25,
                },
                "suspicious_author_count": 8,
                "suspicious_content_count": 12,
                "analyzed_at": "2026-01-16T12:00:00Z",
            }
        }
    )
    product_id: str | None
    time_window_hours: int
    is_campaign_detected: bool
    campaign_confidence: float = Field(..., ge=0, le=1)
    signals: list[CampaignSignalResponse]
    metrics: dict[str, Any]
    suspicious_author_count: int
    suspicious_content_count: int
    analyzed_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# Weighted Sentiment
# ─────────────────────────────────────────────────────────────────────────────


class WeightedSentimentRequest(BaseModel):
    """Request for trust-adjusted sentiment calculation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "mentions": [
                    {
                        "mention_id": "m1",
                        "author_id": "a1",
                        "content": "Love this product!",
                        "published_at": "2026-01-16T10:00:00Z",
                        "sentiment_score": 0.9,
                        "source": "twitter",
                    },
                    {
                        "mention_id": "m2",
                        "author_id": "a2",
                        "content": "Terrible experience, avoid!",
                        "published_at": "2026-01-16T11:00:00Z",
                        "sentiment_score": -0.8,
                        "source": "reddit",
                    },
                ],
                "product_id": "prod_123",
                "period_hours": 24,
                "check_campaign": True,
            }
        }
    )
    mentions: list[MentionInput] = Field(..., min_length=1, max_length=1000)
    product_id: str | None = None
    period_hours: int = Field(24, ge=1, le=168)
    check_campaign: bool = Field(True, description="Whether to check for campaigns")

    # Optional author metadata (for better scoring)
    author_metadata: dict[str, dict[str, Any]] | None = Field(
        None, description="Map of author_id to metadata (follower_count, account_created_at, etc.)"
    )


class RawSentimentStats(BaseModel):
    """Raw sentiment statistics."""

    sentiment: float
    mention_count: int


class AdjustedSentimentStats(BaseModel):
    """Adjusted sentiment statistics."""

    sentiment: float
    effective_mentions: float


class QualityMetrics(BaseModel):
    """Quality metrics for sentiment analysis."""

    high_trust_ratio: float
    filtered_count: int
    confidence: float


class WeightedSentimentResponse(BaseModel):
    """Response with trust-adjusted sentiment."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "prod_123",
                "period_hours": 24,
                "raw": {
                    "sentiment": 0.45,
                    "mention_count": 100,
                },
                "adjusted": {
                    "sentiment": 0.32,
                    "effective_mentions": 67.5,
                },
                "quality": {
                    "high_trust_ratio": 0.35,
                    "filtered_count": 15,
                    "confidence": 0.72,
                },
                "trust_breakdown": {
                    "verified": 5,
                    "high": 30,
                    "medium": 40,
                    "low": 15,
                    "untrusted": 10,
                    "blocked": 0,
                },
                "campaign_detected": False,
            }
        }
    )
    product_id: str
    period_hours: int
    raw: RawSentimentStats
    adjusted: AdjustedSentimentStats
    quality: QualityMetrics
    trust_breakdown: dict[str, int]
    campaign_detected: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Quick Check Endpoints
# ─────────────────────────────────────────────────────────────────────────────


class QuickSpamCheckRequest(BaseModel):
    """Quick spam check request."""

    text: str = Field(..., min_length=1, max_length=5000)
    username: str | None = None


class QuickSpamCheckResponse(BaseModel):
    """Quick spam check response."""

    is_spam: bool
    spam_score: float = Field(..., ge=0, le=1)
    reasons: list[str]


class QuickTrustCheckRequest(BaseModel):
    """Quick author trust check request."""

    author_id: str
    username: str
    source: str
    follower_count: int | None = None
    account_age_days: int | None = None


class QuickTrustCheckResponse(BaseModel):
    """Quick author trust check response."""

    is_trustworthy: bool
    trust_score: float = Field(..., ge=0, le=1)
    trust_level: TrustLevelEnum
    risk_flags: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# Statistics
# ─────────────────────────────────────────────────────────────────────────────


class TrustScoringStatsResponse(BaseModel):
    """Trust scoring service statistics."""

    content_analyzer: dict[str, int]
    config: dict[str, Any]
    cache_stats: dict[str, int]
