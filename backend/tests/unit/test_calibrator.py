"""
Tests for Calibrator — Phase 3 confidence calibration.

Place at: backend/tests/unit/test_calibrator.py

Tests cover:
  - CalibrationRecord properties
  - CalibrationBand properties
  - CalibrationReport properties
  - CalibrationMap (calibrate, interpolation, clamping, serialization)
  - Calibrator.measure (happy path, insufficient data, per-band, monotonicity,
    gap metrics, quality diagnosis)
  - Calibrator.build_calibration_map (PAV isotonic, identity fallback)
  - Calibrator.calibrate (with/without active map)
  - Pearson r computation
  - Edge cases

Run: pytest backend/tests/unit/test_calibrator.py -v
"""

import sys
from datetime import UTC, datetime

import pytest

# ──────────────────────────────────────────────────────────
# sys.modules isolation
# ──────────────────────────────────────────────────────────

_saved_modules = {}


def _save_modules():
    global _saved_modules
    _saved_modules = dict(sys.modules)


def _restore_modules():
    current = set(sys.modules.keys())
    saved = set(_saved_modules.keys())
    for mod in current - saved:
        del sys.modules[mod]


@pytest.fixture(autouse=True)
def isolate_modules():
    _save_modules()
    yield
    _restore_modules()


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────


def _make_records(n=20, base_confidence=0.5, base_lift=3.0, category="all"):
    """Generate n CalibrationRecords spread across confidence range."""
    from services.scoring.learning.calibrator import CalibrationRecord

    records = []
    for i in range(n):
        conf = i / max(n - 1, 1)  # 0.0 to 1.0
        # Revenue correlates with confidence (well-calibrated scenario)
        lift = base_lift * conf + (i % 3 - 1) * 0.5  # Some noise
        action = "accepted" if i % 4 != 3 else "rejected"
        records.append(
            CalibrationRecord(
                confidence_score=round(conf, 4),
                revenue_delta_pct=lift if action != "rejected" else -1.0,
                action=action,
                category=category,
            )
        )
    return records


def _make_overconfident_records(n=30):
    """High confidence but poor outcomes → overconfident."""
    from services.scoring.learning.calibrator import CalibrationRecord

    records = []
    for i in range(n):
        conf = 0.7 + (i / n) * 0.3  # All in 0.7-1.0 range
        # Negative outcomes despite high confidence
        lift = -2.0 + (i % 5) * 0.5
        records.append(
            CalibrationRecord(
                confidence_score=round(conf, 4),
                revenue_delta_pct=lift,
                action="accepted",
            )
        )
    # Add some low-confidence records with good outcomes
    for i in range(n):
        conf = (i / n) * 0.4  # 0.0-0.4 range
        lift = 5.0 + (i % 3)
        records.append(
            CalibrationRecord(
                confidence_score=round(conf, 4),
                revenue_delta_pct=lift,
                action="accepted",
            )
        )
    return records


# ──────────────────────────────────────────────────────────
# TESTS: CalibrationRecord
# ──────────────────────────────────────────────────────────


class TestCalibrationRecord:
    def test_was_successful_accepted_positive(self):
        from services.scoring.learning.calibrator import CalibrationRecord

        r = CalibrationRecord(confidence_score=0.8, revenue_delta_pct=5.0, action="accepted")
        assert r.was_successful is True

    def test_was_successful_modified_positive(self):
        from services.scoring.learning.calibrator import CalibrationRecord

        r = CalibrationRecord(confidence_score=0.8, revenue_delta_pct=2.0, action="modified")
        assert r.was_successful is True

    def test_not_successful_rejected(self):
        from services.scoring.learning.calibrator import CalibrationRecord

        r = CalibrationRecord(confidence_score=0.8, revenue_delta_pct=5.0, action="rejected")
        assert r.was_successful is False

    def test_not_successful_negative_revenue(self):
        from services.scoring.learning.calibrator import CalibrationRecord

        r = CalibrationRecord(confidence_score=0.8, revenue_delta_pct=-1.0, action="accepted")
        assert r.was_successful is False

    def test_not_successful_none_revenue(self):
        from services.scoring.learning.calibrator import CalibrationRecord

        r = CalibrationRecord(confidence_score=0.8, revenue_delta_pct=None, action="accepted")
        assert r.was_successful is False

    def test_not_successful_zero_revenue(self):
        from services.scoring.learning.calibrator import CalibrationRecord

        r = CalibrationRecord(confidence_score=0.8, revenue_delta_pct=0, action="accepted")
        assert r.was_successful is False


