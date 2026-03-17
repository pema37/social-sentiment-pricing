"""
Agent Contracts V2 — Enforced Semantic Contracts
==================================================
Phase 4 — Reasoning Protocols

Input AND output Pydantic models for Scout, Analyst, Strategist.
Validated at every agent boundary. If validation fails, the pipeline
halts with an explicit ContractViolation — not a degraded hallucination.

Upgrades from Phase 1 agent_contracts.py:
  - Input contracts (not just output)
  - Strict validation with Field constraints
  - Provenance hashing for evidence chain tracing
  - ContractViolation exception with structured diagnostics

Location: backend/schemas/agent_contracts/contracts_v2.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


class PriceDirection(str, Enum):
    INCREASE = "increase"
    DECREASE = "decrease"
    HOLD = "hold"


class DataQualityLevel(str, Enum):
    HIGH = "high"  # completeness >= 0.8
    MEDIUM = "medium"  # completeness >= 0.5
    LOW = "low"  # completeness >= 0.2
    INSUFFICIENT = "insufficient"  # completeness < 0.2


class ContractViolation(Exception):
    """
    Raised when an agent's output fails contract validation.

    Attributes:
        agent: Which agent failed (scout, analyst, strategist)
        field: Which field failed validation
        value: The invalid value
        constraint: What was expected
        raw_output: The original unvalidated dict
    """

    def __init__(self, agent: str, field: str, value: Any, constraint: str, raw_output: dict | None = None):
        self.agent = agent
        self.field = field
        self.value = value
        self.constraint = constraint
        self.raw_output = raw_output
        super().__init__(f"ContractViolation [{agent}]: field '{field}' = {value!r} violates constraint: {constraint}")

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "field": self.field,
            "value": str(self.value),
            "constraint": self.constraint,
            "has_raw_output": self.raw_output is not None,
        }


def compute_provenance_hash(data: dict) -> str:
    """
    Compute a deterministic hash of agent output for provenance chain.

    Used by downstream agents to verify they're working with the exact
    output from the upstream agent (not a stale or modified version).
    """
    canonical = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# SCOUT CONTRACTS
# ---------------------------------------------------------------------------


class CompetitorPrice(BaseModel):
    """A single competitor price observation."""

    competitor_name: str = Field(min_length=1, max_length=255)
    price: float = Field(gt=0, description="Must be positive")
    currency: str = Field(default="USD", max_length=3)
    url: str | None = None
    scraped_at: datetime | None = None
    in_stock: bool = True
    shipping_cost: float | None = Field(default=None, ge=0)


class ScoutInput(BaseModel):
    """
    What the Scout agent receives to start data collection.

    Validated BEFORE the Scout runs to catch bad requests early.
    """

    product_id: str = Field(min_length=1)
    merchant_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1, max_length=500)
    product_category: str | None = None
    current_price: float = Field(gt=0)
    target_competitors: list[str] = Field(
        default_factory=list,
        description="Specific competitors to check (optional)",
    )
    search_keywords: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Keywords for competitor discovery",
    )


class ScoutOutput(BaseModel):
    """
    Structured competitive and market data from the Scout agent.

    Every field is typed and constrained — no free-text analysis.
    The Scout observes; it does not interpret or recommend.
    """

    product_id: str
    merchant_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Competitive data
    competitor_prices: list[CompetitorPrice] = Field(default_factory=list)
    our_current_price: float = Field(gt=0)

    # Market signals (numeric, not qualitative)
    review_sentiment_score: float = Field(ge=-1, le=1, description="Aggregate sentiment -1 to +1")
    review_count_30d: int = Field(ge=0)
    search_volume_trend: float = Field(ge=-1, le=1, description="-1=declining, +1=growing")
    social_mention_count_7d: int = Field(ge=0)

    # Data quality + provenance
    data_completeness: float = Field(ge=0, le=1, description="% of target data found")
    sources_checked: list[str] = Field(min_length=0)
    sources_failed: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @property
    def data_quality_level(self) -> DataQualityLevel:
        if self.data_completeness >= 0.8:
            return DataQualityLevel.HIGH
        elif self.data_completeness >= 0.5:
            return DataQualityLevel.MEDIUM
        elif self.data_completeness >= 0.2:
            return DataQualityLevel.LOW
        return DataQualityLevel.INSUFFICIENT

    @property
    def provenance_hash(self) -> str:
        return compute_provenance_hash(self.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# ANALYST CONTRACTS
# ---------------------------------------------------------------------------


class ElasticityEstimate(BaseModel):
    """Price elasticity of demand estimate with uncertainty."""

    value: float = Field(description="PED value (typically negative)")
    confidence_interval_low: float
    confidence_interval_high: float
    sample_size: int = Field(ge=0)
    method: str = Field(default="bayesian_hierarchical")

    @field_validator("value")
    @classmethod
    def elasticity_reasonable(cls, v: float) -> float:
        if abs(v) > 10:
            raise ValueError(f"Elasticity {v} is unreasonably large (|PED| > 10)")
        return v


class PositionIndex(BaseModel):
    """Competitive position index."""

    value: float = Field(ge=0, le=200, description="CPI = (avg_competitor / our_price) * 100")
    percentile: float = Field(ge=0, le=100, description="% of competitors priced above us")
    competitor_count: int = Field(ge=0)
    gap_magnitude: float = Field(description="Average % gap from competitors")


class UrgencyScore(BaseModel):
    """Time-pressure urgency composite."""

    value: float = Field(ge=0, le=1)
    components: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown: sentiment, trend_velocity, competitor_signal, inventory, search_demand",
    )


class AnalystInput(BaseModel):
    """
    What the Analyst receives from the Scout.

    Includes Scout's provenance hash for chain verification.
    """

    scout_output: ScoutOutput
    scout_provenance_hash: str = Field(min_length=16, max_length=16)
    category_priors: dict[str, float] | None = None
    historical_outcomes: list[dict] | None = None

    @model_validator(mode="after")
    def verify_provenance(self) -> AnalystInput:
        expected = self.scout_output.provenance_hash
        if self.scout_provenance_hash != expected:
            raise ValueError(
                f"Provenance mismatch: got {self.scout_provenance_hash}, "
                f"expected {expected}. Scout output may have been modified."
            )
        return self


class AnalystOutput(BaseModel):
    """
    Computed scores from the Analyst agent.

    Scores are computed by the proprietary scoring engine (not LLM).
    The Analyst interprets signals; it does not recommend prices.
    """

    product_id: str
    merchant_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scout_output_hash: str = Field(description="Provenance: links to exact Scout output")

    # Proprietary scores (from deterministic scoring engine)
    elasticity: ElasticityEstimate
    position_index: PositionIndex
    urgency_score: UrgencyScore

    # Category context
    category_avg_price: float | None = Field(default=None, gt=0)
    category_price_range: tuple[float, float] | None = None
    category_elasticity: float | None = None

    # Signals for Strategist
    price_direction: PriceDirection
    magnitude_pct: float = Field(ge=-50, le=50)

    # Evidence chain
    reasoning_steps: list[str] = Field(min_length=1, description="Ordered logical steps")
    key_evidence: list[dict] = Field(
        default_factory=list,
        description="[{fact, source, weight}]",
    )
    confidence: float = Field(ge=0, le=1)

    # Quality warnings
    data_quality_warnings: list[str] = Field(default_factory=list)
    low_confidence_factors: list[str] = Field(default_factory=list)

    @property
    def provenance_hash(self) -> str:
        return compute_provenance_hash(self.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# STRATEGIST CONTRACTS
# ---------------------------------------------------------------------------


class GuardrailVerification(BaseModel):
    """Verification that all guardrails passed."""

    min_margin_met: bool
    max_change_respected: bool
    daily_limit_ok: bool
    cooldown_respected: bool
    margin_after: float
    guardrails_applied: list[str] = Field(default_factory=list)


class StrategistInput(BaseModel):
    """
    What the Strategist receives from the Analyst.

    Includes both Analyst output and original Scout output for
    full evidence chain access.
    """

    analyst_output: AnalystOutput
    analyst_provenance_hash: str = Field(min_length=16, max_length=16)
    scout_output: ScoutOutput
    merchant_preferences: dict[str, Any] | None = None
    experiment_overrides: dict[str, Any] | None = None

    @model_validator(mode="after")
    def verify_provenance(self) -> StrategistInput:
        expected = self.analyst_output.provenance_hash
        if self.analyst_provenance_hash != expected:
            raise ValueError(
                f"Provenance mismatch: got {self.analyst_provenance_hash}, "
                f"expected {expected}. Analyst output may have been modified."
            )
        return self


class StrategistOutput(BaseModel):
    """
    Final pricing recommendation from the Strategist.

    The Strategist produces the actionable recommendation with
    guardrail verification and full evidence chain.
    """

    recommendation_id: str = Field(min_length=1)
    product_id: str
    merchant_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    analyst_output_hash: str = Field(description="Provenance chain")

    # The recommendation
    current_price: float = Field(gt=0)
    suggested_price: float = Field(gt=0)
    change_pct: float = Field(ge=-50, le=50)
    direction: PriceDirection

    # Guardrails verification
    guardrails: GuardrailVerification

    # Confidence with decomposition
    confidence: float = Field(ge=0, le=1)
    confidence_decomposition: dict[str, float] = Field(
        default_factory=dict,
        description="Per-component confidence: {elasticity, position, urgency, data_quality}",
    )

    # Evidence chain (full provenance from Scout → Analyst → Strategist)
    justification: str = Field(
        min_length=10,
        max_length=2000,
        description="Human-readable justification",
    )
    risk_factors: list[str] = Field(default_factory=list)
    evidence_chain: dict[str, Any] = Field(
        default_factory=dict,
        description="Full Scout→Analyst→Strategist evidence",
    )

    # Experiment metadata (if IE is enabled)
    experiment_arm: str | None = None
    is_exploration: bool = False
    scoring_version: str | None = None

    @field_validator("suggested_price")
    @classmethod
    def price_must_be_reasonable(cls, v: float) -> float:
        if v > 1_000_000:
            raise ValueError(f"Suggested price {v} is unreasonably high")
        return v

    @model_validator(mode="after")
    def verify_direction_matches_change(self) -> StrategistOutput:
        if self.change_pct > 0.1 and self.direction != PriceDirection.INCREASE:
            raise ValueError(f"change_pct={self.change_pct} but direction={self.direction}")
        if self.change_pct < -0.1 and self.direction != PriceDirection.DECREASE:
            raise ValueError(f"change_pct={self.change_pct} but direction={self.direction}")
        return self

    @model_validator(mode="after")
    def verify_guardrails_passed(self) -> StrategistOutput:
        g = self.guardrails
        if not g.min_margin_met:
            raise ValueError(f"Cannot recommend a price that violates margin floor. Margin after: {g.margin_after}")
        if not g.max_change_respected:
            raise ValueError(f"Price change {self.change_pct}% exceeds max allowed")
        return self

    @property
    def provenance_hash(self) -> str:
        return compute_provenance_hash(self.model_dump(mode="json"))
