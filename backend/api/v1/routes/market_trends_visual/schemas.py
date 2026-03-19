"""
Market Trends Visual - Schemas & Data Models

Contains:
- Enums for trend types, directions, timeframes
- Dataclasses for internal data structures
- Pydantic models for API request/response validation
"""

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, Field

# =========================================================================
# ENUMS
# =========================================================================


class TrendAgent(StrEnum):
    """The three agents in our trend analysis system."""

    OBSERVER = "observer"
    ANALYST = "analyst"
    FORECASTER = "forecaster"


class TrendDirection(StrEnum):
    """Trend direction classifications."""

    STRONG_UP = "strong_up"
    UP = "up"
    STABLE = "stable"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


class TrendTimeframe(StrEnum):
    """Timeframes for trend analysis."""

    IMMEDIATE = "immediate"  # 24-48 hours
    SHORT_TERM = "short_term"  # 1-2 weeks
    MEDIUM_TERM = "medium_term"  # 1-3 months
    LONG_TERM = "long_term"  # 3+ months


# =========================================================================
# INTERNAL DATACLASSES
# =========================================================================


@dataclass
class TrendMessage:
    """A message from an agent during trend analysis."""

    agent: TrendAgent
    thought_type: str | None  # ThoughtType value
    content: str
    is_final: bool = False
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "agent": self.agent.value,
            "thought_type": self.thought_type,
            "content": self.content,
            "is_final": self.is_final,
            "metadata": self.metadata if self.is_final else {},
        }


@dataclass
class MarketDataPoint:
    """Market data for trend analysis."""

    sentiment_score: float = 0.0  # -1.0 to 1.0
    sentiment_trend: str = "stable"  # up, down, stable
    volume_24h: int = 0
    volume_trend: str = "stable"
    price_change_7d: float = 0.0
    price_change_30d: float = 0.0
    social_mentions: int = 0
    social_trend: str = "stable"
    competitor_activity: str = "normal"
    market_position: str = "mid"
    seasonality: str = "normal"


@dataclass
class TrendForecast:
    """Final trend forecast from the system."""

    direction: TrendDirection
    confidence: float
    timeframe: TrendTimeframe
    recommended_action: str
    price_adjustment: float | None = None
    key_drivers: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    monitoring_points: list[str] = field(default_factory=list)


# =========================================================================
# PYDANTIC MODELS (API Request/Response)
# =========================================================================


class MarketDataInput(BaseModel):
    """Input model for market data - API request body."""

    product: str = Field(..., description="Product name being analyzed")
    category: str = Field(..., description="Product category")
    sentiment_score: float = Field(0.0, ge=-1.0, le=1.0, description="Sentiment score (-1 to 1)")
    sentiment_trend: str = Field("stable", description="Sentiment trend direction")
    volume_24h: int = Field(0, ge=0, description="24-hour volume")
    volume_trend: str = Field("stable", description="Volume trend direction")
    price_change_7d: float = Field(0.0, description="7-day price change percentage")
    price_change_30d: float = Field(0.0, description="30-day price change percentage")
    social_mentions: int = Field(0, ge=0, description="Number of social mentions")
    social_trend: str = Field("stable", description="Social mention trend")
    competitor_activity: str = Field("normal", description="Competitor activity level")
    market_position: str = Field("mid", description="Market position")
    seasonality: str = Field("normal", description="Seasonality factor")

    def to_dict(self) -> dict:
        """Convert to dictionary for analyzer."""
        return {
            "sentiment_score": self.sentiment_score,
            "sentiment_trend": self.sentiment_trend,
            "volume_24h": self.volume_24h,
            "volume_trend": self.volume_trend,
            "price_change_7d": self.price_change_7d,
            "price_change_30d": self.price_change_30d,
            "social_mentions": self.social_mentions,
            "social_trend": self.social_trend,
            "competitor_activity": self.competitor_activity,
            "market_position": self.market_position,
            "seasonality": self.seasonality,
        }


class TrendAnalysisResponse(BaseModel):
    """Response model for non-streaming trend analysis."""

    status: str
    message: str
    product: str | None = None
    category: str | None = None
    message_count: int | None = None


class TrendHealthResponse(BaseModel):
    """Response model for health check."""

    status: str
    service: str
    model: str
    agents: list[str]
