"""
Drift Detector — Tier 3: model degradation detection and retraining triggers.

Monitors multiple signals for scoring model drift:
  1. Confidence-outcome correlation (primary signal)
     - When Pearson r drops below 0.3 → miscalibrated alert
     - When r drops below 0.1 → retraining trigger
  2. Acceptance rate trend (merchant trust signal)
     - Declining acceptance → merchants losing trust in recommendations
  3. Revenue lift trend (business impact signal)
     - Declining mean lift → recommendations getting worse
  4. Confidence distribution shift
     - Scoring engine producing different confidence distributions than training

Uses sliding windows: compares recent window (7d) vs baseline (30d)
to detect acute degradation. Also tracks long-term trends.

Phase 3 Intelligence Environment — Block C, File 12.

Place at: backend/services/scoring/learning/drift_detector.py
"""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Optional, Sequence


# ──────────────────────────────────────────────────────────
# DRIFT SEVERITY
# ──────────────────────────────────────────────────────────

class DriftSeverity(str, Enum):
    NONE = "none"
    LOW = "low"          # Noticeable but not actionable
    MEDIUM = "medium"    # Worth investigating
    HIGH = "high"        # Retraining recommended
    CRITICAL = "critical"  # Immediate action required


# ──────────────────────────────────────────────────────────
# INPUT: Timestamped outcome records
# ──────────────────────────────────────────────────────────

@dataclass
class DriftRecord:
    """Minimal timestamped record for drift detection."""
    recommendation_id: str
    category: str
    timestamp: datetime
    confidence_score: float
    revenue_delta_pct: Optional[float]
    action: str  # accepted, modified, rejected, ignored

    @property
    def was_successful(self) -> bool:
        return (
            self.action in ("accepted", "modified")
            and self.revenue_delta_pct is not None
            and self.revenue_delta_pct > 0
        )

    @property
    def was_acted_on(self) -> bool:
        return self.action in ("accepted", "modified")


# ──────────────────────────────────────────────────────────
# DRIFT SIGNALS
# ──────────────────────────────────────────────────────────

@dataclass
class DriftSignal:
    """One detected drift signal."""
    signal_type: str
    """Type: 'correlation_drop', 'acceptance_decline', 'lift_decline',
    'distribution_shift', 'volume_drop'."""

    severity: DriftSeverity
    current_value: float
    baseline_value: float
    delta: float
    """current - baseline. Negative = degradation."""
    description: str
    category: str


@dataclass
class DriftReport:
    """Complete drift detection report."""

    analyzed_at: datetime
    category: str
    period_start: datetime
    period_end: datetime

    # ── Window sizes ──
    recent_window_days: int
    baseline_window_days: int
    recent_count: int
    baseline_count: int

    # ── Signals ──
    signals: list[DriftSignal]

    # ── Overall assessment ──
    overall_severity: DriftSeverity
    should_retrain: bool
    should_recalibrate: bool

    @property
    def has_drift(self) -> bool:
        return self.overall_severity != DriftSeverity.NONE

    @property
    def summary(self) -> str:
        n_sig = len([s for s in self.signals if s.severity != DriftSeverity.NONE])
        return (
            f"Drift({self.category}): severity={self.overall_severity.value}, "
            f"{n_sig} signals, retrain={self.should_retrain}, "
            f"recalibrate={self.should_recalibrate}, "
            f"n_recent={self.recent_count}, n_baseline={self.baseline_count}"
        )


# ──────────────────────────────────────────────────────────
# DRIFT DETECTOR
# ──────────────────────────────────────────────────────────

_CORRELATION_ACCEPTABLE = 0.3
_CORRELATION_CRITICAL = 0.1
_MIN_WINDOW_SIZE = 10
_ACCEPTANCE_DROP_THRESHOLD = 0.10  # 10% drop is concerning
_LIFT_DROP_THRESHOLD = 1.0         # 1pp drop in mean lift
_KS_THRESHOLD = 0.15              # Kolmogorov-Smirnov statistic threshold


