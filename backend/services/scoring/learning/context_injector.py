"""
Context Injector — Tier 1 immediate feedback for agent context.

Before every recommendation, the system should know:
  - How well past recommendations performed in this category
  - What confidence bands correlate with positive outcomes
  - Whether merchants tend to modify recommendations (and how)
  - What magnitude of changes works best

This file builds two outputs from cached CategoryFeatures:

  1. agent_context_string: Human-readable paragraph injected into
     Strategist/Analyst prompts so the LLM reasons with historical data.

  2. scoring_context: Structured dict consumed by the ScoringEngine
     to adjust behavior (e.g., merchant_bias in ProductContext).

Both are computed from CategoryFeatures (pre-computed weekly by
feature_engineer.py). This file does NO database queries — it's
a pure transformation layer. The Celery task caches CategoryFeatures
and this injects them at recommendation time.

Phase 3 Intelligence Environment — Block A, File 3.

Place at: backend/services/scoring/learning/context_injector.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Optional


# ──────────────────────────────────────────────────────────
# SCORING CONTEXT: Structured data for the deterministic engine
# ──────────────────────────────────────────────────────────

@dataclass
class ScoringContext:
    """
    Structured context consumed by ScoringEngine at recommendation time.

    These fields influence scoring behavior:
    - merchant_bias: injected into ProductContext.merchant_bias
    - suggested_magnitude_cap: if best historical magnitude is known,
      suggest the engine not exceed it
    - confidence_calibration_factor: if past high-confidence recs
      underperformed, scale down confidence
    - data_quality_bonus: if this category has rich outcome data,
      boost the data_quality component of confidence
    """

    category: str

    # ── Merchant behavior adjustments ──
    merchant_bias: float = 0.0
    """Signed bias: >0 means merchant tends to increase beyond recommendation,
    <0 means they scale down. Used as ProductContext.merchant_bias."""

    merchant_acceptance_rate: float = 0.0
    """Historical acceptance rate (accepted + modified) / total.
    Low rate may indicate recommendations are too aggressive."""

    # ── Magnitude guidance ──
    suggested_magnitude_cap: Optional[float] = None
    """If historical data shows a sweet spot, suggest max magnitude.
    None = no suggestion (use default guardrails)."""

    best_performing_magnitude: Optional[str] = None
    """Label of the magnitude bucket with best avg revenue lift.
    e.g., '2-5%'. Informational for agent context."""

    # ── Confidence adjustments ──
    confidence_calibration_factor: float = 1.0
    """Multiply raw confidence by this factor. <1.0 if historical
    high-confidence recs underperformed. Range [0.5, 1.5]."""

    data_quality_bonus: float = 0.0
    """Added to the data_quality component of confidence.
    Range [0.0, 0.2]. Higher when category has rich outcome data."""

    # ── Performance summary ──
    avg_revenue_lift_pct: Optional[float] = None
    positive_outcome_rate: float = 0.0
    n_historical_outcomes: int = 0

    # ── Metadata ──
    features_computed_at: Optional[datetime] = None
    is_stale: bool = False
    """True if features are older than 14 days."""


# ──────────────────────────────────────────────────────────
# CONTEXT INJECTOR
# ──────────────────────────────────────────────────────────

# Thresholds for contextual adjustments
_MIN_OUTCOMES_FOR_CONTEXT = 5        # Need at least 5 outcomes to inject context
_MIN_OUTCOMES_FOR_CALIBRATION = 10   # Need 10+ for confidence calibration
_STALE_DAYS = 14                     # Features older than this are flagged
_HIGH_ACCEPTANCE = 0.70              # Above = "merchants trust recommendations"
_LOW_ACCEPTANCE = 0.40               # Below = "merchants often reject/modify"


class ContextInjector:
    """
    Transforms cached CategoryFeatures into actionable context.

    Usage at recommendation time:

        injector = ContextInjector()

        # Get structured context for scoring engine
        scoring_ctx = injector.build_scoring_context(category_features)

        # Get text context for agent prompts
        agent_text = injector.build_agent_context(category_features)

        # Or get both at once
        scoring_ctx, agent_text = injector.build(category_features)

    The CategoryFeatures input comes from a cache (Redis/in-memory)
    that's refreshed weekly by batch_tasks.py.
    """

    def build(
        self,
        features,  # CategoryFeatures (duck-typed)
        merchant_id: Optional[str] = None,
    ) -> tuple[ScoringContext, str]:
        """
        Build both scoring context and agent context string.

        Args:
            features: CategoryFeatures from feature_engineer.py
            merchant_id: Optional merchant ID for personalized context

        Returns:
            (ScoringContext, agent_context_string)
        """
        scoring = self.build_scoring_context(features)
        agent = self.build_agent_context(features, merchant_id)
        return scoring, agent

    def build_scoring_context(
        self,
        features,  # CategoryFeatures
    ) -> ScoringContext:
        """
        Build structured context for the deterministic scoring engine.

        This context adjusts engine behavior based on historical performance.
        """
        if features is None or features.n_outcomes < _MIN_OUTCOMES_FOR_CONTEXT:
            return ScoringContext(
                category=features.category if features else "unknown",
                n_historical_outcomes=features.n_outcomes if features else 0,
            )

        ctx = ScoringContext(
            category=features.category,
            n_historical_outcomes=features.n_outcomes,
            features_computed_at=features.computed_at,
        )

        # ── Staleness check ──
        if features.computed_at:
            age_days = (datetime.now(UTC) - features.computed_at).total_seconds() / 86400
            ctx.is_stale = age_days > _STALE_DAYS

        # ── Merchant bias from modification patterns ──
        ctx.merchant_bias = self._compute_merchant_bias(features)
        ctx.merchant_acceptance_rate = features.acceptance_rate

        # ── Magnitude guidance ──
        ctx.best_performing_magnitude = features.best_magnitude_bucket
        ctx.suggested_magnitude_cap = self._compute_magnitude_cap(features)

        # ── Confidence calibration ──
        ctx.confidence_calibration_factor = self._compute_calibration_factor(features)
        ctx.data_quality_bonus = self._compute_data_quality_bonus(features)

        # ── Performance summary ──
        ctx.avg_revenue_lift_pct = features.mean_revenue_lift_pct
        ctx.positive_outcome_rate = features.positive_outcome_rate

        return ctx

    def build_agent_context(
        self,
        features,  # CategoryFeatures
        merchant_id: Optional[str] = None,
    ) -> str:
        """
        Build a human-readable context string for LLM agent prompts.

        This paragraph gets injected into the Strategist's system prompt
        so it can reason about historical performance.

        Returns empty string if insufficient data.
        """
        if features is None or features.n_outcomes < _MIN_OUTCOMES_FOR_CONTEXT:
            return ""

        parts = []
        cat = features.category.replace("_", " ").title()

        # ── Opening: category performance summary ──
        parts.append(
            f"Historical pricing intelligence for {cat} "
            f"(based on {features.n_outcomes} measured outcomes):"
        )

        # ── Revenue performance ──
        if features.mean_revenue_lift_pct is not None:
            direction = "positive" if features.mean_revenue_lift_pct > 0 else "negative"
            parts.append(
                f"Past recommendations produced an average "
                f"{abs(features.mean_revenue_lift_pct):.1f}% {direction} revenue impact. "
                f"{features.positive_outcome_rate:.0%} of acted-on recommendations "
                f"resulted in revenue improvement."
            )

        # ── Confidence band insights ──
        confidence_insight = self._format_confidence_insight(features)
        if confidence_insight:
            parts.append(confidence_insight)

        # ── Acceptance patterns ──
        parts.append(
            f"Merchant acceptance rate: {features.acceptance_rate:.0%} "
            f"({features.accepted_rate:.0%} accepted as-is, "
            f"{features.modified_rate:.0%} modified, "
            f"{features.rejected_rate:.0%} rejected)."
        )

        # ── Modification patterns ──
        if features.mean_modification_ratio is not None and features.modified_rate > 0:
            if features.mean_modification_ratio < 0.8:
                parts.append(
                    f"When merchants modify recommendations, they typically "
                    f"implement {features.mean_modification_ratio:.0%} of the "
                    f"suggested change — consider more conservative suggestions."
                )
            elif features.mean_modification_ratio > 1.2:
                parts.append(
                    f"Merchants tend to amplify recommendations to "
                    f"{features.mean_modification_ratio:.0%} of the suggested change "
                    f"— there may be room for more aggressive pricing."
                )

        # ── Magnitude guidance ──
        if features.best_magnitude_bucket:
            parts.append(
                f"Price changes in the {features.best_magnitude_bucket} range "
                f"have historically produced the best revenue outcomes."
            )

        # ── Elasticity insight ──
        if features.mean_observed_elasticity is not None:
            ped = features.mean_observed_elasticity
            if abs(ped) > 2.0:
                elasticity_desc = "highly price-sensitive"
            elif abs(ped) > 1.0:
                elasticity_desc = "moderately price-sensitive"
            else:
                elasticity_desc = "relatively price-insensitive"
            parts.append(
                f"Observed demand elasticity: {ped:.2f} "
                f"(market is {elasticity_desc} in this category)."
            )

        # ── Margin impact warning ──
        if features.mean_margin_delta is not None and features.mean_margin_delta < -0.02:
            parts.append(
                f"Warning: past recommendations have reduced margins by "
                f"an average of {abs(features.mean_margin_delta):.1%}. "
                f"Prioritize margin-protective strategies."
            )

        return " ".join(parts)

    def build_minimal_context(
        self,
        features,  # CategoryFeatures
    ) -> str:
        """
        Build a one-line context summary for logging/debugging.

        Always returns a string (never empty).
        """
        if features is None:
            return "No historical data available."

        if features.n_outcomes < _MIN_OUTCOMES_FOR_CONTEXT:
            return (
                f"{features.category}: {features.n_outcomes} outcomes "
                f"(below {_MIN_OUTCOMES_FOR_CONTEXT} threshold for context injection)."
            )

        lift = features.mean_revenue_lift_pct
        lift_str = f"{lift:+.1f}%" if lift is not None else "unmeasured"

        return (
            f"{features.category}: {features.n_outcomes} outcomes, "
            f"acceptance={features.acceptance_rate:.0%}, "
            f"avg_lift={lift_str}, "
            f"positive_rate={features.positive_outcome_rate:.0%}"
        )

    # ──────────────────────────────────────────────
    # INTERNAL: Scoring adjustments
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_merchant_bias(features) -> float:
        """
        Compute merchant_bias from modification patterns.

        Positive = merchants tend to increase beyond recommendation.
        Negative = merchants tend to reduce the change.
        Zero = no pattern or insufficient data.
        """
        if features.modification_direction_bias == 0 or features.modified_rate < 0.05:
            return 0.0

        # Scale bias: direction_bias is in raw percentage terms
        # Clamp to [-0.10, 0.10] to prevent extreme adjustments
        bias = max(-0.10, min(0.10, features.modification_direction_bias))
        return round(bias, 4)

    @staticmethod
    def _compute_magnitude_cap(features) -> Optional[float]:
        """
        Suggest a magnitude cap based on which bucket performs best.

        Returns the upper bound of the best-performing bucket,
        or None if insufficient data.
        """
        if not features.best_magnitude_bucket:
            return None

        # Map bucket labels to upper bounds
        bucket_caps = {
            "0-2%": 0.02,
            "2-5%": 0.05,
            "5-8%": 0.08,
            "8-10%": 0.10,
            "10%+": None,  # No cap for 10%+
        }

        return bucket_caps.get(features.best_magnitude_bucket)

    @staticmethod
    def _compute_calibration_factor(features) -> float:
        """
        Compute confidence calibration factor from band performance.

        If high-confidence recommendations underperform low-confidence
        ones, scale down confidence. If high outperforms low, scale up.

        Returns factor in [0.5, 1.5].
        """
        if features.n_outcomes < _MIN_OUTCOMES_FOR_CALIBRATION:
            return 1.0  # Not enough data

        bands = features.confidence_band_performance
        if not bands:
            return 1.0

        # Compare high-confidence (0.7+) vs low-confidence (<0.5) performance
        high_bands = [b for b in bands if b.band_lower >= 0.7 and b.count >= 2]
        low_bands = [b for b in bands if b.band_upper <= 0.5 and b.count >= 2]

        if not high_bands or not low_bands:
            return 1.0  # Insufficient per-band data

        high_lift = sum(b.avg_revenue_lift_pct * b.count for b in high_bands) / sum(b.count for b in high_bands)
        low_lift = sum(b.avg_revenue_lift_pct * b.count for b in low_bands) / sum(b.count for b in low_bands)

        # If high-confidence recs do worse than low-confidence, scale down
        if high_lift < low_lift and low_lift > 0:
            # Factor proportional to how much worse
            ratio = high_lift / low_lift if low_lift != 0 else 1.0
            factor = max(0.5, ratio)
        elif high_lift > low_lift:
            # High confidence is validated — slight boost
            factor = min(1.5, 1.0 + (high_lift - low_lift) / 100)
        else:
            factor = 1.0

        return round(factor, 3)

    @staticmethod
    def _compute_data_quality_bonus(features) -> float:
        """
        Compute a data quality bonus based on outcome richness.

        More outcomes + higher impact-data coverage = higher bonus.
        Range [0.0, 0.2].
        """
        if features.n_outcomes < _MIN_OUTCOMES_FOR_CONTEXT:
            return 0.0

        # Score based on volume (max 0.1)
        volume_score = min(0.1, features.n_outcomes / 200)

        # Score based on impact coverage (max 0.1)
        coverage_score = features.pct_with_impact_data * 0.1

        return round(volume_score + coverage_score, 4)

    # ──────────────────────────────────────────────
    # INTERNAL: Text formatting
    # ──────────────────────────────────────────────

    @staticmethod
    def _format_confidence_insight(features) -> Optional[str]:
        """Format confidence band performance as a readable insight."""
        bands = features.confidence_band_performance
        if not bands:
            return None

        # Find the best-performing band (by avg_revenue_lift)
        bands_with_data = [b for b in bands if b.count >= 2]
        if not bands_with_data:
            return None

        best = max(bands_with_data, key=lambda b: b.avg_revenue_lift_pct)
        worst = min(bands_with_data, key=lambda b: b.avg_revenue_lift_pct)

        if best.avg_revenue_lift_pct <= 0:
            return None  # No positive bands

        parts = []
        parts.append(
            f"Recommendations with confidence {best.band_label} "
            f"produced the best results ({best.avg_revenue_lift_pct:+.1f}% revenue lift, "
            f"n={best.count})."
        )

        if worst.avg_revenue_lift_pct < 0:
            parts.append(
                f"Confidence band {worst.band_label} showed negative impact "
                f"({worst.avg_revenue_lift_pct:+.1f}%)."
            )

        return " ".join(parts)
    


    