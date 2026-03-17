"""
Fusion Types — Enums, configs, result types, and magnitude tables.

Shared by score_fusion.py and guardrails.py.
Separated so either module can import types without circular deps.

Phase 2 Scoring Engine — Fusion data layer.

Place at: backend/services/scoring/fusion_types.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# ──────────────────────────────────────────────────────────
# ENUMS
# ──────────────────────────────────────────────────────────


class ConflictType(str, Enum):
    """Types of signal conflicts the fusion layer detects."""

    NONE = "none"
    ELASTICITY_VS_URGENCY = "elasticity_vs_urgency"
    POSITION_VS_SENTIMENT = "position_vs_sentiment"
    URGENCY_VS_MARGIN = "urgency_vs_margin"
    LOW_CONFIDENCE = "low_confidence"
    CONTRADICTORY_SIGNALS = "contradictory_signals"


class GuardrailType(str, Enum):
    """Types of guardrails that can fire."""

    MARGIN_FLOOR = "margin_floor"
    MAX_CHANGE = "max_change"
    VELOCITY_CAP = "velocity_cap"
    RATE_LIMIT = "rate_limit"


# ──────────────────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────────────────


@dataclass
class GuardrailConfig:
    """
    Guardrail parameters. Can be overridden per-merchant or per-rule.

    Defaults are conservative — suitable for new merchants.
    As confidence grows, merchants can widen these.
    """

    # Margin floor: new_price >= cost * (1 + min_margin_pct)
    min_margin_pct: float = 0.15  # 15% minimum margin

    # Max single change: |change_pct| <= max_change_pct
    max_change_pct: float = 0.10  # 10% max single price change

    # Velocity cap: total change in window <= velocity_cap_pct
    velocity_cap_pct: float = 0.20  # 20% max total change
    velocity_window_days: int = 30  # Over 30 days

    # Rate limit: max 1 change per rate_limit_hours
    rate_limit_hours: float = 24.0  # 1 change per 24h


# ──────────────────────────────────────────────────────────
# PRODUCT CONTEXT
# ──────────────────────────────────────────────────────────


@dataclass
class PriceChange:
    """A historical price change for velocity/rate limit checks."""

    old_price: float
    new_price: float
    changed_at: datetime

    @property
    def change_pct(self) -> float:
        if self.old_price == 0:
            return 0.0
        return (self.new_price - self.old_price) / self.old_price


@dataclass
class ProductContext:
    """
    Product-specific data needed for fusion.

    Provided by engine.py from the Product model and price history.
    """

    current_price: float
    cost: float | None = None  # Product cost (for margin floor)
    category: str = "unknown"

    # Recent price change history (for velocity cap and rate limit)
    recent_changes: list[PriceChange] = field(default_factory=list)

    # Merchant preference (learned from modification patterns)
    merchant_bias: float = 0.0  # -1 to 1. Negative = conservative, positive = aggressive
    auto_apply_enabled: bool = False  # If True, higher confidence required


# ──────────────────────────────────────────────────────────
# RESULT TYPES
# ──────────────────────────────────────────────────────────


@dataclass
class GuardrailResult:
    """Record of a guardrail check."""

    guardrail_type: GuardrailType
    passed: bool
    original_value: str | None = None  # What the value was before clamping
    clamped_value: str | None = None  # What it was clamped to
    reason: str = ""


@dataclass
class FusionResult:
    """
    The complete output of the score fusion layer.

    Maps to StrategistOutput fields:
      recommended_price   → recommended_price
      change_pct          → change_percent
      direction           → change_direction (PriceDirection enum)
      confidence          → confidence_score
      reasoning           → reasoning
      guardrails          → guardrails_applied (list of GuardrailCheck)
      was_clamped         → was_clamped
      raw_price           → raw_recommended_price
    """

    # The recommendation
    recommended_price: float
    change_pct: float  # Signed: positive = increase
    direction: str  # "increase", "decrease", "hold"

    # Pre-guardrail values (for traceability)
    raw_price: float  # Price before guardrail clamping
    raw_change_pct: float  # Change % before guardrail clamping
    raw_direction: str  # Direction before conflict resolution

    # Confidence
    confidence: float  # Overall 0-1
    confidence_components: dict[str, float]  # Per-component for decomposition

    # Conflict resolution
    conflicts_detected: list[ConflictType]
    conflict_resolutions: list[str]  # Human-readable resolution descriptions

    # Guardrails
    guardrails: list[GuardrailResult]
    was_clamped: bool

    # Reasoning (deterministic, human-readable)
    reasoning: str
    reasoning_steps: list[str]  # Ordered logic chain

    # Flags
    needs_manual_review: bool = False
    suggest_data_collection: bool = False


# ──────────────────────────────────────────────────────────
# MAGNITUDE TABLES
# ──────────────────────────────────────────────────────────

# Base magnitude by elasticity level (how much to change price)
# Inelastic products can tolerate larger changes.
# Elastic products need small, careful changes.
ELASTICITY_MAGNITUDE: dict[str, tuple[float, float]] = {
    # |PED| range → (base_increase_pct, base_decrease_pct)
    # Increase and decrease are different because consumer psychology
    # is asymmetric: price increases hurt more than decreases please.
    "highly_elastic": (0.02, 0.04),  # |PED| > 2.0: tiny increase, small decrease
    "elastic": (0.03, 0.05),  # |PED| 1.0-2.0: small changes
    "unit_elastic": (0.04, 0.06),  # |PED| ~ 1.0: moderate changes
    "inelastic": (0.06, 0.08),  # |PED| 0.5-1.0: larger changes OK
    "highly_inelastic": (0.08, 0.10),  # |PED| < 0.5: big changes tolerated
}

# Urgency multiplier: higher urgency → larger changes
URGENCY_MULTIPLIER: dict[str, float] = {
    "critical": 1.5,
    "high": 1.25,
    "medium": 1.0,
    "low": 0.75,
    "none": 0.5,
}

# Position-based direction bias
# If we're already overpriced, reduce the increase magnitude.
# If we're underpriced, amplify the increase magnitude.
POSITION_DIRECTION_BIAS: dict[str, dict[str, float]] = {
    "underpriced": {"increase": 1.3, "decrease": 0.5},  # Encourage increase
    "fairly_priced": {"increase": 1.0, "decrease": 1.0},  # Neutral
    "overpriced": {"increase": 0.5, "decrease": 1.3},  # Encourage decrease
    "no_data": {"increase": 0.8, "decrease": 0.8},  # Conservative
}