class DriftDetector:
    """
    Monitors scoring model performance for drift and degradation.

    Compares recent outcomes to a baseline window. When drift exceeds
    thresholds, triggers retraining and/or recalibration alerts.

    Usage:
        detector = DriftDetector()
        report = detector.detect(all_records, category='electronics')
        if report.should_retrain:
            trigger_retraining_pipeline(category)
    """

    def __init__(
        self,
        recent_window_days: int = 7,
        baseline_window_days: int = 30,
    ):
        self._recent_days = recent_window_days
        self._baseline_days = baseline_window_days
        self._history: list[DriftReport] = []

    @property
    def history(self) -> list[DriftReport]:
        return list(self._history)

    def detect(
        self,
        records: Sequence[DriftRecord],
        category: str = "all",
        reference_time: Optional[datetime] = None,
    ) -> DriftReport:
        """
        Run drift detection for a category.

        Splits records into recent vs baseline windows and compares.
        """
        now = reference_time or datetime.now(UTC)
        recent_cutoff = now - timedelta(days=self._recent_days)
        baseline_cutoff = now - timedelta(days=self._baseline_days)

        # Filter by category if not "all"
        if category != "all":
            records = [r for r in records if r.category == category]

        recent = [r for r in records if r.timestamp >= recent_cutoff]
        baseline = [r for r in records if baseline_cutoff <= r.timestamp < recent_cutoff]

        signals = []

        # Only run detection if we have enough data in both windows
        if len(recent) >= _MIN_WINDOW_SIZE and len(baseline) >= _MIN_WINDOW_SIZE:
            signals.extend(self._check_correlation(recent, baseline, category))
            signals.extend(self._check_acceptance(recent, baseline, category))
            signals.extend(self._check_lift(recent, baseline, category))
            signals.extend(self._check_distribution(recent, baseline, category))

        # Check for volume drop (need baseline only)
        if len(baseline) >= _MIN_WINDOW_SIZE:
            signals.extend(self._check_volume(recent, baseline, category))

        # ── Overall assessment ──
        overall = self._assess_overall(signals)
        should_retrain = overall in (DriftSeverity.HIGH, DriftSeverity.CRITICAL)
        should_recalibrate = overall in (DriftSeverity.MEDIUM, DriftSeverity.HIGH, DriftSeverity.CRITICAL)

        report = DriftReport(
            analyzed_at=now,
            category=category,
            period_start=baseline_cutoff,
            period_end=now,
            recent_window_days=self._recent_days,
            baseline_window_days=self._baseline_days,
            recent_count=len(recent),
            baseline_count=len(baseline),
            signals=signals,
            overall_severity=overall,
            should_retrain=should_retrain,
            should_recalibrate=should_recalibrate,
        )

        self._history.append(report)
        return report

    def detect_all_categories(
        self,
        records: Sequence[DriftRecord],
        reference_time: Optional[datetime] = None,
    ) -> list[DriftReport]:
        """Run drift detection for every category present in records."""
        categories = set(r.category for r in records)
        return [
            self.detect(records, cat, reference_time)
            for cat in sorted(categories)
        ]

    # ──────────────────────────────────────────────
    # SIGNAL DETECTORS
    # ──────────────────────────────────────────────

    def _check_correlation(
        self,
        recent: list[DriftRecord],
        baseline: list[DriftRecord],
        category: str,
    ) -> list[DriftSignal]:
        """
        Compare confidence-outcome correlation between windows.

        Primary drift signal: when confidence stops predicting outcomes.
        """
        r_recent = _pearson_r_drift(recent)
        r_baseline = _pearson_r_drift(baseline)

        if r_recent is None or r_baseline is None:
            return []

        delta = r_recent - r_baseline

        # Determine severity based on absolute recent correlation
        if r_recent < _CORRELATION_CRITICAL:
            severity = DriftSeverity.CRITICAL
        elif r_recent < _CORRELATION_ACCEPTABLE:
            severity = DriftSeverity.HIGH
        elif delta < -0.15:
            severity = DriftSeverity.MEDIUM
        elif delta < -0.05:
            severity = DriftSeverity.LOW
        else:
            severity = DriftSeverity.NONE

        return [DriftSignal(
            signal_type="correlation_drop",
            severity=severity,
            current_value=round(r_recent, 4),
            baseline_value=round(r_baseline, 4),
            delta=round(delta, 4),
            description=(
                f"Confidence-outcome correlation: "
                f"{r_baseline:.3f} → {r_recent:.3f} (Δ={delta:+.3f})"
            ),
            category=category,
        )]

    def _check_acceptance(
        self,
        recent: list[DriftRecord],
        baseline: list[DriftRecord],
        category: str,
    ) -> list[DriftSignal]:
        """Check if merchant acceptance rate is declining."""
        recent_rate = sum(1 for r in recent if r.was_acted_on) / len(recent)
        baseline_rate = sum(1 for r in baseline if r.was_acted_on) / len(baseline)
        delta = recent_rate - baseline_rate

        if delta < -_ACCEPTANCE_DROP_THRESHOLD * 2:
            severity = DriftSeverity.HIGH
        elif delta < -_ACCEPTANCE_DROP_THRESHOLD:
            severity = DriftSeverity.MEDIUM
        elif delta < -0.05:
            severity = DriftSeverity.LOW
        else:
            severity = DriftSeverity.NONE

        return [DriftSignal(
            signal_type="acceptance_decline",
            severity=severity,
            current_value=round(recent_rate, 4),
            baseline_value=round(baseline_rate, 4),
            delta=round(delta, 4),
            description=(
                f"Acceptance rate: {baseline_rate:.1%} → {recent_rate:.1%} "
                f"(Δ={delta:+.1%})"
            ),
            category=category,
        )]

    def _check_lift(
        self,
        recent: list[DriftRecord],
        baseline: list[DriftRecord],
        category: str,
    ) -> list[DriftSignal]:
        """Check if average revenue lift is declining."""
        recent_lifts = [
            r.revenue_delta_pct for r in recent
            if r.revenue_delta_pct is not None and r.was_acted_on
        ]
        baseline_lifts = [
            r.revenue_delta_pct for r in baseline
            if r.revenue_delta_pct is not None and r.was_acted_on
        ]

        if not recent_lifts or not baseline_lifts:
            return []

        recent_mean = statistics.mean(recent_lifts)
        baseline_mean = statistics.mean(baseline_lifts)
        delta = recent_mean - baseline_mean

        if delta < -_LIFT_DROP_THRESHOLD * 2:
            severity = DriftSeverity.HIGH
        elif delta < -_LIFT_DROP_THRESHOLD:
            severity = DriftSeverity.MEDIUM
        elif delta < -0.5:
            severity = DriftSeverity.LOW
        else:
            severity = DriftSeverity.NONE

        return [DriftSignal(
            signal_type="lift_decline",
            severity=severity,
            current_value=round(recent_mean, 4),
            baseline_value=round(baseline_mean, 4),
            delta=round(delta, 4),
            description=(
                f"Mean revenue lift: {baseline_mean:.2f}% → {recent_mean:.2f}% "
                f"(Δ={delta:+.2f}pp)"
            ),
            category=category,
        )]

    def _check_distribution(
        self,
        recent: list[DriftRecord],
        baseline: list[DriftRecord],
        category: str,
    ) -> list[DriftSignal]:
        """
        Check if confidence score distribution has shifted.

        Uses a simplified KS-like statistic: max absolute difference
        between cumulative distributions of confidence scores.
        """
        recent_confs = sorted(r.confidence_score for r in recent)
        baseline_confs = sorted(r.confidence_score for r in baseline)

        ks_stat = _simplified_ks(recent_confs, baseline_confs)

        if ks_stat > _KS_THRESHOLD * 2:
            severity = DriftSeverity.HIGH
        elif ks_stat > _KS_THRESHOLD:
            severity = DriftSeverity.MEDIUM
        elif ks_stat > 0.08:
            severity = DriftSeverity.LOW
        else:
            severity = DriftSeverity.NONE

        recent_mean = statistics.mean(recent_confs)
        baseline_mean = statistics.mean(baseline_confs)

        return [DriftSignal(
            signal_type="distribution_shift",
            severity=severity,
            current_value=round(recent_mean, 4),
            baseline_value=round(baseline_mean, 4),
            delta=round(ks_stat, 4),
            description=(
                f"Confidence distribution KS={ks_stat:.3f} "
                f"(mean: {baseline_mean:.3f} → {recent_mean:.3f})"
            ),
            category=category,
        )]

    def _check_volume(
        self,
        recent: list[DriftRecord],
        baseline: list[DriftRecord],
        category: str,
    ) -> list[DriftSignal]:
        """Check for significant volume drop (may indicate data pipeline issues)."""
        # Normalize to per-day rates
        recent_per_day = len(recent) / max(self._recent_days, 1)
        baseline_per_day = len(baseline) / max(self._baseline_days - self._recent_days, 1)

        if baseline_per_day < 0.5:
            return []  # Not enough baseline volume to compare

        ratio = recent_per_day / baseline_per_day if baseline_per_day > 0 else 0
        delta = ratio - 1.0  # < 0 means drop

        if ratio < 0.3:
            severity = DriftSeverity.HIGH
        elif ratio < 0.5:
            severity = DriftSeverity.MEDIUM
        elif ratio < 0.7:
            severity = DriftSeverity.LOW
        else:
            severity = DriftSeverity.NONE

        return [DriftSignal(
            signal_type="volume_drop",
            severity=severity,
            current_value=round(recent_per_day, 2),
            baseline_value=round(baseline_per_day, 2),
            delta=round(delta, 4),
            description=(
                f"Volume: {baseline_per_day:.1f}/day → {recent_per_day:.1f}/day "
                f"(ratio={ratio:.2f})"
            ),
            category=category,
        )]

    # ──────────────────────────────────────────────
    # OVERALL ASSESSMENT
    # ──────────────────────────────────────────────

    @staticmethod
    def _assess_overall(signals: list[DriftSignal]) -> DriftSeverity:
        """
        Determine overall drift severity from individual signals.

        Escalation logic:
        - Any CRITICAL signal → CRITICAL overall
        - 2+ HIGH signals → CRITICAL
        - Any HIGH signal → HIGH
        - 2+ MEDIUM signals → HIGH
        - Any MEDIUM signal → MEDIUM
        - Otherwise → max of individual severities
        """
        if not signals:
            return DriftSeverity.NONE

        severity_order = {
            DriftSeverity.NONE: 0,
            DriftSeverity.LOW: 1,
            DriftSeverity.MEDIUM: 2,
            DriftSeverity.HIGH: 3,
            DriftSeverity.CRITICAL: 4,
        }

        counts = defaultdict(int)
        for s in signals:
            counts[s.severity] += 1

        if counts[DriftSeverity.CRITICAL] > 0:
            return DriftSeverity.CRITICAL
        if counts[DriftSeverity.HIGH] >= 2:
            return DriftSeverity.CRITICAL
        if counts[DriftSeverity.HIGH] > 0:
            return DriftSeverity.HIGH
        if counts[DriftSeverity.MEDIUM] >= 2:
            return DriftSeverity.HIGH
        if counts[DriftSeverity.MEDIUM] > 0:
            return DriftSeverity.MEDIUM

        max_sev = max(signals, key=lambda s: severity_order[s.severity])
        return max_sev.severity


