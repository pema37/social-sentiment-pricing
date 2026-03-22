"""
Agent Contracts V2 — Enforced Semantic Contracts
==================================================
Phase 4 — Reasoning Protocols

Input contracts, shared types, and ContractViolation for the agent pipeline.
Output contracts are defined in their respective per-agent modules
(scout.py, analyst.py, strategist.py) and re-exported here for
backward compatibility.

Upgrades from Phase 1 agent_contracts.py:
  - Input contracts (not just output)
  - Strict validation with Field constraints
  - Provenance hashing for evidence chain tracing
  - ContractViolation exception with structured diagnostics

Location: backend/schemas/agent_contracts/contracts_v2.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .shared import compute_provenance_hash

# Re-export authoritative Output classes from per-agent modules.
# These replace the duplicate definitions that previously lived here
# (which had incompatible field names/types vs what agents actually produce).
from .analyst import AnalystOutput  # noqa: F401
from .scout import ScoutOutput  # noqa: F401
from .strategist import StrategistOutput  # noqa: F401

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


class PriceDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    HOLD = "hold"


class DataQualityLevel(StrEnum):
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


# ---------------------------------------------------------------------------
# Legacy helper types (kept for backward compatibility — no longer used by
# the authoritative Output classes but may be imported elsewhere)
# ---------------------------------------------------------------------------


class CompetitorPrice(BaseModel):
    """A single competitor price observation (legacy v2 schema)."""

    competitor_name: str = Field(min_length=1, max_length=255)
    price: float = Field(gt=0, description="Must be positive")
    currency: str = Field(default="USD", max_length=3)
    url: str | None = None
    scraped_at: datetime | None = None
    in_stock: bool = True
    shipping_cost: float | None = Field(default=None, ge=0)


class ElasticityEstimate(BaseModel):
    """Price elasticity of demand estimate with uncertainty (legacy v2 schema)."""

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
    """Competitive position index (legacy v2 schema)."""

    value: float = Field(ge=0, le=200, description="CPI = (avg_competitor / our_price) * 100")
    percentile: float = Field(ge=0, le=100, description="% of competitors priced above us")
    competitor_count: int = Field(ge=0)
    gap_magnitude: float = Field(description="Average % gap from competitors")


class UrgencyScore(BaseModel):
    """Time-pressure urgency composite (legacy v2 schema)."""

    value: float = Field(ge=0, le=1)
    components: dict[str, float] = Field(
        default_factory=dict,
        description="Breakdown: sentiment, trend_velocity, competitor_signal, inventory, search_demand",
    )


class GuardrailVerification(BaseModel):
    """Verification that all guardrails passed (legacy v2 schema)."""

    min_margin_met: bool
    max_change_respected: bool
    daily_limit_ok: bool
    cooldown_respected: bool
    margin_after: float
    guardrails_applied: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# SCOUT INPUT CONTRACT
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ANALYST INPUT CONTRACT
# ---------------------------------------------------------------------------


class AnalystInput(BaseModel):
    """
    What the Analyst receives from the Scout.

    Includes Scout's provenance hash for chain verification.
    Uses the authoritative ScoutOutput from scout.py.
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


# ---------------------------------------------------------------------------
# STRATEGIST INPUT CONTRACT
# ---------------------------------------------------------------------------


class StrategistInput(BaseModel):
    """
    What the Strategist receives from the Analyst.

    Includes both Analyst output and original Scout output for
    full evidence chain access. Uses authoritative types from
    analyst.py and scout.py.
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
