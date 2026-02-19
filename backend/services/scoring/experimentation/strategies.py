"""
Strategies — Pricing strategy definitions for Thompson Sampling.

Each strategy represents a distinct pricing philosophy (an "arm" in
multi-armed bandit terms). Thompson Sampling tests these against each
other and converges on winners per category.

Strategies influence the scoring engine by overriding:
  - GuardrailConfig (max change %, margin floors)
  - Magnitude multiplier (how aggressively to act on signals)
  - Weight adjustments (which scoring components to emphasize)

Phase 3 Intelligence Environment — Block B, File 5.

Place at: backend/services/scoring/experimentation/strategies.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StrategyType(str, Enum):
    """Strategy type identifiers."""
    CONSERVATIVE = "conservative"
    ELASTICITY_OPTIMAL = "elasticity_optimal"
    COMPETITIVE = "competitive"
    PREMIUM = "premium"
    CUSTOM = "custom"


@dataclass(frozen=True)
class GuardrailOverride:
    """
    Overrides for the scoring engine's GuardrailConfig.

    Only non-None fields override the default. None means "use default."
    This allows strategies to selectively tweak guardrails without
    needing to specify everything.
    """

    max_change_pct: Optional[float] = None
    """Maximum allowed price change per recommendation (absolute).
    e.g., 0.05 = ±5%."""

    min_margin: Optional[float] = None
    """Minimum margin floor. Recommendations below this are blocked."""

    max_daily_changes: Optional[int] = None
    """Max price changes per product per day."""

    cooldown_hours: Optional[int] = None
    """Minimum hours between price changes for same product."""


@dataclass(frozen=True)
class WeightOverride:
    """
    Overrides for scoring component weights.

    The scoring engine's ScoreFusion uses default weights:
      elasticity: 0.30, position: 0.25, urgency: 0.20, data_quality: 0.25

    Strategies can shift emphasis. e.g., COMPETITIVE strategy weights
    position higher; ELASTICITY_OPTIMAL weights elasticity higher.
    """

    elasticity_weight: Optional[float] = None
    position_weight: Optional[float] = None
    urgency_weight: Optional[float] = None
    data_quality_weight: Optional[float] = None

    def to_dict(self) -> dict[str, float]:
        """Return only non-None overrides as a dict."""
        result = {}
        if self.elasticity_weight is not None:
            result["elasticity"] = self.elasticity_weight
        if self.position_weight is not None:
            result["position"] = self.position_weight
        if self.urgency_weight is not None:
            result["urgency"] = self.urgency_weight
        if self.data_quality_weight is not None:
            result["data_quality"] = self.data_quality_weight
        return result

    @property
    def is_valid(self) -> bool:
        """Check that overrides sum to 1.0 if all four are specified."""
        vals = [v for v in [
            self.elasticity_weight, self.position_weight,
            self.urgency_weight, self.data_quality_weight,
        ] if v is not None]

        if len(vals) == 4:
            return abs(sum(vals) - 1.0) < 0.01
        return True  # Partial overrides don't need to sum to 1.0


@dataclass(frozen=True)
class PricingStrategy:
    """
    A complete pricing strategy definition (Thompson Sampling arm).

    Immutable (frozen). Strategies are created once and registered.
    The bandit selects among them; the experiment_manager applies
    the selected strategy's overrides to the scoring engine.
    """

    name: str
    """Unique identifier. Used as the arm key in Thompson Sampling."""

    strategy_type: StrategyType
    """Category of strategy. Determines default behavior."""

    description: str
    """Human-readable description for dashboards and logging."""

    # ── Scoring overrides ──
    magnitude_multiplier: float = 1.0
    """Scale factor on the raw recommended price change.
    <1.0 = more conservative, >1.0 = more aggressive.
    Applied after the scoring engine computes the raw recommendation."""

    guardrail_override: GuardrailOverride = field(default_factory=GuardrailOverride)
    """Selective guardrail overrides."""

    weight_override: WeightOverride = field(default_factory=WeightOverride)
    """Selective scoring component weight overrides."""

    # ── Bandit configuration ──
    initial_alpha: float = 1.0
    """Initial α for Beta(α, β) prior. Higher = more optimistic start."""

    initial_beta: float = 19.0
    """Initial β for Beta(α, β) prior. Beta(1, 19) = 5% expected success
    rate, matching typical conversion rate baseline."""

    # ── Metadata ──
    enabled: bool = True
    """Whether this strategy is available for selection."""

    min_outcomes_to_evaluate: int = 10
    """Minimum outcomes before this strategy can be declared a winner."""

    @property
    def initial_expected_value(self) -> float:
        """Expected success rate from the prior: α / (α + β)."""
        return self.initial_alpha / (self.initial_alpha + self.initial_beta)

    def apply_magnitude(self, raw_change_pct: float) -> float:
        """
        Apply this strategy's magnitude multiplier to a raw recommendation.

        Args:
            raw_change_pct: The scoring engine's raw recommended change (e.g., 0.05)

        Returns:
            Adjusted change (e.g., 0.025 for conservative with 0.5× multiplier)
        """
        adjusted = raw_change_pct * self.magnitude_multiplier

        # Respect guardrail override if present
        if self.guardrail_override.max_change_pct is not None:
            cap = self.guardrail_override.max_change_pct
            adjusted = max(-cap, min(cap, adjusted))

        return round(adjusted, 6)


# ──────────────────────────────────────────────────────────
# DEFAULT STRATEGIES
# ──────────────────────────────────────────────────────────

CONSERVATIVE = PricingStrategy(
    name="conservative",
    strategy_type=StrategyType.CONSERVATIVE,
    description=(
        "Match market median. Small, safe changes. "
        "Prioritizes stability and merchant trust. "
        "Best for risk-averse merchants and stable markets."
    ),
    magnitude_multiplier=0.6,
    guardrail_override=GuardrailOverride(
        max_change_pct=0.05,
        cooldown_hours=48,
    ),
    weight_override=WeightOverride(
        elasticity_weight=0.25,
        position_weight=0.30,
        urgency_weight=0.15,
        data_quality_weight=0.30,
    ),
    initial_alpha=1.0,
    initial_beta=19.0,
)

ELASTICITY_OPTIMAL = PricingStrategy(
    name="elasticity_optimal",
    strategy_type=StrategyType.ELASTICITY_OPTIMAL,
    description=(
        "Follow the PED signal. Size changes proportional to demand sensitivity. "
        "Data-driven approach, requires good elasticity estimates. "
        "Best when category has reliable historical data."
    ),
    magnitude_multiplier=1.0,
    guardrail_override=GuardrailOverride(
        max_change_pct=0.08,
        cooldown_hours=24,
    ),
    weight_override=WeightOverride(
        elasticity_weight=0.40,
        position_weight=0.20,
        urgency_weight=0.20,
        data_quality_weight=0.20,
    ),
    initial_alpha=1.0,
    initial_beta=19.0,
)

COMPETITIVE = PricingStrategy(
    name="competitive",
    strategy_type=StrategyType.COMPETITIVE,
    description=(
        "Undercut competitors. Aggressive market positioning. "
        "Weights competitive position heavily. "
        "Best for commoditized products and price-sensitive buyers."
    ),
    magnitude_multiplier=1.2,
    guardrail_override=GuardrailOverride(
        max_change_pct=0.10,
        min_margin=0.10,
        cooldown_hours=12,
    ),
    weight_override=WeightOverride(
        elasticity_weight=0.20,
        position_weight=0.40,
        urgency_weight=0.25,
        data_quality_weight=0.15,
    ),
    initial_alpha=1.0,
    initial_beta=19.0,
)

PREMIUM = PricingStrategy(
    name="premium",
    strategy_type=StrategyType.PREMIUM,
    description=(
        "Price above market. Lean into brand strength and positive sentiment. "
        "Conservative changes, margin-protective. "
        "Best for strong brands, positive sentiment, inelastic demand."
    ),
    magnitude_multiplier=0.8,
    guardrail_override=GuardrailOverride(
        max_change_pct=0.05,
        min_margin=0.20,
        cooldown_hours=72,
    ),
    weight_override=WeightOverride(
        elasticity_weight=0.20,
        position_weight=0.20,
        urgency_weight=0.25,
        data_quality_weight=0.35,
    ),
    initial_alpha=1.0,
    initial_beta=19.0,
)


# ──────────────────────────────────────────────────────────
# STRATEGY REGISTRY
# ──────────────────────────────────────────────────────────

class StrategyRegistry:
    """
    Registry of available pricing strategies.

    The experiment_manager queries this to get available arms.
    Strategies can be added/removed at runtime for custom experiments.
    """

    def __init__(self):
        self._strategies: dict[str, PricingStrategy] = {}
        # Register defaults
        for strategy in [CONSERVATIVE, ELASTICITY_OPTIMAL, COMPETITIVE, PREMIUM]:
            self.register(strategy)

    def register(self, strategy: PricingStrategy) -> None:
        """Add a strategy to the registry."""
        if strategy.name in self._strategies:
            raise ValueError(f"Strategy '{strategy.name}' already registered")
        self._strategies[strategy.name] = strategy

    def unregister(self, name: str) -> PricingStrategy:
        """Remove and return a strategy."""
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' not found")
        return self._strategies.pop(name)

    def get(self, name: str) -> PricingStrategy:
        """Get a strategy by name."""
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' not found. Available: {list(self._strategies.keys())}")
        return self._strategies[name]

    def get_enabled(self) -> list[PricingStrategy]:
        """Get all enabled strategies (available for Thompson Sampling)."""
        return [s for s in self._strategies.values() if s.enabled]

    def get_all(self) -> list[PricingStrategy]:
        """Get all registered strategies."""
        return list(self._strategies.values())

    def list_names(self) -> list[str]:
        """List all strategy names."""
        return list(self._strategies.keys())

    @property
    def size(self) -> int:
        return len(self._strategies)

    def create_custom(
        self,
        name: str,
        description: str,
        magnitude_multiplier: float = 1.0,
        max_change_pct: Optional[float] = None,
        min_margin: Optional[float] = None,
        register: bool = True,
    ) -> PricingStrategy:
        """
        Create and optionally register a custom strategy.

        Convenience method for experiments that need non-default arms.
        """
        strategy = PricingStrategy(
            name=name,
            strategy_type=StrategyType.CUSTOM,
            description=description,
            magnitude_multiplier=magnitude_multiplier,
            guardrail_override=GuardrailOverride(
                max_change_pct=max_change_pct,
                min_margin=min_margin,
            ),
        )
        if register:
            self.register(strategy)
        return strategy
    

    