# ──────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────

def _pearson_r_drift(records: list[DriftRecord]) -> Optional[float]:
    """Pearson r between confidence and revenue_delta for drift records."""
    pairs = [
        (r.confidence_score, r.revenue_delta_pct)
        for r in records
        if r.revenue_delta_pct is not None
    ]
    n = len(pairs)
    if n < 5:
        return None

    cs = [p[0] for p in pairs]
    rs = [p[1] for p in pairs]
    mean_c = sum(cs) / n
    mean_r = sum(rs) / n

    cov = sum((c - mean_c) * (r - mean_r) for c, r in pairs)
    var_c = sum((c - mean_c) ** 2 for c in cs)
    var_r = sum((r - mean_r) ** 2 for r in rs)

    denom = math.sqrt(var_c * var_r)
    if denom < 1e-10:
        return 0.0
    return cov / denom


def _simplified_ks(sample_a: list[float], sample_b: list[float]) -> float:
    """
    Simplified Kolmogorov-Smirnov two-sample statistic.

    Returns max absolute difference between empirical CDFs.
    Both inputs should be sorted.
    """
    if not sample_a or not sample_b:
        return 0.0

    # Merge and compute CDFs at each point
    all_values = sorted(set(sample_a + sample_b))
    n_a = len(sample_a)
    n_b = len(sample_b)

    max_diff = 0.0
    idx_a = 0
    idx_b = 0

    for val in all_values:
        while idx_a < n_a and sample_a[idx_a] <= val:
            idx_a += 1
        while idx_b < n_b and sample_b[idx_b] <= val:
            idx_b += 1

        cdf_a = idx_a / n_a
        cdf_b = idx_b / n_b
        diff = abs(cdf_a - cdf_b)
        if diff > max_diff:
            max_diff = diff

    return max_diff


