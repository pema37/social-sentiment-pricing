"""
Conflict Resolution Protocols
===============================
Phase 4 — Reasoning Protocols

When scoring signals conflict, apply deterministic business rules —
not LLM arbitration. These are testable, versionable rules that
encode institutional pricing knowledge.

Conflict scenarios from architecture doc:
  1. Elasticity says "increase" but urgency says "hold"
  2. Position shows "cheapest" but sentiment is negative
  3. High urgency + high confidence but margin floor violated
  4. Insufficient data (confidence < 0.3)
  5. Scout and Analyst scores diverge significantly

All resolution rules return a ConflictResolution with:
  - resolved_direction
  - magnitude_adjustment (multiplier)
  - confidence_penalty
  - explanation
  - requires_manual_review flag

Location: backend/schemas/agent_contracts/conflict_resolution.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resolution result types
# ---------------------------------------------------------------------------


class ConflictType(str, Enum):
    DIRECTION_DISAGREE = "direction_disagree"
    POSITION_SENTIMENT_MISMATCH = "position_sentiment_mismatch"
    MARGIN_FLOOR_VIOLATION = "margin_floor_violation"
    INSUFFICIENT_DATA = "insufficient_data"
    SCORER_DIVERGENCE = "scorer_divergence"
    EXPLORATION_OVERRIDE = "exploration_override"


@dataclass(frozen=True)
class ConflictResolution:
    """
    Result of a deterministic conflict resolution.

    All fields are immutable (frozen dataclass).
    """

    conflict_type: ConflictType
    resolved_direction: str  # "increase" | "decrease" | "hold"
    magnitude_adjustment: float  # Multiplier on original magnitude (0-1)
    confidence_penalty: float  # Subtracted from confidence (0-1)
    explanation: str  # Human-readable why
    requires_manual_review: bool  # Flag for merchant attention
    rule_version: str = "v1.0"
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The resolver
# ---------------------------------------------------------------------------


class ConflictResolver:
    """
    Applies deterministic conflict resolution rules.

    Rules are versioned, tested, and A/B testable via the
    experimentation framework. They encode institutional pricing
    knowledge — in the resolution logic, not in prompt engineering.

    Usage:
        resolver = ConflictResolver()
        resolution = resolver.resolve(scoring_signals)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        # Thresholds (configurable for experimentation)
        self._min_confidence = self._config.get("min_confidence", 0.3)
        self._high_confidence = self._config.get("high_confidence", 0.7)
        self._divergence_threshold = self._config.get("divergence_threshold", 0.4)
        self._sentiment_negative_threshold = self._config.get("sentiment_negative", -0.2)

    def resolve_all(self, signals: dict[str, Any]) -> list[ConflictResolution]:
        """
        Check all conflict scenarios and return resolutions for any that fire.

        Args:
            signals: Dict with keys:
                - elasticity_direction: "increase" | "decrease" | "hold"
                - elasticity_confidence: float (0-1)
                - urgency_direction: "increase" | "decrease" | "hold"
                - urgency_score: float (0-1)
                - position_percentile: float (0-100)
                - sentiment_score: float (-1 to +1)
                - overall_confidence: float (0-1)
                - margin_after: float
                - margin_floor: float
                - magnitude_pct: float
                - scorer_values: dict[str, float] (component scores)
                - is_exploration: bool (optional)

        Returns:
            List of ConflictResolution objects for all detected conflicts.
            Empty list = no conflicts detected.
        """
        resolutions: list[ConflictResolution] = []

        # Check each scenario
        r = self._check_direction_disagree(signals)
        if r:
            resolutions.append(r)

        r = self._check_position_sentiment_mismatch(signals)
        if r:
            resolutions.append(r)

        r = self._check_margin_floor_violation(signals)
        if r:
            resolutions.append(r)

        r = self._check_insufficient_data(signals)
        if r:
            resolutions.append(r)

        r = self._check_scorer_divergence(signals)
        if r:
            resolutions.append(r)

        if resolutions:
            logger.info(
                "[Conflict] %d conflict(s) detected: %s",
                len(resolutions),
                [r.conflict_type.value for r in resolutions],
            )

        return resolutions

    def apply_resolutions(
        self,
        original_direction: str,
        original_magnitude: float,
        original_confidence: float,
        resolutions: list[ConflictResolution],
    ) -> dict[str, Any]:
        """
        Apply all resolutions to produce final adjusted values.

        Resolution application order matters:
          1. Margin floor violations are absolute (override everything)
          2. Insufficient data next (may force hold)
          3. Direction disagreements (reduce magnitude)
          4. Sentiment mismatches (flag for review)
          5. Scorer divergence (penalize confidence)

        Returns:
            {
                "direction": str,
                "magnitude_pct": float,
                "confidence": float,
                "requires_manual_review": bool,
                "conflicts_applied": list[str],
                "explanations": list[str],
            }
        """
        direction = original_direction
        magnitude = original_magnitude
        confidence = original_confidence
        requires_review = False
        applied: list[str] = []
        explanations: list[str] = []

        # Sort by priority: margin floor > insufficient data > others
        priority_order = [
            ConflictType.MARGIN_FLOOR_VIOLATION,
            ConflictType.INSUFFICIENT_DATA,
            ConflictType.DIRECTION_DISAGREE,
            ConflictType.POSITION_SENTIMENT_MISMATCH,
            ConflictType.SCORER_DIVERGENCE,
        ]

        sorted_resolutions = sorted(
            resolutions,
            key=lambda r: (
                priority_order.index(r.conflict_type) if r.conflict_type in priority_order else len(priority_order)
            ),
        )

        for resolution in sorted_resolutions:
            direction = resolution.resolved_direction
            magnitude *= resolution.magnitude_adjustment
            confidence = max(0.0, confidence - resolution.confidence_penalty)
            if resolution.requires_manual_review:
                requires_review = True
            applied.append(resolution.conflict_type.value)
            explanations.append(resolution.explanation)

        return {
            "direction": direction,
            "magnitude_pct": round(magnitude, 2),
            "confidence": round(confidence, 4),
            "requires_manual_review": requires_review,
            "conflicts_applied": applied,
            "explanations": explanations,
        }

    # -------------------------------------------------------------------
    # Individual conflict checks
    # -------------------------------------------------------------------

    def _check_direction_disagree(self, signals: dict[str, Any]) -> ConflictResolution | None:
        """
        Scenario 1: Elasticity says "increase" but urgency says "hold" (or vice versa).

        Rule: If elasticity confidence > 0.7 AND urgency < 0.5,
              follow elasticity but reduce magnitude by 50%.
        """
        elast_dir = signals.get("elasticity_direction", "hold")
        urgency_dir = signals.get("urgency_direction", "hold")
        elast_conf = signals.get("elasticity_confidence", 0.5)
        urgency_score = signals.get("urgency_score", 0.5)

        if elast_dir == urgency_dir:
            return None  # No conflict

        if elast_dir != "hold" and urgency_dir != elast_dir:
            if elast_conf > self._high_confidence and urgency_score < 0.5:
                return ConflictResolution(
                    conflict_type=ConflictType.DIRECTION_DISAGREE,
                    resolved_direction=elast_dir,
                    magnitude_adjustment=0.5,
                    confidence_penalty=0.1,
                    explanation=(
                        f"Elasticity ({elast_dir}, conf={elast_conf:.2f}) conflicts with "
                        f"urgency ({urgency_dir}, score={urgency_score:.2f}). "
                        f"Following elasticity with 50% magnitude reduction."
                    ),
                    requires_manual_review=False,
                )
            else:
                # Neither signal is strong — hold
                return ConflictResolution(
                    conflict_type=ConflictType.DIRECTION_DISAGREE,
                    resolved_direction="hold",
                    magnitude_adjustment=0.0,
                    confidence_penalty=0.15,
                    explanation=(
                        f"Elasticity ({elast_dir}) and urgency ({urgency_dir}) disagree "
                        f"with no strong signal. Holding price."
                    ),
                    requires_manual_review=False,
                )
        return None

    def _check_position_sentiment_mismatch(self, signals: dict[str, Any]) -> ConflictResolution | None:
        """
        Scenario 2: Position shows "cheapest" but sentiment is negative.

        Rule: Hold price. Flag for manual review.
        Rationale: Negative sentiment + low price = potential quality perception problem.
        """
        position_pct = signals.get("position_percentile", 50)
        sentiment = signals.get("sentiment_score", 0)

        # "Cheapest" = position percentile < 20 (we're cheaper than 80% of competitors)
        if position_pct < 20 and sentiment < self._sentiment_negative_threshold:
            return ConflictResolution(
                conflict_type=ConflictType.POSITION_SENTIMENT_MISMATCH,
                resolved_direction="hold",
                magnitude_adjustment=0.0,
                confidence_penalty=0.2,
                explanation=(
                    f"Product is cheapest (percentile={position_pct:.0f}) but sentiment is "
                    f"negative ({sentiment:.2f}). Low price + negative sentiment suggests "
                    f"quality perception problem. Holding for manual review."
                ),
                requires_manual_review=True,
            )
        return None

    def _check_margin_floor_violation(self, signals: dict[str, Any]) -> ConflictResolution | None:
        """
        Scenario 3: Recommendation would violate margin floor.

        Rule: Set price at margin floor. Never violate. Absolute constraint.
        """
        margin_after = signals.get("margin_after")
        margin_floor = signals.get("margin_floor")

        if margin_after is None or margin_floor is None:
            return None

        if margin_after < margin_floor:
            return ConflictResolution(
                conflict_type=ConflictType.MARGIN_FLOOR_VIOLATION,
                resolved_direction="hold",
                magnitude_adjustment=0.0,
                confidence_penalty=0.0,  # Not a confidence issue
                explanation=(
                    f"Recommended price would produce margin {margin_after:.1f}% "
                    f"below floor {margin_floor:.1f}%. Price set at margin floor."
                ),
                requires_manual_review=False,
                metadata={"margin_after": margin_after, "margin_floor": margin_floor},
            )
        return None

    def _check_insufficient_data(self, signals: dict[str, Any]) -> ConflictResolution | None:
        """
        Scenario 4: Insufficient data (confidence < 0.3).

        Rule: Recommend "hold" with explanation. Suggest data collection actions.
        """
        confidence = signals.get("overall_confidence", 0.5)

        if confidence < self._min_confidence:
            return ConflictResolution(
                conflict_type=ConflictType.INSUFFICIENT_DATA,
                resolved_direction="hold",
                magnitude_adjustment=0.0,
                confidence_penalty=0.0,
                explanation=(
                    f"Overall confidence {confidence:.2f} is below minimum threshold "
                    f"{self._min_confidence}. Insufficient data for a reliable "
                    f"recommendation. Suggest: add more competitor tracking, "
                    f"wait for more sales data, or enable sentiment analysis."
                ),
                requires_manual_review=True,
            )
        return None

    def _check_scorer_divergence(self, signals: dict[str, Any]) -> ConflictResolution | None:
        """
        Scenario 5: Component scores diverge significantly.

        Rule: If max - min component score > threshold, penalize confidence.
        High divergence means scorers disagree on the situation.
        """
        scorer_values = signals.get("scorer_values", {})
        if len(scorer_values) < 2:
            return None

        values = list(scorer_values.values())
        max_val = max(values)
        min_val = min(values)
        spread = max_val - min_val

        if spread > self._divergence_threshold:
            high_scorer = max(scorer_values, key=scorer_values.get)  # type: ignore
            low_scorer = min(scorer_values, key=scorer_values.get)  # type: ignore
            return ConflictResolution(
                conflict_type=ConflictType.SCORER_DIVERGENCE,
                resolved_direction=signals.get("elasticity_direction", "hold"),
                magnitude_adjustment=0.7,  # Reduce magnitude by 30%
                confidence_penalty=spread * 0.3,  # Penalty proportional to spread
                explanation=(
                    f"Scorer divergence detected: {high_scorer}={max_val:.2f} vs "
                    f"{low_scorer}={min_val:.2f} (spread={spread:.2f}). "
                    f"Reducing magnitude and confidence."
                ),
                requires_manual_review=False,
                metadata={"scorer_values": scorer_values, "spread": spread},
            )
        return None
