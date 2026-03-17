"""
Strategist Agent Output Contract.

Strategist's job: Produce a specific, actionable price recommendation.
Consumes: AnalystOutput (+ merchant preferences from calibration)
Produces: The final recommendation that becomes PriceRecommendation
Stored in: strategist_evidence JSONB column on RecommendationOutcome
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .analyst import ConfidenceDecomposition
from .shared import PriceDirection


class GuardrailCheck(BaseModel):
    """Record of a guardrail that was evaluated."""

    name: str = Field(description="e.g. 'max_change_percent', 'min_price_floor', 'margin_protection'")
    passed: bool
    original_value: str | None = None
    clamped_value: str | None = None
    reason: str | None = None


class StrategistOutput(BaseModel):
    """
    Strategist's final pricing recommendation for one product.

    Contract:
    - MUST consume a valid AnalystOutput
    - MUST produce recommended_price and change_percent
    - MUST produce overall confidence_score (from Analyst's decomposition)
    - MUST apply and document all guardrail checks
    - MUST apply merchant preference_prior if available
    - MUST produce human-readable reasoning
    - SHOULD produce compare_at_price for sale display
    """

    # Traceability (carried through pipeline)
    product_id: UUID
    scout_scouted_at: datetime
    analyst_analyzed_at: datetime
    strategized_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # The recommendation (→ becomes PriceRecommendation fields)
    current_price: Decimal
    recommended_price: Decimal
    change_percent: Decimal = Field(
        description="Percentage change: positive = increase, negative = decrease",
    )
    change_direction: PriceDirection
    compare_at_price: Decimal | None = Field(
        default=None,
        description="Strike-through price for sale display (Shopify compare_at_price)",
    )

    # Confidence (→ becomes recommendation.confidence_score)
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence. From Analyst's decomposition, possibly adjusted.",
    )
    confidence_decomposition: ConfidenceDecomposition

    # Reasoning (→ becomes recommendation.reasoning + recommendation.factors)
    reasoning: str = Field(
        description="Human-readable explanation of why this price was chosen.",
    )
    factors: dict = Field(
        default_factory=dict,
        description="Structured factors dict for the recommendation.factors JSON column.",
    )

    # Guardrails applied
    guardrails_applied: list[GuardrailCheck] = Field(default_factory=list)
    was_clamped: bool = Field(
        default=False,
        description="True if any guardrail modified the raw recommendation.",
    )
    raw_recommended_price: Decimal | None = Field(
        default=None,
        description="Price before guardrails. Null if no clamping occurred.",
    )

    # Merchant preference calibration (from outcome_calibration backward learning)
    preference_prior_applied: float | None = Field(
        default=None,
        description="Scaling factor from merchant modification patterns. e.g. 0.7 = reduced by 30%.",
    )
    pre_calibration_change_percent: Decimal | None = Field(
        default=None,
        description="Change percent before preference prior was applied.",
    )

    # Category context (from outcome_benchmarks cross-merchant intelligence)
    category_benchmark_used: bool = False
    category_optimal_range: dict | None = Field(
        default=None,
        description="From get_category_benchmarks: {min, max, median} of successful changes.",
    )

    # Pipeline metadata
    pipeline_source: str = Field(
        default="full_pipeline",
        description="'full_pipeline', 'rule_based', 'crisis_override', 'manual'",
    )
    strategist_version: str = "1.0"
    processing_time_ms: int | None = None
    total_pipeline_time_ms: int | None = None
    model_used: str = Field(
        default="gemini-2.0-flash",
        description="Which LLM/model produced this recommendation",
    )

    @model_validator(mode="after")
    def validate_direction_matches(self):
        """Ensure change_percent sign matches change_direction."""
        if self.change_direction == PriceDirection.INCREASE and self.change_percent < 0:
            raise ValueError("change_percent must be positive for INCREASE direction")
        if self.change_direction == PriceDirection.DECREASE and self.change_percent > 0:
            raise ValueError("change_percent must be negative for DECREASE direction")
        if self.change_direction == PriceDirection.HOLD and abs(self.change_percent) > Decimal("0.5"):
            raise ValueError("change_percent should be near zero for HOLD direction")
        return self

    def to_evidence(self) -> dict:
        """Serialize for JSONB storage on RecommendationOutcome.strategist_evidence."""
        return self.model_dump(mode="json")

    def to_recommendation_kwargs(self) -> dict:
        """Extract fields that map to PriceRecommendation model columns."""
        return {
            "product_id": self.product_id,
            "current_price": self.current_price,
            "recommended_price": self.recommended_price,
            "change_percent": self.change_percent,
            "confidence_score": Decimal(str(self.confidence_score)),
            "reasoning": self.reasoning,
            "factors": self.factors,
        }
