"""
Calibrator — Confidence score calibration from outcome data.

A confidence score of 0.8 should mean "80% of the time, this
recommendation produces a positive outcome." If it doesn't,
the scoring engine is miscalibrated and recommendations can't
be trusted.

This module:
  1. Measures calibration quality (Pearson r, band-level accuracy)
  2. Builds isotonic calibration maps when miscalibrated
  3. Produces alerts when calibration degrades
  4. Applies calibration at recommendation time

Calibration targets (from Phase 3 plan Section 3.6):
  - Pearson r(confidence, revenue_lift) > 0.3 (acceptable)
  - Pearson r > 0.7 (well-calibrated)
  - Per-band positive_rate should be monotonically increasing

Phase 3 Intelligence Environment — Block C, File 11.

Place at: backend/services/scoring/learning/calibrator.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# ──────────────────────────────────────────────────────────
# INPUT: Outcome records with confidence scores
# ──────────────────────────────────────────────────────────


@dataclass
class CalibrationRecord:
    """Minimal record for calibration analysis."""

    confidence_score: float
    revenue_delta_pct: float | None
    action: str  # accepted, modified, rejected, ignored
    category: str = "all"

    @property
    def was_successful(self) -> bool:
        return (
            self.action in ("accepted", "modified")
            and self.revenue_delta_pct is not None
            and self.revenue_delta_pct > 0
        )


# ──────────────────────────────────────────────────────────
# CALIBRATION BAND: Per-band measurement
# ──────────────────────────────────────────────────────────


@dataclass
class CalibrationBand:
    """Calibration measurement for one confidence band."""

    band_lower: float
    band_upper: float
    count: int
    positive_count: int
    positive_rate: float
    """Actual positive outcome rate in this band."""
    expected_rate: float
    """Expected rate (midpoint of band)."""
    gap: float
    """positive_rate - expected_rate. Negative = overconfident."""
    mean_confidence: float
    mean_revenue_lift: float

    @property
    def band_label(self) -> str:
        return f"{self.band_lower:.1f}-{self.band_upper:.1f}"

    @property
    def is_overconfident(self) -> bool:
        """Positive rate significantly below expected."""
        return self.gap < -0.10

    @property
    def is_underconfident(self) -> bool:
        """Positive rate significantly above expected."""
        return self.gap > 0.10


# ──────────────────────────────────────────────────────────
# CALIBRATION REPORT
# ──────────────────────────────────────────────────────────


@dataclass
class CalibrationReport:
    """Complete calibration measurement for a category (or global)."""

    category: str
    analyzed_at: datetime
    n_records: int

    # ── Overall correlation ──
    pearson_r: float | None
    """Correlation between confidence and revenue_delta.
    >0.7 = well-calibrated, >0.3 = acceptable, <0.3 = miscalibrated."""

    # ── Per-band measurement ──
    bands: list[CalibrationBand]

    # ── Calibration quality ──
    is_monotonic: bool
    """True if positive_rate increases as confidence increases."""

    mean_absolute_gap: float
    """Average |positive_rate - expected_rate| across bands."""

    max_gap: float
    """Worst single band gap."""

    # ── Diagnosis ──
    calibration_quality: str
    """'well_calibrated', 'acceptable', 'miscalibrated', 'insufficient_data'"""

    overconfident_bands: list[str]
    """Band labels where we're overconfident."""

    underconfident_bands: list[str]
    """Band labels where we're underconfident."""

    @property
    def needs_calibration(self) -> bool:
        """True if calibration map should be applied."""
        return self.calibration_quality == "miscalibrated"

    @property
    def summary(self) -> str:
        r_str = f"r={self.pearson_r:.3f}" if self.pearson_r is not None else "r=N/A"
        return (
            f"Calibration({self.category}): {r_str}, "
            f"quality={self.calibration_quality}, "
            f"monotonic={self.is_monotonic}, "
            f"mean_gap={self.mean_absolute_gap:.3f}, "
            f"n={self.n_records}"
        )


# ──────────────────────────────────────────────────────────
# CALIBRATION MAP: Correction function
# ──────────────────────────────────────────────────────────