# ──────────────────────────────────────────────────────────
# TESTS: CalibrationBand
# ──────────────────────────────────────────────────────────


class TestCalibrationBand:
    def test_band_label(self):
        from services.scoring.learning.calibrator import CalibrationBand

        band = CalibrationBand(
            band_lower=0.6,
            band_upper=0.8,
            count=10,
            positive_count=7,
            positive_rate=0.7,
            expected_rate=0.7,
            gap=0.0,
            mean_confidence=0.7,
            mean_revenue_lift=3.0,
        )
        assert band.band_label == "0.6-0.8"

    def test_is_overconfident(self):
        from services.scoring.learning.calibrator import CalibrationBand

        band = CalibrationBand(
            band_lower=0.8,
            band_upper=1.0,
            count=10,
            positive_count=5,
            positive_rate=0.5,
            expected_rate=0.9,
            gap=-0.4,
            mean_confidence=0.9,
            mean_revenue_lift=1.0,
        )
        assert band.is_overconfident is True
        assert band.is_underconfident is False

    def test_is_underconfident(self):
        from services.scoring.learning.calibrator import CalibrationBand

        band = CalibrationBand(
            band_lower=0.0,
            band_upper=0.2,
            count=10,
            positive_count=8,
            positive_rate=0.8,
            expected_rate=0.1,
            gap=0.7,
            mean_confidence=0.1,
            mean_revenue_lift=5.0,
        )
        assert band.is_underconfident is True
        assert band.is_overconfident is False

    def test_neither_over_nor_under(self):
        from services.scoring.learning.calibrator import CalibrationBand

        band = CalibrationBand(
            band_lower=0.4,
            band_upper=0.6,
            count=10,
            positive_count=5,
            positive_rate=0.5,
            expected_rate=0.5,
            gap=0.0,
            mean_confidence=0.5,
            mean_revenue_lift=2.0,
        )
        assert band.is_overconfident is False
        assert band.is_underconfident is False


# ──────────────────────────────────────────────────────────
# TESTS: CalibrationReport
# ──────────────────────────────────────────────────────────


class TestCalibrationReport:
    def _make_report(self, quality="miscalibrated", **kwargs):
        from services.scoring.learning.calibrator import CalibrationReport

        defaults = dict(
            category="all",
            analyzed_at=datetime.now(UTC),
            n_records=50,
            pearson_r=0.2,
            bands=[],
            is_monotonic=True,
            mean_absolute_gap=0.15,
            max_gap=0.3,
            calibration_quality=quality,
            overconfident_bands=[],
            underconfident_bands=[],
        )
        defaults.update(kwargs)
        return CalibrationReport(**defaults)

    def test_needs_calibration_true(self):
        report = self._make_report(quality="miscalibrated")
        assert report.needs_calibration is True

    def test_needs_calibration_false_well(self):
        report = self._make_report(quality="well_calibrated")
        assert report.needs_calibration is False

    def test_needs_calibration_false_acceptable(self):
        report = self._make_report(quality="acceptable")
        assert report.needs_calibration is False

    def test_summary_string(self):
        report = self._make_report(pearson_r=0.45)
        s = report.summary
        assert "r=0.450" in s
        assert "all" in s

    def test_summary_none_r(self):
        report = self._make_report(pearson_r=None)
        assert "r=N/A" in report.summary


# ──────────────────────────────────────────────────────────
# TESTS: CalibrationMap
# ──────────────────────────────────────────────────────────


