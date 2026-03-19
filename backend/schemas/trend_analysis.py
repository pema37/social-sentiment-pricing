"""
Trend Analysis API Schemas

Pydantic schemas for the trend analysis API endpoints.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# ============================================
# ENUMS
# ============================================


class TrendDirection(StrEnum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    VOLATILE = "volatile"


class TrendCategory(StrEnum):
    VIRAL_POSITIVE = "viral_positive"
    VIRAL_NEGATIVE = "viral_negative"
    COMPETITOR_LAUNCH = "competitor_launch"
    SEASONAL = "seasonal"
    NEWS_EVENT = "news_event"
    MARKET_SHIFT = "market_shift"
    ORGANIC_GROWTH = "organic_growth"
    ORGANIC_DECLINE = "organic_decline"


class OpportunityType(StrEnum):
    PRICE_INCREASE = "price_increase"
    PRICE_DECREASE = "price_decrease"
    HOLD = "hold"
    PROMOTIONAL = "promotional"
    PREMIUM_POSITIONING = "premium_positioning"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


# ============================================
# REQUEST SCHEMAS
# ============================================


class TrendAnalysisRequest(BaseModel):
    """Request to run AI trend analysis."""

    days: int = Field(default=30, ge=7, le=90, description="Number of days to analyze (7-90)")
    product_ids: list[str] | None = Field(
        default=None, description="Specific product IDs to analyze (None = all products)"
    )
    use_model: str = Field(
        default="openai", pattern="^(openai|gemini)$", description="AI model to use: 'openai' or 'gemini'"
    )


class ProductOpportunityRequest(BaseModel):
    """Request to analyze a specific product for opportunities."""

    product_id: str = Field(..., description="Product ID to analyze")
    use_model: str = Field(default="openai", pattern="^(openai|gemini)$", description="AI model to use")


class RiskDetectionRequest(BaseModel):
    """Request to detect risks."""

    use_model: str = Field(default="openai", pattern="^(openai|gemini)$", description="AI model to use")


class InsightGenerationRequest(BaseModel):
    """Request to generate market insight."""

    days: int = Field(default=30, ge=7, le=90, description="Number of days to analyze")
    use_model: str = Field(default="openai", pattern="^(openai|gemini)$", description="AI model to use")


# ============================================
# RESPONSE SCHEMAS
# ============================================


class TrendSignalResponse(BaseModel):
    """A single trend signal."""

    signal_type: str
    value: float
    timestamp: datetime
    source: str
    description: str


class TrendPredictionResponse(BaseModel):
    """A trend prediction."""

    direction: TrendDirection
    category: TrendCategory
    confidence: ConfidenceLevel
    confidence_score: float = Field(ge=0, le=100)
    predicted_change: float
    timeframe_days: int
    reasoning: str
    supporting_signals: list[TrendSignalResponse] = []


class PricingOpportunityResponse(BaseModel):
    """A pricing opportunity."""

    opportunity_type: OpportunityType
    product_id: str
    product_name: str
    current_price: str
    suggested_price: str
    expected_impact: str
    confidence: ConfidenceLevel
    confidence_score: float = Field(ge=0, le=100)
    reasoning: str
    valid_until: datetime
    triggers: list[str] = []


class RiskAlertResponse(BaseModel):
    """A risk alert."""

    risk_level: RiskLevel
    risk_type: str
    title: str
    description: str
    affected_products: list[str] = []
    recommended_actions: list[str] = []
    detected_at: datetime
    expires_at: datetime | None = None


class AIInsightResponse(BaseModel):
    """An AI-generated insight."""

    title: str
    summary: str
    detailed_analysis: str
    key_factors: list[str] = []
    data_points_analyzed: int
    generated_at: datetime
    model_used: str


class TrendAnalysisResponse(BaseModel):
    """Complete trend analysis result."""

    model_config = ConfigDict(from_attributes=True)
    analysis_id: str
    generated_at: datetime

    # Market overview
    market_sentiment: TrendDirection
    market_sentiment_score: float = Field(ge=-100, le=100)

    # Analysis results
    predictions: list[TrendPredictionResponse] = []
    opportunities: list[PricingOpportunityResponse] = []
    risks: list[RiskAlertResponse] = []
    insights: list[AIInsightResponse] = []

    # Summary
    executive_summary: str
    recommended_actions: list[str] = []

    # Metadata
    products_analyzed: int
    mentions_analyzed: int
    time_range_days: int


class RiskDetectionResponse(BaseModel):
    """Risk detection result."""

    risks: list[RiskAlertResponse] = []
    overall_risk_level: RiskLevel
    summary: str
    generated_at: datetime


class QuickStatsResponse(BaseModel):
    """Quick stats for the trends dashboard."""

    # Sentiment
    current_sentiment: float
    sentiment_trend: TrendDirection
    sentiment_change_7d: float

    # Volume
    mentions_today: int
    mentions_7d: int
    volume_change_percent: float

    # Opportunities
    active_opportunities: int
    potential_revenue_impact: str

    # Risks
    active_risks: int
    highest_risk_level: RiskLevel

    # Products
    trending_up: list[str]
    trending_down: list[str]

    last_updated: datetime