@dataclass
class CalibrationMap:
    """
    Isotonic calibration map: maps raw confidence → calibrated confidence.

    Built from historical data. Applied at recommendation time.
    The map is a piecewise linear function defined by anchor points.
    """

    category: str
    created_at: datetime
    anchor_points: list[tuple[float, float]]
    """[(raw_confidence, calibrated_confidence), ...] sorted by raw."""

    n_training_records: int = 0

    def calibrate(self, raw_confidence: float) -> float:
        """
        Map raw confidence to calibrated confidence.

        Uses linear interpolation between anchor points.
        Clamps output to [0.0, 1.0].
        """
        if not self.anchor_points:
            return raw_confidence

        # Clamp to range of anchor points
        if raw_confidence <= self.anchor_points[0][0]:
            return max(0.0, self.anchor_points[0][1])
        if raw_confidence >= self.anchor_points[-1][0]:
            return min(1.0, self.anchor_points[-1][1])

        # Linear interpolation
        for i in range(len(self.anchor_points) - 1):
            x0, y0 = self.anchor_points[i]
            x1, y1 = self.anchor_points[i + 1]
            if x0 <= raw_confidence <= x1:
                if x1 == x0:
                    return y0
                t = (raw_confidence - x0) / (x1 - x0)
                return max(0.0, min(1.0, y0 + t * (y1 - y0)))

        return raw_confidence  # Fallback

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "created_at": self.created_at.isoformat(),
            "anchor_points": self.anchor_points,
            "n_training_records": self.n_training_records,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CalibrationMap:
        return cls(
            category=d["category"],
            created_at=datetime.fromisoformat(d["created_at"]),
            anchor_points=[tuple(p) for p in d["anchor_points"]],
            n_training_records=d.get("n_training_records", 0),
        )


# ──────────────────────────────────────────────────────────
# CALIBRATOR
# ──────────────────────────────────────────────────────────

# Bands for calibration measurement
_BANDS = [
    (0.0, 0.2),
    (0.2, 0.4),
    (0.4, 0.6),
    (0.6, 0.8),
    (0.8, 1.0),
]

_MIN_RECORDS = 10  # Minimum for any analysis
_MIN_PER_BAND = 3  # Minimum per band for meaningful measurement
_WELL_CALIBRATED_R = 0.7
_ACCEPTABLE_R = 0.3