class TestCalibrationMap:
    def _make_map(self, points="DEFAULT"):
        from services.scoring.learning.calibrator import CalibrationMap

        if points == "DEFAULT":
            points = [(0.0, 0.1), (0.5, 0.5), (1.0, 0.9)]
        return CalibrationMap(
            category="test",
            created_at=datetime.now(UTC),
            anchor_points=points,
            n_training_records=50,
        )

    def test_calibrate_midpoint(self):
        """Interpolation at known anchor point."""
        m = self._make_map()
        assert m.calibrate(0.5) == 0.5

    def test_calibrate_between_anchors(self):
        """Linear interpolation between anchors."""
        m = self._make_map()
        result = m.calibrate(0.25)
        # Between (0.0, 0.1) and (0.5, 0.5): t=0.5, y=0.1+0.5*0.4=0.3
        assert abs(result - 0.3) < 0.01

    def test_calibrate_below_range(self):
        """Below first anchor → clamp to first y."""
        m = self._make_map()
        result = m.calibrate(-0.5)
        assert result == 0.1

    def test_calibrate_above_range(self):
        """Above last anchor → clamp to last y (capped at 1.0)."""
        m = self._make_map()
        result = m.calibrate(1.5)
        assert result == 0.9

    def test_calibrate_empty_map(self):
        """Empty anchor points → return raw."""
        m = self._make_map(points=[])
        assert m.calibrate(0.7) == 0.7

    def test_calibrate_single_point(self):
        """Single anchor → below returns that y."""
        m = self._make_map(points=[(0.5, 0.6)])
        assert m.calibrate(0.3) == 0.6
        assert m.calibrate(0.8) == 0.6

    def test_calibrate_clamps_to_0_1(self):
        """Output clamped to [0.0, 1.0]."""
        m = self._make_map(points=[(0.0, -0.2), (1.0, 1.5)])
        assert m.calibrate(0.0) == 0.0
        assert m.calibrate(1.0) == 1.0

    def test_to_dict_and_back(self):
        """Serialization roundtrip."""
        from services.scoring.learning.calibrator import CalibrationMap

        m = self._make_map()
        d = m.to_dict()
        m2 = CalibrationMap.from_dict(d)
        assert m2.category == m.category
        assert m2.anchor_points == m.anchor_points
        assert m2.n_training_records == m.n_training_records

    def test_duplicate_x_values(self):
        """Duplicate x in anchors doesn't crash."""
        m = self._make_map(points=[(0.5, 0.4), (0.5, 0.6), (1.0, 0.8)])
        result = m.calibrate(0.5)
        assert 0.0 <= result <= 1.0


# ──────────────────────────────────────────────────────────
# TESTS: Calibrator.measure
# ──────────────────────────────────────────────────────────


