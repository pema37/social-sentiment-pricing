"""
Analyst Feedback — Backward learning: outcomes → scoring weight adjustments.

When the scoring engine consistently over- or under-weights a component,
outcomes reveal the pattern. This module:

  1. Correlates each scoring component with outcome success/failure
  2. Identifies which components are predictive vs noisy
  3. Recommends weight adjustments for ScoreFusion
  4. Detects systematic bias (e.g., urgency driving bad recommendations)

The output is consumed by:
  - The weekly learning cycle (auto-adjust weights per category)
  - Admin dashboards (manual review before applying changes)
  - calibrator.py (File 11) for confidence calibration

Phase 3 Intelligence Environment — Block C, File 10.

Place at: backend/services/scoring/learning/analyst_feedback.py
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

# ──────────────────────────────────────────────────────────
# INPUT: Outcome records with component scores
# ──────────────────────────────────────────────────────────


@dataclass
class OutcomeWithComponents:
    """
    Outcome record enriched with the scoring engine's component outputs.

    These are the individual scores that ScoreFusion combined into the
    final confidence_score. By tracking which components were high/low
    for successful vs failed recommendations, we learn which components
    are actually predictive.

    The component scores come from the recommendation metadata JSONB
    column in pricing_recommendations (set by engine.py at scoring time).
    """

    recommendation_id: str
    category: str

    # ── Outcome ──
    action: str = "unknown"
    revenue_delta_pct: float | None = None

    # ── Final confidence ──
    confidence_score: float = 0.5

    # ── Component scores (0-1 each) ──
    elasticity_score: float = 0.5
    position_score: float = 0.5
    urgency_score: float = 0.5
    data_quality_score: float = 0.5

    # ── Current weights used ──
    elasticity_weight: float = 0.30
    position_weight: float = 0.25
    urgency_weight: float = 0.20
    data_quality_weight: float = 0.25

    @property
    def was_successful(self) -> bool:
        acted_on = self.action in ("accepted", "modified")
        positive = self.revenue_delta_pct is not None and self.revenue_delta_pct > 0
        return acted_on and positive

    @property
    def was_failure(self) -> bool:
        if self.action in ("rejected", "ignored"):
            return True
        if self.action in ("accepted", "modified"):
            return self.revenue_delta_pct is not None and self.revenue_delta_pct < 0
        return False

    @property
    def component_scores(self) -> dict[str, float]:
        return {
            "elasticity": self.elasticity_score,
            "position": self.position_score,
            "urgency": self.urgency_score,
            "data_quality": self.data_quality_score,
        }

    @property
    def component_weights(self) -> dict[str, float]:
        return {
            "elasticity": self.elasticity_weight,
            "position": self.position_weight,
            "urgency": self.urgency_weight,
            "data_quality": self.data_quality_weight,
        }


# ──────────────────────────────────────────────────────────
# OUTPUT: Weight adjustment recommendations
# ──────────────────────────────────────────────────────────


@dataclass
class ComponentAnalysis:
    """Analysis of one scoring component's predictive power."""

    component: str
    """Component name: elasticity, position, urgency, data_quality."""

    current_weight: float
    """Current weight in ScoreFusion."""

    # ── Predictive power ──
    success_mean: float = 0.0
    """Mean component score for successful outcomes."""

    failure_mean: float = 0.0
    """Mean component score for failed outcomes."""

    separation: float = 0.0
    """success_mean - failure_mean. Positive = component predicts success.
    Negative = component anti-predicts (high score → worse outcomes)."""

    correlation_with_revenue: float | None = None
    """Pearson r between component score and revenue_delta_pct.
    Positive = higher score → better outcomes."""

    # ── Recommendation ──
    recommended_weight: float | None = None
    """Suggested new weight. None = no change recommended."""

    weight_delta: float = 0.0
    """recommended - current. Positive = increase weight."""

    reasoning: str = ""


@dataclass
class WeightAdjustmentRecommendation:
    """Complete weight adjustment recommendation for a category."""

    category: str
    n_outcomes: int
    n_successes: int
    n_failures: int

    component_analyses: list[ComponentAnalysis]
    """Per-component analysis."""

    recommended_weights: dict[str, float]
    """Recommended new weights (normalized to sum to 1.0)."""

    current_weights: dict[str, float]
    """Current weights for comparison."""

    max_weight_change: float = 0.0
    """Largest absolute change in any component weight."""

    should_apply: bool = False
    """True if the recommendation is strong enough to auto-apply."""

    apply_reason: str = ""
    """Why should/shouldn't apply."""

    @property
    def summary(self) -> str:
        changes = []
        for comp, new_w in self.recommended_weights.items():
            old_w = self.current_weights.get(comp, 0)
            delta = new_w - old_w
            if abs(delta) > 0.005:
                changes.append(f"{comp}: {old_w:.0%}→{new_w:.0%}")
        change_str = ", ".join(changes) if changes else "no changes"
        return f"{self.category}: {self.n_outcomes} outcomes | {change_str} | apply={self.should_apply}"