class Calibrator:
    """
    Measures and corrects confidence score calibration.

    Usage:
        cal = Calibrator()

        # Measure calibration quality
        report = cal.measure(calibration_records)
        if report.needs_calibration:
            cal_map = cal.build_calibration_map(calibration_records)
            # At recommendation time:
            calibrated = cal_map.calibrate(raw_confidence)
    """

    def __init__(self):
        self._maps: dict[str, CalibrationMap] = {}

    @property
    def active_maps(self) -> dict[str, CalibrationMap]:
        """Currently active calibration maps by category."""
        return dict(self._maps)

    def measure(
        self,
        records: Sequence[CalibrationRecord],
        category: str = "all",
    ) -> CalibrationReport:
        """
        Measure calibration quality from outcome data.

        Returns a CalibrationReport with per-band measurements,
        correlation, and diagnosis.
        """
        now = datetime.now(UTC)

        if len(records) < _MIN_RECORDS:
            return CalibrationReport(
                category=category,
                analyzed_at=now,
                n_records=len(records),
                pearson_r=None,
                bands=[],
                is_monotonic=True,
                mean_absolute_gap=0,
                max_gap=0,
                calibration_quality="insufficient_data",
                overconfident_bands=[],
                underconfident_bands=[],
            )

        # ── Pearson r ──
        pearson_r = self._compute_pearson_r(records)

        # ── Per-band measurement ──
        bands = self._measure_bands(records)

        # ── Monotonicity check ──
        bands_with_data = [b for b in bands if b.count >= _MIN_PER_BAND]
        is_monotonic = self._check_monotonic(bands_with_data)

        # ── Gap metrics ──
        if bands_with_data:
            gaps = [abs(b.gap) for b in bands_with_data]
            mean_gap = sum(gaps) / len(gaps)
            max_gap = max(gaps)
        else:
            mean_gap = 0
            max_gap = 0

        # ── Overconfident / underconfident bands ──
        overconfident = [b.band_label for b in bands_with_data if b.is_overconfident]
        underconfident = [b.band_label for b in bands_with_data if b.is_underconfident]

        # ── Quality diagnosis ──
        quality = self._diagnose_quality(pearson_r, is_monotonic, mean_gap)

        return CalibrationReport(
            category=category,
            analyzed_at=now,
            n_records=len(records),
            pearson_r=round(pearson_r, 4) if pearson_r is not None else None,
            bands=bands,
            is_monotonic=is_monotonic,
            mean_absolute_gap=round(mean_gap, 4),
            max_gap=round(max_gap, 4),
            calibration_quality=quality,
            overconfident_bands=overconfident,
            underconfident_bands=underconfident,
        )

    def build_calibration_map(
        self,
        records: Sequence[CalibrationRecord],
        category: str = "all",
    ) -> CalibrationMap:
        """
        Build a calibration map from outcome data.

        Uses isotonic regression principle: for each confidence band,
        the calibrated value is the actual positive outcome rate.
        Ensures monotonicity via pool-adjacent-violators (PAV).

        The map is stored and can be applied at recommendation time.
        """
        bands = self._measure_bands(records)
        bands_with_data = [b for b in bands if b.count >= _MIN_PER_BAND]

        if not bands_with_data:
            # Identity map
            cal_map = CalibrationMap(
                category=category,
                created_at=datetime.now(UTC),
                anchor_points=[(0.0, 0.0), (1.0, 1.0)],
                n_training_records=len(records),
            )
            self._maps[category] = cal_map
            return cal_map

        # Build anchor points: (mean_confidence, positive_rate)
        raw_points = [(b.mean_confidence, b.positive_rate) for b in bands_with_data]

        # Apply PAV (pool adjacent violators) for monotonicity
        monotonic_points = self._pav_isotonic(raw_points)

        cal_map = CalibrationMap(
            category=category,
            created_at=datetime.now(UTC),
            anchor_points=monotonic_points,
            n_training_records=len(records),
        )

        self._maps[category] = cal_map
        return cal_map

    def calibrate(
        self,
        raw_confidence: float,
        category: str = "all",
    ) -> float:
        """
        Apply calibration map to a raw confidence score.

        Returns the raw score if no calibration map exists.
        """
        cal_map = self._maps.get(category)
        if cal_map is None:
            return raw_confidence
        return cal_map.calibrate(raw_confidence)

    # ──────────────────────────────────────────────
    # INTERNAL: Statistical computations
    # ──────────────────────────────────────────────

    @staticmethod
    def _compute_pearson_r(records: Sequence[CalibrationRecord]) -> float | None:
        """Pearson r between confidence_score and revenue_delta_pct."""
        pairs = [(r.confidence_score, r.revenue_delta_pct) for r in records if r.revenue_delta_pct is not None]
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

    @staticmethod
    def _measure_bands(records: Sequence[CalibrationRecord]) -> list[CalibrationBand]:
        """Compute per-band calibration measurements."""
        bands = []
        for lower, upper in _BANDS:
            in_band = [
                r
                for r in records
                if lower <= r.confidence_score < upper or (upper == 1.0 and r.confidence_score == 1.0 and lower <= 0.8)
            ]
            if not in_band:
                bands.append(
                    CalibrationBand(
                        band_lower=lower,
                        band_upper=upper,
                        count=0,
                        positive_count=0,
                        positive_rate=0,
                        expected_rate=(lower + upper) / 2,
                        gap=0,
                        mean_confidence=0,
                        mean_revenue_lift=0,
                    )
                )
                continue

            n = len(in_band)
            pos = sum(1 for r in in_band if r.was_successful)
            pos_rate = pos / n
            expected = sum(r.confidence_score for r in in_band) / n

            lifts = [r.revenue_delta_pct for r in in_band if r.revenue_delta_pct is not None]
            mean_lift = sum(lifts) / len(lifts) if lifts else 0

            bands.append(
                CalibrationBand(
                    band_lower=lower,
                    band_upper=upper,
                    count=n,
                    positive_count=pos,
                    positive_rate=round(pos_rate, 4),
                    expected_rate=round(expected, 4),
                    gap=round(pos_rate - expected, 4),
                    mean_confidence=round(expected, 4),
                    mean_revenue_lift=round(mean_lift, 4),
                )
            )

        return bands

    @staticmethod
    def _check_monotonic(bands: list[CalibrationBand]) -> bool:
        """Check if positive_rate is monotonically non-decreasing."""
        if len(bands) < 2:
            return True
        return all(bands[i].positive_rate >= bands[i - 1].positive_rate - 0.01 for i in range(1, len(bands)))

    @staticmethod
    def _diagnose_quality(
        pearson_r: float | None,
        is_monotonic: bool,
        mean_gap: float,
    ) -> str:
        """Diagnose calibration quality."""
        if pearson_r is None:
            return "insufficient_data"

        if pearson_r >= _WELL_CALIBRATED_R and is_monotonic and mean_gap < 0.10:
            return "well_calibrated"
        elif pearson_r >= _ACCEPTABLE_R:
            return "acceptable"
        else:
            return "miscalibrated"

    @staticmethod
    def _pav_isotonic(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """
        Pool Adjacent Violators algorithm for isotonic regression.

        Ensures output y-values are monotonically non-decreasing
        while minimizing squared error from original values.
        """
        if len(points) <= 1:
            return list(points)

        # Sort by x
        sorted_pts = sorted(points, key=lambda p: p[0])

        # PAV: merge adjacent violators
        blocks = [[y] for _, y in sorted_pts]
        x_vals = [x for x, _ in sorted_pts]

        i = 0
        while i < len(blocks) - 1:
            mean_curr = sum(blocks[i]) / len(blocks[i])
            mean_next = sum(blocks[i + 1]) / len(blocks[i + 1])

            if mean_curr > mean_next:
                # Violation: merge
                blocks[i].extend(blocks[i + 1])
                blocks.pop(i + 1)
                x_vals.pop(i + 1)
                # Back up to re-check
                if i > 0:
                    i -= 1
            else:
                i += 1

        # Build output points: use mean of each block
        result = []
        x_idx = 0
        for block in blocks:
            mean_y = sum(block) / len(block)
            # Use the midpoint x of the block
            block_x = sorted_pts[x_idx][0]
            result.append((round(block_x, 4), round(mean_y, 4)))
            x_idx += len(block)

        return result
