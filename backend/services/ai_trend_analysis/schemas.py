"""
AI Trend Analysis - Data Models

These models define the structure of trend analysis results.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum


class TrendDirection(str, Enum):
    """Direction of a detected trend."""

    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    VOLATILE = "volatile"


class TrendCategory(str, Enum):
    """Category of detected trend."""

    VIRAL_POSITIVE = "viral_positive"
    VIRAL_NEGATIVE = "viral_negative"
    COMPETITOR_LAUNCH = "competitor_launch"
    SEASONAL = "seasonal"
    NEWS_EVENT = "news_event"
    MARKET_SHIFT = "market_shift"
    ORGANIC_GROWTH = "organic_growth"
    ORGANIC_DECLINE = "organic_decline"


class OpportunityType(str, Enum):
    """Type of pricing opportunity."""

    PRICE_INCREASE = "price_increase"
    PRICE_DECREASE = "price_decrease"
    HOLD = "hold"
    PROMOTIONAL = "promotional"
    PREMIUM_POSITIONING = "premium_positioning"


class RiskLevel(str, Enum):
    """Risk severity level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceLevel(str, Enum):
    """Confidence level of AI prediction."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class TrendSignal:
    """A single trend signal detected from data."""

    signal_type: str
    value: float
    timestamp: datetime
    source: str  # 'sentiment', 'volume', 'competitor', 'velocity'
    description: str


@dataclass
class TrendPrediction:
    """AI-generated prediction for a trend."""

    direction: TrendDirection
    category: TrendCategory
    confidence: ConfidenceLevel
    confidence_score: float  # 0-100
    predicted_change: float  # Percentage change expected
    timeframe_days: int  # Days until expected change
    reasoning: str
    supporting_signals: list[TrendSignal] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PricingOpportunity:
    """A detected pricing opportunity."""

    opportunity_type: OpportunityType
    product_id: str
    product_name: str
    current_price: Decimal
    suggested_price: Decimal
    expected_impact: str  # e.g., "+12% revenue", "-5% margin"
    confidence: ConfidenceLevel
    confidence_score: float
    reasoning: str
    valid_until: datetime
    triggers: list[str] = field(default_factory=list)


@dataclass
class RiskAlert:
    """A detected risk that requires attention."""

    risk_level: RiskLevel
    risk_type: str
    title: str
    description: str
    affected_products: list[str]
    recommended_actions: list[str]
    detected_at: datetime
    expires_at: datetime | None = None


@dataclass
class AIInsight:
    """AI-generated insight about market conditions."""

    title: str
    summary: str
    detailed_analysis: str
    key_factors: list[str]
    data_points_analyzed: int
    generated_at: datetime
    model_used: str  # 'openai' or 'gemini'


@dataclass
class TrendAnalysisResult:
    """Complete result of AI trend analysis."""

    user_id: str
    analysis_id: str
    generated_at: datetime

    # Overall market assessment
    market_sentiment: TrendDirection
    market_sentiment_score: float  # -100 to +100

    # Predictions
    predictions: list[TrendPrediction]

    # Opportunities
    opportunities: list[PricingOpportunity]

    # Risks
    risks: list[RiskAlert]

    # AI Insights
    insights: list[AIInsight]

    # Summary
    executive_summary: str
    recommended_actions: list[str]

    # Metadata
    products_analyzed: int
    mentions_analyzed: int
    time_range_days: int

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "user_id": self.user_id,
            "analysis_id": self.analysis_id,
            "generated_at": self.generated_at.isoformat(),
            "market_sentiment": self.market_sentiment.value,
            "market_sentiment_score": self.market_sentiment_score,
            "predictions": [
                {
                    "direction": p.direction.value,
                    "category": p.category.value,
                    "confidence": p.confidence.value,
                    "confidence_score": p.confidence_score,
                    "predicted_change": p.predicted_change,
                    "timeframe_days": p.timeframe_days,
                    "reasoning": p.reasoning,
                    "supporting_signals": [
                        {
                            "signal_type": s.signal_type,
                            "value": s.value,
                            "timestamp": s.timestamp.isoformat(),
                            "source": s.source,
                            "description": s.description,
                        }
                        for s in p.supporting_signals
                    ],
                }
                for p in self.predictions
            ],
            "opportunities": [
                {
                    "opportunity_type": o.opportunity_type.value,
                    "product_id": o.product_id,
                    "product_name": o.product_name,
                    "current_price": str(o.current_price),
                    "suggested_price": str(o.suggested_price),
                    "expected_impact": o.expected_impact,
                    "confidence": o.confidence.value,
                    "confidence_score": o.confidence_score,
                    "reasoning": o.reasoning,
                    "valid_until": o.valid_until.isoformat(),
                    "triggers": o.triggers,
                }
                for o in self.opportunities
            ],
            "risks": [
                {
                    "risk_level": r.risk_level.value,
                    "risk_type": r.risk_type,
                    "title": r.title,
                    "description": r.description,
                    "affected_products": r.affected_products,
                    "recommended_actions": r.recommended_actions,
                    "detected_at": r.detected_at.isoformat(),
                    "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                }
                for r in self.risks
            ],
            "insights": [
                {
                    "title": i.title,
                    "summary": i.summary,
                    "detailed_analysis": i.detailed_analysis,
                    "key_factors": i.key_factors,
                    "data_points_analyzed": i.data_points_analyzed,
                    "generated_at": i.generated_at.isoformat(),
                    "model_used": i.model_used,
                }
                for i in self.insights
            ],
            "executive_summary": self.executive_summary,
            "recommended_actions": self.recommended_actions,
            "products_analyzed": self.products_analyzed,
            "mentions_analyzed": self.mentions_analyzed,
            "time_range_days": self.time_range_days,
        }