@dataclass
class AnalystFeedbackReport:
    """Complete output from one analyst feedback cycle."""

    analyzed_at: datetime
    total_outcomes: int
    category_recommendations: list[WeightAdjustmentRecommendation]

    @property
    def categories_with_changes(self) -> list[WeightAdjustmentRecommendation]:
        return [r for r in self.category_recommendations if r.should_apply]

    @property
    def summary(self) -> str:
        n_apply = len(self.categories_with_changes)
        return (
            f"AnalystFeedback: {self.total_outcomes} outcomes, "
            f"{len(self.category_recommendations)} categories analyzed, "
            f"{n_apply} with recommended changes"
        )


# ──────────────────────────────────────────────────────────
# ANALYST FEEDBACK ANALYZER
# ──────────────────────────────────────────────────────────

_COMPONENTS = ["elasticity", "position", "urgency", "data_quality"]
_MIN_OUTCOMES = 10  # Minimum outcomes per category
_MIN_PER_GROUP = 3  # Min successes AND failures needed
_SEPARATION_THRESHOLD = 0.05  # Component must separate success/fail by this much
_MAX_SINGLE_WEIGHT = 0.50  # No component can exceed 50%
_MIN_SINGLE_WEIGHT = 0.10  # No component can drop below 10%
_AUTO_APPLY_THRESHOLD = 0.04  # Max single weight change for auto-apply


