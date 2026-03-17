"""
Analyst Agent Output Contract.

Analyst's job: Score and interpret Scout's raw data.
Consumes: ScoutOutput
Feeds into: Strategist
Stored in: analyst_evidence JSONB column on RecommendationOutcome
"""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from .shared import PriceDirection, UrgencyLevel


class ElasticityEstimate(BaseModel):
    """Analyst's estimate of price elasticity of demand."""

    point_estimate: float = Field(
        description="Estimated PED. Negative = normal good. e.g. -1.2 means 1% price increase → 1.2% demand decrease",
    )
    confidence_interval_low: float | None = None
    confidence_interval_high: float | None = None
    method: str = Field(
        default="bayesian_hierarchical",
        description="'bayesian_hierarchical', 'category_prior', 'historical_regression'",
    )
    prior_source: str | None = Field(
        default=None,
        description="'category_benchmark', 'merchant_history', 'default'",
    )
    sample_size: int | None = Field(
        default=None,
        description="Number of historical observations used",
    )


class ConfidenceDecomposition(BaseModel):
    """
    Per-component confidence scores.

    Feeds directly into the confidence_elasticity, confidence_position,
    confidence_urgency, confidence_data_quality columns on RecommendationOutcome.
    """

    elasticity: float = Field(ge=0.0, le=1.0, description="Confidence in elasticity estimate")
    position: float = Field(ge=0.0, le=1.0, description="Confidence in competitive position")
    urgency: float = Field(ge=0.0, le=1.0, description="Confidence in urgency assessment")
    data_quality: float = Field(ge=0.0, le=1.0, description="Input data completeness/reliability")

    @property
    def overall(self) -> float:
        """Weighted overall confidence. Matches the Analyst's scoring formula."""
        weights = {
            "elasticity": 0.30,
            "position": 0.25,
            "urgency": 0.20,
            "data_quality": 0.25,
        }
        return round(
            self.elasticity * weights["elasticity"]
            + self.position * weights["position"]
            + self.urgency * weights["urgency"]
            + self.data_quality * weights["data_quality"],
            4,
        )


class AnalystOutput(BaseModel):
    """
    Analyst's scored interpretation of market conditions for one product.

    Contract:
    - MUST consume a valid ScoutOutput (pass product_id + scouted_at through)
    - MUST produce elasticity_estimate
    - MUST produce confidence decomposition (all four components)
    - MUST produce urgency assessment
    - MUST produce recommended_direction
    - SHOULD produce sentiment_score if Scout provided sentiment data
    - MUST NOT produce a specific price — that's Strategist's job
    """

    # Traceability (carried from Scout)
    product_id: UUID
    scout_scouted_at: datetime = Field(
        description="When Scout gathered the data. For staleness detection.",
    )
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Elasticity analysis (→ feeds Strategist magnitude)
    elasticity: ElasticityEstimate

    # Confidence decomposition (→ feeds outcome calibration)
    confidence: ConfidenceDecomposition

    # Urgency assessment (→ feeds Strategist timing)
    urgency_level: UrgencyLevel
    urgency_score: float = Field(
        ge=0.0,
        le=1.0,
        description="0.0 = no urgency, 1.0 = act immediately",
    )
    urgency_reasons: list[str] = Field(
        default_factory=list,
        description="['competitor_undercut_15%', 'negative_sentiment_spike', ...]",
    )

    # Sentiment interpretation
    sentiment_score: float | None = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="Analyst's weighted sentiment. None if no social data from Scout.",
    )
    sentiment_impact: str | None = Field(
        default=None,
        description="'supports_increase', 'suggests_decrease', 'neutral', 'crisis_override'",
    )

    # Market position analysis
    competitive_position_index: float = Field(
        ge=0.0,
        le=1.0,
        description="From Scout, possibly adjusted. 0.0 = cheapest, 1.0 = most expensive.",
    )
    market_pressure: str | None = Field(
        default=None,
        description="'underpriced', 'fairly_priced', 'overpriced', 'no_data'",
    )

    # Direction recommendation (WHAT to do, not HOW MUCH)
    recommended_direction: PriceDirection
    direction_reasoning: str = Field(
        description="Plain-text explanation. Stored for audit trail.",
    )

    # Data quality pass-through (for Strategist guardrails)
    data_completeness: float = Field(ge=0.0, le=1.0)
    competitor_count: int = Field(ge=0)

    # Metadata
    analyst_version: str = "1.0"
    processing_time_ms: int | None = None
    model_used: str = Field(
        default="gemini-2.0-flash",
        description="Which LLM/model produced this analysis",
    )

    def to_evidence(self) -> dict:
        """Serialize for JSONB storage on RecommendationOutcome.analyst_evidence."""
        return self.model_dump(mode="json")
