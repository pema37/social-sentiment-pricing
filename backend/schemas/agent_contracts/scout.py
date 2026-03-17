"""
Scout Agent Output Contract.

Scout's job: Gather raw competitive intelligence for one product.
Feeds into: Analyst
Stored in: scout_evidence JSONB column on RecommendationOutcome
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .shared import DataSource


class CompetitorPrice(BaseModel):
    """A single competitor's price observation."""

    competitor_name: str
    price: Decimal
    currency: str = "USD"
    url: str | None = None
    scraped_at: datetime
    is_on_sale: bool = False
    sale_price: Decimal | None = None


class SentimentSnapshot(BaseModel):
    """Aggregated sentiment at time of scouting."""

    overall_score: float = Field(ge=-1.0, le=1.0)
    mention_count: int = Field(ge=0)
    positive_ratio: float = Field(ge=0.0, le=1.0)
    negative_ratio: float = Field(ge=0.0, le=1.0)
    neutral_ratio: float = Field(ge=0.0, le=1.0)
    trending_topics: list[str] = Field(default_factory=list)
    crisis_detected: bool = False
    crisis_severity: float | None = Field(default=None, ge=0.0, le=1.0)
    source_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description="Mention count by source: {'twitter': 42, 'reddit': 15, ...}",
    )


class PriceHistoryPoint(BaseModel):
    """Historical price data point for trend analysis."""

    price: Decimal
    recorded_at: datetime
    source: str = "internal"


class ScoutOutput(BaseModel):
    """
    Everything Scout knows about the competitive landscape for one product.

    Contract:
    - MUST populate product_id and scouted_at
    - MUST populate data_completeness (0.0 to 1.0)
    - SHOULD populate competitors (empty list if none found)
    - SHOULD populate sentiment (None if no social data)
    - SHOULD populate price_history (empty list if no history)
    - MUST be honest about data_sources used
    """

    # Identity
    product_id: UUID
    scouted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Competitor intelligence
    competitors: list[CompetitorPrice] = Field(default_factory=list)
    competitor_count: int = Field(ge=0, default=0)
    our_price: Decimal
    our_position: str | None = Field(
        default=None,
        description="'cheapest', 'below_median', 'at_median', 'above_median', 'most_expensive'",
    )
    competitive_position_index: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="0.0 = cheapest in market, 1.0 = most expensive",
    )

    # Sentiment intelligence
    sentiment: SentimentSnapshot | None = None

    # Price history (for trend detection)
    price_history: list[PriceHistoryPoint] = Field(default_factory=list)
    price_trend: str | None = Field(
        default=None,
        description="'rising', 'falling', 'stable', 'volatile'",
    )

    # Data quality (critical for Analyst confidence decomposition)
    data_completeness: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = no data, 1.0 = full coverage. < 0.6 triggers Scout priority queue.",
    )
    data_sources: list[DataSource] = Field(default_factory=list)
    data_gaps: list[str] = Field(
        default_factory=list,
        description="What's missing: ['no_competitor_prices', 'no_social_data', ...]",
    )

    # Metadata
    scout_version: str = "1.0"
    processing_time_ms: int | None = None

    @field_validator("competitor_count", mode="before")
    @classmethod
    def set_competitor_count(cls, v, info):
        """Auto-set from competitors list if not provided."""
        if v == 0 and "competitors" in info.data:
            return len(info.data["competitors"])
        return v

    def to_evidence(self) -> dict:
        """Serialize for JSONB storage on RecommendationOutcome.scout_evidence."""
        return self.model_dump(mode="json")