class AnalystFeedbackAnalyzer:
    """
    Analyzes scoring component predictiveness from outcome data.

    Pure Python analysis, no DB queries. Produces weight adjustment
    recommendations consumed by the learning cycle or admin review.

    Usage:
        analyzer = AnalystFeedbackAnalyzer()
        report = analyzer.analyze(outcomes)
        for rec in report.categories_with_changes:
            apply_weight_update(rec.category, rec.recommended_weights)
    """

    def analyze(
        self,
        outcomes: Sequence[OutcomeWithComponents],
    ) -> AnalystFeedbackReport:
        """
        Analyze outcomes and produce weight adjustment recommendations.
        """
        now = datetime.now(UTC)

        if not outcomes:
            return AnalystFeedbackReport(
                analyzed_at=now,
                total_outcomes=0,
                category_recommendations=[],
            )

        # Group by category
        by_cat: dict[str, list[OutcomeWithComponents]] = defaultdict(list)
        for o in outcomes:
            by_cat[o.category].append(o)

        recommendations = []
        for category, records in by_cat.items():
            rec = self._analyze_category(category, records)
            if rec is not None:
                recommendations.append(rec)

        return AnalystFeedbackReport(
            analyzed_at=now,
            total_outcomes=len(outcomes),
            category_recommendations=recommendations,
        )

    def _analyze_category(
        self,
        category: str,
        records: list[OutcomeWithComponents],
    ) -> WeightAdjustmentRecommendation | None:
        """Analyze one category and produce weight recommendations."""

        successes = [r for r in records if r.was_successful]
        failures = [r for r in records if r.was_failure]

        if len(records) < _MIN_OUTCOMES:
            return None
        if len(successes) < _MIN_PER_GROUP or len(failures) < _MIN_PER_GROUP:
            return None

        # Get current weights from the records (should be uniform within category)
        current_weights = records[0].component_weights

        # ── Analyze each component ──
        analyses = []
        for comp in _COMPONENTS:
            analysis = self._analyze_component(comp, successes, failures, records, current_weights.get(comp, 0.25))
            analyses.append(analysis)

        # ── Compute recommended weights ──
        recommended = self._compute_recommended_weights(analyses, current_weights)

        # ── Determine if we should auto-apply ──
        max_change = round(max(abs(recommended.get(c, 0) - current_weights.get(c, 0)) for c in _COMPONENTS), 4)

        should_apply = max_change > 0.005 and max_change <= _AUTO_APPLY_THRESHOLD
        apply_reason = self._get_apply_reason(max_change, analyses)

        return WeightAdjustmentRecommendation(
            category=category,
            n_outcomes=len(records),
            n_successes=len(successes),
            n_failures=len(failures),
            component_analyses=analyses,
            recommended_weights=recommended,
            current_weights=current_weights,
            max_weight_change=round(max_change, 4),
            should_apply=should_apply,
            apply_reason=apply_reason,
        )

    def _analyze_component(
        self,
        component: str,
        successes: list[OutcomeWithComponents],
        failures: list[OutcomeWithComponents],
        all_records: list[OutcomeWithComponents],
        current_weight: float,
    ) -> ComponentAnalysis:
        """Analyze one component's predictive power."""

        # Mean score for successes vs failures
        success_scores = [r.component_scores[component] for r in successes]
        failure_scores = [r.component_scores[component] for r in failures]

        success_mean = statistics.mean(success_scores)
        failure_mean = statistics.mean(failure_scores)
        separation = success_mean - failure_mean

        # Correlation with revenue
        corr = self._pearson_r(component, all_records)

        analysis = ComponentAnalysis(
            component=component,
            current_weight=current_weight,
            success_mean=round(success_mean, 4),
            failure_mean=round(failure_mean, 4),
            separation=round(separation, 4),
            correlation_with_revenue=round(corr, 4) if corr is not None else None,
        )

        # Generate reasoning
        if separation > _SEPARATION_THRESHOLD:
            analysis.reasoning = f"{component} predicts success (sep={separation:.3f})"
        elif separation < -_SEPARATION_THRESHOLD:
            analysis.reasoning = f"{component} anti-predicts: higher scores → worse outcomes (sep={separation:.3f})"
        else:
            analysis.reasoning = f"{component} shows weak predictive signal (sep={separation:.3f})"

        return analysis

    def _compute_recommended_weights(
        self,
        analyses: list[ComponentAnalysis],
        current_weights: dict[str, float],
    ) -> dict[str, float]:
        """
        Compute recommended weights based on component predictiveness.

        Strategy: weight proportional to predictive power (separation),
        with dampening to prevent drastic changes.
        """
        # Compute raw predictive scores (clipped to non-negative)
        raw_scores = {}
        for a in analyses:
            # Use separation + correlation signal
            sep_signal = max(0, a.separation)
            corr_signal = max(0, a.correlation_with_revenue or 0) * 0.5

            # Combined predictive score
            predictive = sep_signal + corr_signal
            raw_scores[a.component] = predictive

        # If all scores are zero, return current weights unchanged
        total_raw = sum(raw_scores.values())
        if total_raw < 0.01:
            return dict(current_weights)

        # Normalize raw scores to weights
        ideal_weights = {comp: score / total_raw for comp, score in raw_scores.items()}

        # Dampen: blend 80% current + 20% ideal (conservative adjustment)
        blended = {}
        for comp in _COMPONENTS:
            curr = current_weights.get(comp, 0.25)
            ideal = ideal_weights.get(comp, 0.25)
            blended[comp] = 0.80 * curr + 0.20 * ideal

        # Enforce bounds
        clamped = {}
        for comp, w in blended.items():
            clamped[comp] = max(_MIN_SINGLE_WEIGHT, min(_MAX_SINGLE_WEIGHT, w))

        # Re-normalize to sum to 1.0
        total = sum(clamped.values())
        normalized = {comp: round(w / total, 4) for comp, w in clamped.items()}

        # Update analyses with recommended weights
        for a in analyses:
            a.recommended_weight = normalized.get(a.component)
            a.weight_delta = round((a.recommended_weight or 0) - a.current_weight, 4)

        return normalized

    @staticmethod
    def _get_apply_reason(max_change: float, analyses: list[ComponentAnalysis]) -> str:
        """Generate human-readable reason for apply/skip decision."""
        if max_change <= 0.005:
            return "Changes too small to be meaningful"

        if max_change > _AUTO_APPLY_THRESHOLD:
            return (
                f"Max change {max_change:.1%} exceeds auto-apply threshold "
                f"({_AUTO_APPLY_THRESHOLD:.0%}). Manual review recommended."
            )

        # Summarize what's changing
        increasing = [a.component for a in analyses if (a.weight_delta or 0) > 0.005]
        decreasing = [a.component for a in analyses if (a.weight_delta or 0) < -0.005]
        parts = []
        if increasing:
            parts.append(f"increase {', '.join(increasing)}")
        if decreasing:
            parts.append(f"decrease {', '.join(decreasing)}")
        return f"Auto-apply: {'; '.join(parts)}" if parts else "No significant changes"

    @staticmethod
    def _pearson_r(
        component: str,
        records: list[OutcomeWithComponents],
    ) -> float | None:
        """
        Compute Pearson r between a component's score and revenue_delta_pct.

        Only uses records with measured revenue. Returns None if <5 pairs.
        """
        pairs = [
            (r.component_scores[component], r.revenue_delta_pct) for r in records if r.revenue_delta_pct is not None
        ]

        n = len(pairs)
        if n < 5:
            return None

        scores = [p[0] for p in pairs]
        revenues = [p[1] for p in pairs]

        mean_s = sum(scores) / n
        mean_r = sum(revenues) / n

        cov = sum((s - mean_s) * (r - mean_r) for s, r in pairs)
        var_s = sum((s - mean_s) ** 2 for s in scores)
        var_r = sum((r - mean_r) ** 2 for r in revenues)

        denom = math.sqrt(var_s * var_r)
        if denom < 1e-10:
            return 0.0

        return cov / denom

    # (End of AnalystFeedbackAnalyzer)