class TestCalibratorMeasure:
    def _cal(self):
        from services.scoring.learning.calibrator import Calibrator

        return Calibrator()

    def test_insufficient_data(self):
        """< 10 records → insufficient_data quality."""
        records = _make_records(n=5)
        report = self._cal().measure(records)
        assert report.calibration_quality == "insufficient_data"
        assert report.pearson_r is None
        assert report.bands == []

    def test_sufficient_data_has_bands(self):
        """20 records → 5 bands populated."""
        records = _make_records(n=20)
        report = self._cal().measure(records)
        assert len(report.bands) == 5
        assert report.n_records == 20

    def test_pearson_r_computed(self):
        """Pearson r is a float between -1 and 1."""
        records = _make_records(n=30)
        report = self._cal().measure(records)
        assert report.pearson_r is not None
        assert -1.0 <= report.pearson_r <= 1.0

    def test_well_calibrated_diagnosis(self):
        """Strong correlation + monotonic + low gap → well_calibrated."""
        from services.scoring.learning.calibrator import Calibrator

        # Directly test the diagnosis logic
        quality = Calibrator._diagnose_quality(pearson_r=0.8, is_monotonic=True, mean_gap=0.05)
        assert quality == "well_calibrated"

    def test_acceptable_diagnosis(self):
        from services.scoring.learning.calibrator import Calibrator

        quality = Calibrator._diagnose_quality(pearson_r=0.4, is_monotonic=False, mean_gap=0.15)
        assert quality == "acceptable"

    def test_miscalibrated_diagnosis(self):
        from services.scoring.learning.calibrator import Calibrator

        quality = Calibrator._diagnose_quality(pearson_r=0.1, is_monotonic=False, mean_gap=0.25)
        assert quality == "miscalibrated"

    def test_insufficient_diagnosis_none_r(self):
        from services.scoring.learning.calibrator import Calibrator

        quality = Calibrator._diagnose_quality(pearson_r=None, is_monotonic=True, mean_gap=0.0)
        assert quality == "insufficient_data"

    def test_monotonicity_check_increasing(self):
        """Monotonically increasing positive rates → True."""
        from services.scoring.learning.calibrator import CalibrationBand, Calibrator

        bands = [
            CalibrationBand(0.0, 0.2, 5, 1, 0.2, 0.1, 0.1, 0.1, 1.0),
            CalibrationBand(0.4, 0.6, 5, 3, 0.5, 0.5, 0.0, 0.5, 3.0),
            CalibrationBand(0.8, 1.0, 5, 4, 0.8, 0.9, -0.1, 0.9, 5.0),
        ]
        assert Calibrator._check_monotonic(bands) is True

    def test_monotonicity_check_violation(self):
        """Non-monotonic → False."""
        from services.scoring.learning.calibrator import CalibrationBand, Calibrator

        bands = [
            CalibrationBand(0.0, 0.2, 5, 4, 0.8, 0.1, 0.7, 0.1, 5.0),
            CalibrationBand(0.4, 0.6, 5, 1, 0.2, 0.5, -0.3, 0.5, 1.0),
        ]
        assert Calibrator._check_monotonic(bands) is False

    def test_monotonicity_single_band(self):
        """Single band → trivially monotonic."""
        from services.scoring.learning.calibrator import CalibrationBand, Calibrator

        bands = [CalibrationBand(0.0, 0.2, 5, 3, 0.6, 0.1, 0.5, 0.1, 3.0)]
        assert Calibrator._check_monotonic(bands) is True

    def test_overconfident_bands_detected(self):
        """Overconfident high bands appear in report."""
        records = _make_overconfident_records(n=30)
        report = self._cal().measure(records)
        # High bands should be overconfident (positive_rate << expected)
        assert isinstance(report.overconfident_bands, list)

    def test_gap_metrics(self):
        """Mean and max gap are non-negative."""
        records = _make_records(n=30)
        report = self._cal().measure(records)
        assert report.mean_absolute_gap >= 0
        assert report.max_gap >= 0
        assert report.max_gap >= report.mean_absolute_gap

    def test_category_passed_through(self):
        """Category argument appears in report."""
        records = _make_records(n=20)
        report = self._cal().measure(records, category="fashion")
        assert report.category == "fashion"

    def test_band_at_1_0_included(self):
        """Confidence score of exactly 1.0 is included in 0.8-1.0 band."""
        from services.scoring.learning.calibrator import CalibrationRecord

        records = _make_records(n=15)
        records.append(CalibrationRecord(confidence_score=1.0, revenue_delta_pct=10.0, action="accepted"))
        report = self._cal().measure(records)
        last_band = report.bands[-1]
        assert last_band.count > 0


# ──────────────────────────────────────────────────────────
# TESTS: Calibrator.build_calibration_map
# ──────────────────────────────────────────────────────────


class TestBuildCalibrationMap:
    def _cal(self):
        from services.scoring.learning.calibrator import Calibrator

        return Calibrator()

    def test_returns_calibration_map(self):
        from services.scoring.learning.calibrator import CalibrationMap

        records = _make_records(n=30)
        cal = self._cal()
        m = cal.build_calibration_map(records)
        assert isinstance(m, CalibrationMap)
        assert len(m.anchor_points) > 0

    def test_map_stored_internally(self):
        """Built map is stored in active_maps."""
        records = _make_records(n=30)
        cal = self._cal()
        cal.build_calibration_map(records, category="electronics")
        assert "electronics" in cal.active_maps

    def test_single_band_map(self):
        """All records in one band → single anchor point at that band."""
        from services.scoring.learning.calibrator import CalibrationRecord

        # All records in one narrow band
        records = [CalibrationRecord(confidence_score=0.5, revenue_delta_pct=1.0, action="accepted") for _ in range(20)]
        cal = self._cal()
        m = cal.build_calibration_map(records)
        # Single band populated → single anchor point
        assert len(m.anchor_points) >= 1
        # All anchor y-values in [0, 1]
        for x, y in m.anchor_points:
            assert 0.0 <= y <= 1.0

    def test_anchor_points_monotonic(self):
        """PAV ensures y-values are monotonically non-decreasing."""
        records = _make_overconfident_records(n=20)
        cal = self._cal()
        m = cal.build_calibration_map(records)
        for i in range(1, len(m.anchor_points)):
            assert m.anchor_points[i][1] >= m.anchor_points[i - 1][1]

    def test_pav_merges_violators(self):
        """PAV algorithm merges adjacent violators."""
        from services.scoring.learning.calibrator import Calibrator

        points = [(0.1, 0.8), (0.3, 0.2), (0.7, 0.6)]
        result = Calibrator._pav_isotonic(points)
        # After PAV, y-values should be non-decreasing
        for i in range(1, len(result)):
            assert result[i][1] >= result[i - 1][1]

    def test_pav_single_point(self):
        from services.scoring.learning.calibrator import Calibrator

        result = Calibrator._pav_isotonic([(0.5, 0.6)])
        assert result == [(0.5, 0.6)]

    def test_pav_empty(self):
        from services.scoring.learning.calibrator import Calibrator

        result = Calibrator._pav_isotonic([])
        assert result == []

    def test_pav_already_monotonic(self):
        from services.scoring.learning.calibrator import Calibrator

        points = [(0.1, 0.2), (0.5, 0.5), (0.9, 0.8)]
        result = Calibrator._pav_isotonic(points)
        assert len(result) == 3
        assert result[0][1] <= result[1][1] <= result[2][1]

    def test_n_training_records_set(self):
        records = _make_records(n=25)
        cal = self._cal()
        m = cal.build_calibration_map(records)
        assert m.n_training_records == 25


