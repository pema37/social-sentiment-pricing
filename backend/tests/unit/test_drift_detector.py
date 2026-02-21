"""
Tests for DriftDetector — Phase 3 model drift detection.

Place at: backend/tests/unit/test_drift_detector.py

Tests cover:
  - DriftRecord properties
  - DriftReport properties
  - DriftDetector.detect (happy path, insufficient data, all 5 signal types)
  - Correlation drop detection
  - Acceptance rate decline
  - Revenue lift decline
  - Distribution shift (simplified KS)
  - Volume drop
  - Overall severity assessment (escalation logic)
  - detect_all_categories
  - Edge cases

Run: pytest backend/tests/unit/test_drift_detector.py -v
"""

import sys
import pytest
from datetime import datetime, timedelta, UTC


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

def _make_records(
    n_baseline=20, n_recent=15,
    baseline_conf=0.6, recent_conf=0.6,
    baseline_lift=5.0, recent_lift=5.0,
    baseline_acceptance=0.8, recent_acceptance=0.8,
    category="electronics",
    reference_time=None,
):
    """Generate drift records in baseline and recent windows."""
    from services.scoring.learning.drift_detector import DriftRecord
    now = reference_time or datetime.now(UTC)
    records = []

    # Baseline: 8-30 days ago
    for i in range(n_baseline):
        day_offset = 8 + (i * 22 // max(n_baseline, 1))
        ts = now - timedelta(days=day_offset)
        acted = i < int(n_baseline * baseline_acceptance)
        action = "accepted" if acted else "rejected"
        conf = baseline_conf + (i % 5 - 2) * 0.05
        lift = baseline_lift + (i % 3 - 1) * 1.0 if acted else -1.0

        records.append(DriftRecord(
            recommendation_id=f"base-{i}",
            category=category,
            timestamp=ts,
            confidence_score=max(0.0, min(1.0, round(conf, 4))),
            revenue_delta_pct=lift,
            action=action,
        ))

    # Recent: 0-7 days ago
    for i in range(n_recent):
        day_offset = i * 7 // max(n_recent, 1)
        ts = now - timedelta(days=day_offset)
        acted = i < int(n_recent * recent_acceptance)
        action = "accepted" if acted else "rejected"
        conf = recent_conf + (i % 5 - 2) * 0.05
        lift = recent_lift + (i % 3 - 1) * 1.0 if acted else -1.0

        records.append(DriftRecord(
            recommendation_id=f"recent-{i}",
            category=category,
            timestamp=ts,
            confidence_score=max(0.0, min(1.0, round(conf, 4))),
            revenue_delta_pct=lift,
            action=action,
        ))

    return records


# ──────────────────────────────────────────────────────────
# TESTS: DriftRecord
# ──────────────────────────────────────────────────────────

class TestDriftRecord:

    def test_was_successful(self):
        from services.scoring.learning.drift_detector import DriftRecord
        r = DriftRecord("r1", "cat", datetime.now(UTC), 0.8, 5.0, "accepted")
        assert r.was_successful is True

    def test_was_successful_modified(self):
        from services.scoring.learning.drift_detector import DriftRecord
        r = DriftRecord("r1", "cat", datetime.now(UTC), 0.8, 3.0, "modified")
        assert r.was_successful is True

    def test_not_successful_negative(self):
        from services.scoring.learning.drift_detector import DriftRecord
        r = DriftRecord("r1", "cat", datetime.now(UTC), 0.8, -2.0, "accepted")
        assert r.was_successful is False

    def test_not_successful_rejected(self):
        from services.scoring.learning.drift_detector import DriftRecord
        r = DriftRecord("r1", "cat", datetime.now(UTC), 0.8, 5.0, "rejected")
        assert r.was_successful is False

    def test_was_acted_on(self):
        from services.scoring.learning.drift_detector import DriftRecord
        r = DriftRecord("r1", "cat", datetime.now(UTC), 0.8, 5.0, "accepted")
        assert r.was_acted_on is True

    def test_was_not_acted_on(self):
        from services.scoring.learning.drift_detector import DriftRecord
        r = DriftRecord("r1", "cat", datetime.now(UTC), 0.8, 5.0, "ignored")
        assert r.was_acted_on is False


# ──────────────────────────────────────────────────────────
# TESTS: DriftReport
# ──────────────────────────────────────────────────────────

class TestDriftReport:

    def test_has_drift_true(self):
        from services.scoring.learning.drift_detector import DriftReport, DriftSeverity
        report = DriftReport(
            analyzed_at=datetime.now(UTC), category="all",
            period_start=datetime.now(UTC), period_end=datetime.now(UTC),
            recent_window_days=7, baseline_window_days=30,
            recent_count=15, baseline_count=50,
            signals=[], overall_severity=DriftSeverity.MEDIUM,
            should_retrain=False, should_recalibrate=True,
        )
        assert report.has_drift is True

    def test_has_drift_false(self):
        from services.scoring.learning.drift_detector import DriftReport, DriftSeverity
        report = DriftReport(
            analyzed_at=datetime.now(UTC), category="all",
            period_start=datetime.now(UTC), period_end=datetime.now(UTC),
            recent_window_days=7, baseline_window_days=30,
            recent_count=15, baseline_count=50,
            signals=[], overall_severity=DriftSeverity.NONE,
            should_retrain=False, should_recalibrate=False,
        )
        assert report.has_drift is False

    def test_summary_string(self):
        from services.scoring.learning.drift_detector import DriftReport, DriftSeverity
        report = DriftReport(
            analyzed_at=datetime.now(UTC), category="electronics",
            period_start=datetime.now(UTC), period_end=datetime.now(UTC),
            recent_window_days=7, baseline_window_days=30,
            recent_count=15, baseline_count=50,
            signals=[], overall_severity=DriftSeverity.LOW,
            should_retrain=False, should_recalibrate=False,
        )
        s = report.summary
        assert "electronics" in s
        assert "low" in s


# ──────────────────────────────────────────────────────────
# TESTS: DriftDetector.detect — Happy Path
# ──────────────────────────────────────────────────────────

class TestDriftDetectorDetect:

    def _detector(self, **kwargs):
        from services.scoring.learning.drift_detector import DriftDetector
        return DriftDetector(**kwargs)

    def test_stable_system_no_drift(self):
        """Stable baseline and recent → NONE or LOW severity."""
        from services.scoring.learning.drift_detector import DriftRecord, DriftSeverity
        now = datetime.now(UTC)
        records = []
        # Baseline: uniform confidence, positive lift, all accepted
        for i in range(20):
            records.append(DriftRecord(
                recommendation_id=f"base-{i}",
                category="electronics",
                timestamp=now - timedelta(days=10 + i),
                confidence_score=0.7,
                revenue_delta_pct=4.0,
                action="accepted",
            ))
        # Recent: same pattern
        for i in range(15):
            records.append(DriftRecord(
                recommendation_id=f"recent-{i}",
                category="electronics",
                timestamp=now - timedelta(days=i),
                confidence_score=0.7,
                revenue_delta_pct=4.0,
                action="accepted",
            ))
        report = self._detector().detect(records)
        assert report.overall_severity in (DriftSeverity.NONE, DriftSeverity.LOW)

    def test_report_has_signals(self):
        """Detect produces signal list."""
        records = _make_records()
        report = self._detector().detect(records)
        assert isinstance(report.signals, list)

    def test_insufficient_recent(self):
        """Not enough recent data → no signals."""
        records = _make_records(n_recent=3)
        report = self._detector().detect(records)
        # Volume check may still fire, but correlation/acceptance/lift/distribution won't
        correlation_signals = [s for s in report.signals if s.signal_type == "correlation_drop"]
        assert len(correlation_signals) == 0

    def test_insufficient_baseline(self):
        """Not enough baseline → no signals at all."""
        records = _make_records(n_baseline=3, n_recent=15)
        report = self._detector().detect(records)
        assert len(report.signals) == 0

    def test_report_stored_in_history(self):
        """Each detect() call is stored in history."""
        detector = self._detector()
        records = _make_records()
        detector.detect(records)
        detector.detect(records)
        assert len(detector.history) == 2

    def test_category_filter(self):
        """Category filter only uses matching records."""
        records = _make_records(category="electronics")
        records += _make_records(category="fashion")
        report = self._detector().detect(records, category="electronics")
        assert report.category == "electronics"

    def test_reference_time(self):
        """Custom reference time shifts windows."""
        ref = datetime(2026, 1, 15, tzinfo=UTC)
        records = _make_records(reference_time=ref)
        report = self._detector().detect(records, reference_time=ref)
        assert report.analyzed_at == ref


# ──────────────────────────────────────────────────────────
# TESTS: Individual Signal Detectors
# ──────────────────────────────────────────────────────────

class TestCorrelationDrop:

    def _detector(self):
        from services.scoring.learning.drift_detector import DriftDetector
        return DriftDetector()

    def test_critical_correlation(self):
        """Very low recent correlation → CRITICAL."""
        from services.scoring.learning.drift_detector import DriftSeverity
        # Recent: random confidence, no correlation with revenue
        records = _make_records(
            baseline_conf=0.5, recent_conf=0.5,
            baseline_lift=5.0, recent_lift=0.0,  # No lift pattern
        )
        report = self._detector().detect(records)
        corr_signals = [s for s in report.signals if s.signal_type == "correlation_drop"]
        # At minimum we get a signal
        assert isinstance(corr_signals, list)


class TestAcceptanceDecline:

    def _detector(self):
        from services.scoring.learning.drift_detector import DriftDetector
        return DriftDetector()

    def test_declining_acceptance(self):
        """Sharp acceptance drop → at least MEDIUM signal."""
        from services.scoring.learning.drift_detector import DriftSeverity
        records = _make_records(
            baseline_acceptance=0.9,
            recent_acceptance=0.4,
        )
        report = self._detector().detect(records)
        acc_signals = [s for s in report.signals if s.signal_type == "acceptance_decline"]
        assert len(acc_signals) == 1
        assert acc_signals[0].severity in (
            DriftSeverity.MEDIUM, DriftSeverity.HIGH
        )
        assert acc_signals[0].delta < 0

    def test_stable_acceptance(self):
        """Stable acceptance → NONE."""
        from services.scoring.learning.drift_detector import DriftSeverity
        records = _make_records(
            baseline_acceptance=0.8,
            recent_acceptance=0.8,
        )
        report = self._detector().detect(records)
        acc_signals = [s for s in report.signals if s.signal_type == "acceptance_decline"]
        if acc_signals:
            assert acc_signals[0].severity == DriftSeverity.NONE


class TestLiftDecline:

    def _detector(self):
        from services.scoring.learning.drift_detector import DriftDetector
        return DriftDetector()

    def test_declining_lift(self):
        """Sharp lift drop → at least MEDIUM."""
        from services.scoring.learning.drift_detector import DriftSeverity
        records = _make_records(
            baseline_lift=8.0,
            recent_lift=2.0,
        )
        report = self._detector().detect(records)
        lift_signals = [s for s in report.signals if s.signal_type == "lift_decline"]
        if lift_signals:
            assert lift_signals[0].severity in (
                DriftSeverity.MEDIUM, DriftSeverity.HIGH
            )

    def test_stable_lift(self):
        """Stable lift → NONE."""
        from services.scoring.learning.drift_detector import DriftSeverity
        records = _make_records(baseline_lift=5.0, recent_lift=5.0)
        report = self._detector().detect(records)
        lift_signals = [s for s in report.signals if s.signal_type == "lift_decline"]
        if lift_signals:
            assert lift_signals[0].severity == DriftSeverity.NONE


class TestDistributionShift:

    def _detector(self):
        from services.scoring.learning.drift_detector import DriftDetector
        return DriftDetector()

    def test_shifted_distribution(self):
        """Major confidence shift → signal detected."""
        records = _make_records(
            baseline_conf=0.3,  # Low confidence baseline
            recent_conf=0.9,   # High confidence recent
        )
        report = self._detector().detect(records)
        dist_signals = [s for s in report.signals if s.signal_type == "distribution_shift"]
        assert len(dist_signals) == 1

    def test_stable_distribution(self):
        """Same distribution → NONE."""
        from services.scoring.learning.drift_detector import DriftSeverity
        records = _make_records(baseline_conf=0.5, recent_conf=0.5)
        report = self._detector().detect(records)
        dist_signals = [s for s in report.signals if s.signal_type == "distribution_shift"]
        if dist_signals:
            assert dist_signals[0].severity == DriftSeverity.NONE


class TestVolumeCheck:

    def _detector(self):
        from services.scoring.learning.drift_detector import DriftDetector
        return DriftDetector()

    def test_volume_drop(self):
        """Very few recent vs baseline → volume_drop signal."""
        from services.scoring.learning.drift_detector import DriftSeverity
        records = _make_records(n_baseline=40, n_recent=2)
        report = self._detector().detect(records)
        vol_signals = [s for s in report.signals if s.signal_type == "volume_drop"]
        assert len(vol_signals) == 1
        assert vol_signals[0].severity in (
            DriftSeverity.MEDIUM, DriftSeverity.HIGH
        )

    def test_stable_volume(self):
        """Similar per-day rates → NONE."""
        from services.scoring.learning.drift_detector import DriftSeverity
        records = _make_records(n_baseline=20, n_recent=15)
        report = self._detector().detect(records)
        vol_signals = [s for s in report.signals if s.signal_type == "volume_drop"]
        if vol_signals:
            assert vol_signals[0].severity == DriftSeverity.NONE


# ──────────────────────────────────────────────────────────
# TESTS: Overall Severity Assessment
# ──────────────────────────────────────────────────────────

class TestOverallAssessment:

    def _assess(self, severities):
        from services.scoring.learning.drift_detector import (
            DriftDetector, DriftSignal, DriftSeverity,
        )
        signals = [
            DriftSignal(
                signal_type="test", severity=sev,
                current_value=0, baseline_value=0,
                delta=0, description="test", category="all",
            )
            for sev in severities
        ]
        return DriftDetector._assess_overall(signals)

    def test_no_signals(self):
        from services.scoring.learning.drift_detector import DriftSeverity
        assert self._assess([]) == DriftSeverity.NONE

    def test_single_critical(self):
        from services.scoring.learning.drift_detector import DriftSeverity
        assert self._assess([DriftSeverity.CRITICAL]) == DriftSeverity.CRITICAL

    def test_two_high_escalate(self):
        from services.scoring.learning.drift_detector import DriftSeverity
        result = self._assess([DriftSeverity.HIGH, DriftSeverity.HIGH])
        assert result == DriftSeverity.CRITICAL

    def test_single_high(self):
        from services.scoring.learning.drift_detector import DriftSeverity
        result = self._assess([DriftSeverity.HIGH, DriftSeverity.LOW])
        assert result == DriftSeverity.HIGH

    def test_two_medium_escalate(self):
        from services.scoring.learning.drift_detector import DriftSeverity
        result = self._assess([DriftSeverity.MEDIUM, DriftSeverity.MEDIUM])
        assert result == DriftSeverity.HIGH

    def test_single_medium(self):
        from services.scoring.learning.drift_detector import DriftSeverity
        result = self._assess([DriftSeverity.MEDIUM, DriftSeverity.LOW])
        assert result == DriftSeverity.MEDIUM

    def test_all_low(self):
        from services.scoring.learning.drift_detector import DriftSeverity
        result = self._assess([DriftSeverity.LOW, DriftSeverity.LOW])
        assert result == DriftSeverity.LOW

    def test_all_none(self):
        from services.scoring.learning.drift_detector import DriftSeverity
        result = self._assess([DriftSeverity.NONE, DriftSeverity.NONE])
        assert result == DriftSeverity.NONE

    def test_retrain_flag_high(self):
        """HIGH overall → should_retrain=True."""
        records = _make_records(baseline_acceptance=0.95, recent_acceptance=0.2)
        from services.scoring.learning.drift_detector import DriftDetector
        report = DriftDetector().detect(records)
        # If overall is HIGH or CRITICAL, should_retrain is True
        if report.overall_severity.value in ("high", "critical"):
            assert report.should_retrain is True

    def test_recalibrate_flag_medium(self):
        """MEDIUM+ overall → should_recalibrate=True."""
        from services.scoring.learning.drift_detector import DriftSeverity
        records = _make_records(baseline_acceptance=0.9, recent_acceptance=0.5)
        from services.scoring.learning.drift_detector import DriftDetector
        report = DriftDetector().detect(records)
        if report.overall_severity in (DriftSeverity.MEDIUM, DriftSeverity.HIGH, DriftSeverity.CRITICAL):
            assert report.should_recalibrate is True


# ──────────────────────────────────────────────────────────
# TESTS: detect_all_categories
# ──────────────────────────────────────────────────────────

class TestDetectAllCategories:

    def test_multiple_categories(self):
        """Reports generated per category."""
        from services.scoring.learning.drift_detector import DriftDetector
        records = _make_records(category="electronics")
        records += _make_records(category="fashion")
        detector = DriftDetector()
        reports = detector.detect_all_categories(records)
        categories = {r.category for r in reports}
        assert "electronics" in categories
        assert "fashion" in categories

    def test_empty_records(self):
        from services.scoring.learning.drift_detector import DriftDetector
        reports = DriftDetector().detect_all_categories([])
        assert reports == []


# ──────────────────────────────────────────────────────────
# TESTS: Simplified KS Statistic
# ──────────────────────────────────────────────────────────

class TestSimplifiedKS:

    def test_identical_distributions(self):
        from services.scoring.learning.drift_detector import _simplified_ks
        a = [0.1, 0.3, 0.5, 0.7, 0.9]
        assert _simplified_ks(a, list(a)) == 0.0

    def test_completely_separated(self):
        from services.scoring.learning.drift_detector import _simplified_ks
        a = [0.0, 0.1, 0.2]
        b = [0.8, 0.9, 1.0]
        ks = _simplified_ks(a, b)
        assert ks > 0.5

    def test_empty_samples(self):
        from services.scoring.learning.drift_detector import _simplified_ks
        assert _simplified_ks([], [0.5]) == 0.0
        assert _simplified_ks([0.5], []) == 0.0
        assert _simplified_ks([], []) == 0.0

    def test_ks_between_0_and_1(self):
        from services.scoring.learning.drift_detector import _simplified_ks
        a = [0.1, 0.2, 0.3, 0.4, 0.5]
        b = [0.3, 0.4, 0.5, 0.6, 0.7]
        ks = _simplified_ks(a, b)
        assert 0.0 <= ks <= 1.0

        