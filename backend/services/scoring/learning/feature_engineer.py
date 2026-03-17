"""
Feature Engineer — Computes per-category features from outcome data.

Takes raw outcome records (from pricing_outcomes + pricing_impacts joined)
and produces CategoryFeatures that drive the Tier 2 learning loop:

  1. Observed elasticity (price change → unit change regression)
  2. Acceptance rates (accepted / modified / rejected breakdown)
  3. Revenue lift by confidence band (does higher confidence → better results?)
  4. Optimal magnitude by category (what size changes work best?)
  5. Merchant modification patterns (how do merchants adjust recommendations?)

Pure Python math. No DB dependency. No LLM calls.
The Celery task (batch_tasks.py) queries the DB and feeds rows here.

Phase 3 Intelligence Environment — Block A, File 1.

Place at: backend/services/scoring/learning/feature_engineer.py
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

# ──────────────────────────────────────────────────────────
# INPUT: Outcome records (duck-typed from DB rows)
# ──────────────────────────────────────────────────────────


@dataclass
class OutcomeRecord:
    """
    One measured recommendation outcome.

    Corresponds to a JOIN of:
      pricing_recommendations × pricing_outcomes × pricing_impacts

    The Celery task constructs these from DB rows.
    """

    # Recommendation metadata
    recommendation_id: str
    category: str
    created_at: datetime

    # What was recommended
    recommended_price: float
    original_price: float
    recommended_change_pct: float  # Signed: +0.05 = 5% increase
    confidence_score: float  # 0-1 overall confidence

    # What the merchant did
    action: str  # "accepted", "modified", "rejected", "ignored"
    actual_price_set: float | None  # None if rejected/ignored
    merchant_modified_to: float | None  # None if accepted as-is or rejected

    # Measured impact (7-day window, the primary measurement)
    revenue_before_7d: float | None = None
    revenue_after_7d: float | None = None
    revenue_delta_pct: float | None = None
    units_before_7d: int | None = None
    units_after_7d: int | None = None
    margin_before: float | None = None
    margin_after: float | None = None

    # Experiment metadata (populated by Phase 3 experiment_manager)
    strategy_arm: str | None = None  # e.g., "conservative", "competitive"
    is_exploration: bool = False  # True if from 5% holdout

    @property
    def was_acted_on(self) -> bool:
        """Merchant accepted or modified (not rejected/ignored)."""
        return self.action in ("accepted", "modified")

    @property
    def has_impact_data(self) -> bool:
        """We have measured revenue/unit outcomes."""
        return self.revenue_delta_pct is not None

    @property
    def actual_change_pct(self) -> float:
        """The actual price change that happened (vs recommended)."""
        if not self.was_acted_on or self.original_price <= 0:
            return 0.0
        price_set = self.merchant_modified_to or self.actual_price_set or self.original_price
        return (price_set - self.original_price) / self.original_price

    @property
    def modification_ratio(self) -> float | None:
        """
        How much the merchant modified the recommendation.

        1.0 = accepted as-is
        0.5 = took half the suggested change
        0.0 = ignored the direction entirely
        None = not applicable (rejected/ignored)
        """
        if self.action != "modified" or self.recommended_change_pct == 0:
            return None
        actual = self.actual_change_pct
        return actual / self.recommended_change_pct if self.recommended_change_pct != 0 else None


# ──────────────────────────────────────────────────────────
# OUTPUT: Per-category computed features
# ──────────────────────────────────────────────────────────


@dataclass
class ConfidenceBandPerformance:
    """Performance metrics for a confidence band (e.g., 0.6-0.8)."""

    band_label: str  # e.g., "0.6-0.8"
    band_lower: float
    band_upper: float
    count: int
    avg_revenue_lift_pct: float
    avg_margin_delta: float
    acceptance_rate: float  # % of recommendations acted on
    positive_outcome_rate: float  # % with revenue_delta > 0


@dataclass
class MagnitudeBucket:
    """Performance metrics for a magnitude range."""

    bucket_label: str  # e.g., "2-5%"
    bucket_lower_pct: float
    bucket_upper_pct: float
    count: int
    avg_revenue_lift_pct: float
    avg_margin_delta: float
    positive_outcome_rate: float


@dataclass
class CategoryFeatures:
    """
    Computed features for one product category.

    Consumed by:
    - prior_updater.py (observed_elasticities → Bayesian prior update)
    - context_injector.py (all fields → agent context string)
    - calibrator.py (confidence_band_performance → calibration check)
    """

    category: str
    computed_at: datetime
    n_outcomes: int  # Total outcomes analyzed

    # ── Observed elasticity ──
    observed_elasticities: list[float]  # Individual PED observations
    mean_observed_elasticity: float | None
    median_observed_elasticity: float | None
    elasticity_std: float | None
    elasticity_n: int  # How many valid elasticity observations

    # ── Acceptance rates ──
    acceptance_rate: float  # (accepted + modified) / total
    accepted_rate: float  # accepted / total
    modified_rate: float  # modified / total
    rejected_rate: float  # rejected / total
    ignored_rate: float  # ignored / total

    # ── Revenue lift ──
    mean_revenue_lift_pct: float | None
    median_revenue_lift_pct: float | None
    positive_outcome_rate: float  # % with revenue_delta > 0

    # ── Margin impact ──
    mean_margin_delta: float | None

    # ── Confidence band performance ──
    confidence_band_performance: list[ConfidenceBandPerformance]
    confidence_outcome_correlation: float | None  # Pearson r

    # ── Optimal magnitude ──
    magnitude_performance: list[MagnitudeBucket]
    best_magnitude_bucket: str | None  # Label of highest avg_revenue_lift bucket

    # ── Merchant modification patterns ──
    mean_modification_ratio: float | None  # Avg how much merchants scale recs
    modification_direction_bias: float  # >0 = merchants increase more than rec'd

    # ── Data quality ──
    pct_with_impact_data: float  # % of outcomes with measured impact
    pct_acted_on: float  # % accepted or modified


# ──────────────────────────────────────────────────────────
# FEATURE ENGINEER
# ──────────────────────────────────────────────────────────

# Confidence bands for stratified analysis
_CONFIDENCE_BANDS = [
    ("0.0-0.3", 0.0, 0.3),
    ("0.3-0.5", 0.3, 0.5),
    ("0.5-0.7", 0.5, 0.7),
    ("0.7-0.9", 0.7, 0.9),
    ("0.9-1.0", 0.9, 1.0),
]

# Magnitude buckets (absolute change %)
_MAGNITUDE_BUCKETS = [
    ("0-2%", 0.0, 0.02),
    ("2-5%", 0.02, 0.05),
    ("5-8%", 0.05, 0.08),
    ("8-10%", 0.08, 0.10),
    ("10%+", 0.10, 1.0),
]


class FeatureEngineer:
    """
    Computes per-category features from outcome records.

    Stateless. Call compute() with a batch of outcomes.
    The batch_tasks.py Celery task queries the DB for the relevant
    window (e.g., last 90 days) and passes records here.
    """

    def compute(
        self,
        outcomes: Sequence[OutcomeRecord],
    ) -> dict[str, CategoryFeatures]:
        """
        Compute features for all categories present in outcomes.

        Returns: {category_name: CategoryFeatures}
        """
        by_category: dict[str, list[OutcomeRecord]] = defaultdict(list)
        for o in outcomes:
            by_category[o.category].append(o)

        result = {}
        for cat, records in by_category.items():
            result[cat] = self._compute_category(cat, records)

        return result

    def _compute_category(
        self,
        category: str,
        records: list[OutcomeRecord],
    ) -> CategoryFeatures:
        """Compute all features for one category."""
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        n = len(records)

        # ── Observed elasticity ──
        elasticities = self._compute_elasticities(records)
        e_mean = statistics.mean(elasticities) if elasticities else None
        e_median = statistics.median(elasticities) if elasticities else None
        e_std = statistics.stdev(elasticities) if len(elasticities) >= 2 else None

        # ── Acceptance rates ──
        action_counts = defaultdict(int)
        for r in records:
            action_counts[r.action] += 1

        accepted = action_counts.get("accepted", 0)
        modified = action_counts.get("modified", 0)
        rejected = action_counts.get("rejected", 0)
        ignored = action_counts.get("ignored", 0)

        acceptance_rate = (accepted + modified) / n if n > 0 else 0.0
        accepted_rate = accepted / n if n > 0 else 0.0
        modified_rate = modified / n if n > 0 else 0.0
        rejected_rate = rejected / n if n > 0 else 0.0
        ignored_rate = ignored / n if n > 0 else 0.0

        # ── Revenue lift ──
        with_impact = [r for r in records if r.has_impact_data]
        acted_on = [r for r in records if r.was_acted_on]

        if with_impact:
            lifts = [r.revenue_delta_pct for r in with_impact]
            mean_lift = statistics.mean(lifts)
            median_lift = statistics.median(lifts)
            positive_rate = sum(1 for l in lifts if l > 0) / len(lifts)
        else:
            mean_lift = None
            median_lift = None
            positive_rate = 0.0

        # ── Margin impact ──
        margin_deltas = [
            r.margin_after - r.margin_before
            for r in with_impact
            if r.margin_before is not None and r.margin_after is not None
        ]
        mean_margin = statistics.mean(margin_deltas) if margin_deltas else None

        # ── Confidence band performance ──
        band_perf = self._compute_confidence_bands(records)
        conf_corr = self._compute_confidence_correlation(with_impact)

        # ── Magnitude performance ──
        mag_perf = self._compute_magnitude_buckets(records)
        best_bucket = self._find_best_magnitude(mag_perf)

        # ── Modification patterns ──
        mod_ratios = [r.modification_ratio for r in records if r.modification_ratio is not None]
        mean_mod_ratio = statistics.mean(mod_ratios) if mod_ratios else None

        # Direction bias: do merchants tend to scale up or down?
        direction_deltas = []
        for r in records:
            if r.action == "modified" and r.recommended_change_pct != 0:
                actual = r.actual_change_pct
                direction_deltas.append(actual - r.recommended_change_pct)
        direction_bias = statistics.mean(direction_deltas) if direction_deltas else 0.0

        return CategoryFeatures(
            category=category,
            computed_at=now,
            n_outcomes=n,
            observed_elasticities=elasticities,
            mean_observed_elasticity=e_mean,
            median_observed_elasticity=e_median,
            elasticity_std=e_std,
            elasticity_n=len(elasticities),
            acceptance_rate=round(acceptance_rate, 4),
            accepted_rate=round(accepted_rate, 4),
            modified_rate=round(modified_rate, 4),
            rejected_rate=round(rejected_rate, 4),
            ignored_rate=round(ignored_rate, 4),
            mean_revenue_lift_pct=round(mean_lift, 4) if mean_lift is not None else None,
            median_revenue_lift_pct=round(median_lift, 4) if median_lift is not None else None,
            positive_outcome_rate=round(positive_rate, 4),
            mean_margin_delta=round(mean_margin, 4) if mean_margin is not None else None,
            confidence_band_performance=band_perf,
            confidence_outcome_correlation=conf_corr,
            magnitude_performance=mag_perf,
            best_magnitude_bucket=best_bucket,
            mean_modification_ratio=round(mean_mod_ratio, 4) if mean_mod_ratio is not None else None,
            modification_direction_bias=round(direction_bias, 4),
            pct_with_impact_data=round(len(with_impact) / n, 4) if n > 0 else 0.0,
            pct_acted_on=round(len(acted_on) / n, 4) if n > 0 else 0.0,
        )

    # ──────────────────────────────────────────────
    # OBSERVED ELASTICITY
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_elasticities(
        records: list[OutcomeRecord],
    ) -> list[float]:
        """
        Compute observed PED from price changes and unit changes.

        PED = (%ΔQ / %ΔP)

        Filters:
        - Must have been acted on (accepted or modified)
        - Must have unit data (before and after)
        - Price must have actually changed (|%ΔP| > 0.5%)
        - Units before > 0 (can't compute % change from zero)
        """
        elasticities = []

        for r in records:
            if not r.was_acted_on:
                continue
            if r.units_before_7d is None or r.units_after_7d is None:
                continue
            if r.units_before_7d <= 0:
                continue

            # Actual price change (may differ from recommended if modified)
            pct_price_change = r.actual_change_pct
            if abs(pct_price_change) < 0.005:
                continue  # Price barely moved, can't measure elasticity

            # Unit change
            pct_unit_change = (r.units_after_7d - r.units_before_7d) / r.units_before_7d

            # PED = %ΔQ / %ΔP
            ped = pct_unit_change / pct_price_change

            # Sanity filter: PED should be negative (law of demand)
            # and not wildly extreme
            if ped > 1.0:
                continue  # Giffen-like, likely noise
            if ped < -10.0:
                continue  # Implausibly elastic

            elasticities.append(round(ped, 4))

        return elasticities

    # ──────────────────────────────────────────────
    # CONFIDENCE BAND PERFORMANCE
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_confidence_bands(
        records: list[OutcomeRecord],
    ) -> list[ConfidenceBandPerformance]:
        """
        Stratify outcomes by confidence band.

        This is the core data for confidence calibration:
        do higher-confidence recommendations produce better outcomes?
        """
        results = []

        for label, lower, upper in _CONFIDENCE_BANDS:
            band_records = [
                r
                for r in records
                if lower <= r.confidence_score < upper or (upper == 1.0 and r.confidence_score == 1.0)
            ]
            if not band_records:
                results.append(
                    ConfidenceBandPerformance(
                        band_label=label,
                        band_lower=lower,
                        band_upper=upper,
                        count=0,
                        avg_revenue_lift_pct=0.0,
                        avg_margin_delta=0.0,
                        acceptance_rate=0.0,
                        positive_outcome_rate=0.0,
                    )
                )
                continue

            n = len(band_records)
            acted = sum(1 for r in band_records if r.was_acted_on)

            with_impact = [r for r in band_records if r.has_impact_data]
            if with_impact:
                avg_lift = statistics.mean(r.revenue_delta_pct for r in with_impact)
                margin_deltas = [
                    r.margin_after - r.margin_before
                    for r in with_impact
                    if r.margin_before is not None and r.margin_after is not None
                ]
                avg_margin = statistics.mean(margin_deltas) if margin_deltas else 0.0
                pos_rate = sum(1 for r in with_impact if r.revenue_delta_pct > 0) / len(with_impact)
            else:
                avg_lift = 0.0
                avg_margin = 0.0
                pos_rate = 0.0

            results.append(
                ConfidenceBandPerformance(
                    band_label=label,
                    band_lower=lower,
                    band_upper=upper,
                    count=n,
                    avg_revenue_lift_pct=round(avg_lift, 4),
                    avg_margin_delta=round(avg_margin, 4),
                    acceptance_rate=round(acted / n, 4),
                    positive_outcome_rate=round(pos_rate, 4),
                )
            )

        return results

    # ──────────────────────────────────────────────
    # CONFIDENCE-OUTCOME CORRELATION
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_confidence_correlation(
        with_impact: list[OutcomeRecord],
    ) -> float | None:
        """
        Pearson r between confidence_score and revenue_delta_pct.

        Returns None if < 5 data points (insufficient for correlation).
        """
        if len(with_impact) < 5:
            return None

        confs = [r.confidence_score for r in with_impact]
        lifts = [r.revenue_delta_pct for r in with_impact]

        # Pearson r manual computation (no numpy dependency)
        n = len(confs)
        mean_c = sum(confs) / n
        mean_l = sum(lifts) / n

        cov = sum((c - mean_c) * (l - mean_l) for c, l in zip(confs, lifts)) / n
        std_c = math.sqrt(sum((c - mean_c) ** 2 for c in confs) / n)
        std_l = math.sqrt(sum((l - mean_l) ** 2 for l in lifts) / n)

        if std_c < 1e-10 or std_l < 1e-10:
            return 0.0  # No variance in one or both

        return round(cov / (std_c * std_l), 4)

    # ──────────────────────────────────────────────
    # MAGNITUDE PERFORMANCE
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_magnitude_buckets(
        records: list[OutcomeRecord],
    ) -> list[MagnitudeBucket]:
        """
        Stratify outcomes by actual change magnitude.

        Answers: what size price changes produce the best results?
        """
        results = []

        for label, lower, upper in _MAGNITUDE_BUCKETS:
            bucket_records = [
                r for r in records if r.was_acted_on and r.has_impact_data and lower <= abs(r.actual_change_pct) < upper
            ]

            if not bucket_records:
                results.append(
                    MagnitudeBucket(
                        bucket_label=label,
                        bucket_lower_pct=lower,
                        bucket_upper_pct=upper,
                        count=0,
                        avg_revenue_lift_pct=0.0,
                        avg_margin_delta=0.0,
                        positive_outcome_rate=0.0,
                    )
                )
                continue

            n = len(bucket_records)
            avg_lift = statistics.mean(r.revenue_delta_pct for r in bucket_records)
            margin_deltas = [
                r.margin_after - r.margin_before
                for r in bucket_records
                if r.margin_before is not None and r.margin_after is not None
            ]
            avg_margin = statistics.mean(margin_deltas) if margin_deltas else 0.0
            pos_rate = sum(1 for r in bucket_records if r.revenue_delta_pct > 0) / n

            results.append(
                MagnitudeBucket(
                    bucket_label=label,
                    bucket_lower_pct=lower,
                    bucket_upper_pct=upper,
                    count=n,
                    avg_revenue_lift_pct=round(avg_lift, 4),
                    avg_margin_delta=round(avg_margin, 4),
                    positive_outcome_rate=round(pos_rate, 4),
                )
            )

        return results

    @staticmethod
    def _find_best_magnitude(
        buckets: list[MagnitudeBucket],
    ) -> str | None:
        """
        Find the magnitude bucket with highest avg_revenue_lift.

        Requires min 3 observations per bucket to be considered.
        """
        eligible = [b for b in buckets if b.count >= 3]
        if not eligible:
            return None
        best = max(eligible, key=lambda b: b.avg_revenue_lift_pct)
        return best.bucket_label if best.avg_revenue_lift_pct > 0 else None