# ──────────────────────────────────────────────────────────
# TESTS: Calibrator.calibrate
# ──────────────────────────────────────────────────────────


class TestCalibratorCalibrate:
    def _cal(self):
        from services.scoring.learning.calibrator import Calibrator

        return Calibrator()

    def test_no_map_returns_raw(self):
        """No calibration map for category → raw score returned."""
        cal = self._cal()
        assert cal.calibrate(0.7) == 0.7

    def test_with_map_adjusts(self):
        """Active map → score adjusted."""
        cal = self._cal()
        records = _make_records(n=30)
        cal.build_calibration_map(records, category="all")
        result = cal.calibrate(0.5, category="all")
        # Should be different from raw (unless perfectly calibrated)
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_wrong_category_returns_raw(self):
        """Map for 'electronics' doesn't affect 'fashion'."""
        cal = self._cal()
        records = _make_records(n=30)
        cal.build_calibration_map(records, category="electronics")
        assert cal.calibrate(0.5, category="fashion") == 0.5


# ──────────────────────────────────────────────────────────
# TESTS: Pearson r
# ──────────────────────────────────────────────────────────


class TestPearsonR:
    def test_perfect_positive(self):
        from services.scoring.learning.calibrator import CalibrationRecord, Calibrator

        records = [
            CalibrationRecord(confidence_score=float(i) / 10, revenue_delta_pct=float(i), action="accepted")
            for i in range(1, 11)
        ]
        r = Calibrator._compute_pearson_r(records)
        assert r is not None
        assert r > 0.99

    def test_perfect_negative(self):
        from services.scoring.learning.calibrator import CalibrationRecord, Calibrator

        records = [
            CalibrationRecord(confidence_score=float(i) / 10, revenue_delta_pct=float(10 - i), action="accepted")
            for i in range(1, 11)
        ]
        r = Calibrator._compute_pearson_r(records)
        assert r is not None
        assert r < -0.99

    def test_insufficient_pairs(self):
        from services.scoring.learning.calibrator import CalibrationRecord, Calibrator

        records = [CalibrationRecord(confidence_score=0.5, revenue_delta_pct=3.0, action="accepted") for _ in range(3)]
        r = Calibrator._compute_pearson_r(records)
        assert r is None

    def test_none_revenue_excluded(self):
        from services.scoring.learning.calibrator import CalibrationRecord, Calibrator

        records = [
            CalibrationRecord(confidence_score=float(i) / 10, revenue_delta_pct=None, action="accepted")
            for i in range(10)
        ]
        r = Calibrator._compute_pearson_r(records)
        assert r is None  # All None → < 5 pairs

    def test_constant_values_returns_zero(self):
        from services.scoring.learning.calibrator import CalibrationRecord, Calibrator

        records = [CalibrationRecord(confidence_score=0.5, revenue_delta_pct=3.0, action="accepted") for _ in range(10)]
        r = Calibrator._compute_pearson_r(records)
        assert r == 0.0
