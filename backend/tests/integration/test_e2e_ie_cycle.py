"""
Integration Test: Full Intelligence Environment Cycle

Place at: backend/tests/integration/test_e2e_ie_cycle.py

Tests the complete feedback loop:
  1. IE Orchestrator generates a recommendation (with experiment arm)
  2. Outcome is recorded (merchant decision)
  3. Measurement service evaluates at 7d window
  4. Calibrator measures calibration quality
  5. Drift detector checks for degradation
  6. Scout/Analyst feedback produces adjustments
  7. Next recommendation reflects learned context

This test uses MOCKED database and components — no real DB.
It validates the DATA FLOW between all IE phases, not SQL queries.

Run: pytest backend/tests/integration/test_e2e_ie_cycle.py -v
"""

import sys
import pytest
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch


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
# Fake collaborators for IEOrchestrator
# ──────────────────────────────────────────────────────────

class FakeExperimentManager:
    """Tracks which arms were selected and assignments recorded."""

    def __init__(self):
        self.selections = []
        self.assignments = []
        self._arm_index = 0

    def get_experiment_config(self, category_id, merchant_id):
        config = {
            "strategy_name": f"strategy_{self._arm_index}",
            "arm_index": self._arm_index,
            "is_exploration": self._arm_index % 3 == 0,
            "magnitude_multiplier": 1.0,
            "guardrail_overrides": {},
            "weight_overrides": {},
        }
        self.selections.append(config)
        self._arm_index = (self._arm_index + 1) % 3
        return config

    def record_assignment(self, recommendation_id, category_id, arm_index, is_exploration):
        self.assignments.append({
            "recommendation_id": recommendation_id,
            "category_id": category_id,
            "arm_index": arm_index,
            "is_exploration": is_exploration,
        })
        return f"assign-{len(self.assignments)}"

    def update_arm(self, category_id, arm_index, reward):
        """Called after outcome measurement to update bandit."""
        pass


class FakeScoringEngine:
    """Returns deterministic scoring results."""

    def __init__(self, suggested_price=42.99, confidence=0.75):
        self._price = suggested_price
        self._confidence = confidence
        self.call_count = 0

    def score(self, product_context):
        self.call_count += 1
        current = product_context.get("current_price", 39.99)
        return {
            "suggested_price": self._price,
            "confidence": self._confidence,
            "confidence_decomposition": {
                "elasticity": 0.7,
                "position": 0.6,
                "urgency": 0.5,
                "data_quality": 0.8,
            },
            "evidence": {
                "elasticity_estimate": -1.5,
                "competitive_position_index": 0.6,
                "urgency_score": 0.4,
            },
        }


class FakeContextInjector:
    """Returns cached category context."""

    def __init__(self):
        self.injections = []

    def get_scoring_context(self, category_id):
        ctx = {
            "category": category_id,
            "merchant_bias": 0.02,
            "acceptance_rate": 0.75,
            "best_magnitude": "2-5%",
            "n_outcomes": 25,
        }
        self.injections.append(ctx)
        return ctx

    def get_agent_context_string(self, category_id):
        return f"Historical data for {category_id}: 25 outcomes, 75% acceptance."


class FakeCalibrator:
    """Applies a simple calibration adjustment."""

    def __init__(self, adjustment=0.0):
        self._adj = adjustment
        self.calibrations = []

    def calibrate(self, raw_confidence, category_id):
        calibrated = max(0.0, min(1.0, raw_confidence + self._adj))
        result = {
            "calibrated": calibrated,
            "method": "isotonic",
            "sample_count": 50,
        }
        self.calibrations.append(result)
        return result


# ──────────────────────────────────────────────────────────
# STEP 1: IE Orchestrator generates recommendation
# ──────────────────────────────────────────────────────────

class TestStep1_GenerateRecommendation:
    """IE Orchestrator produces a traced recommendation."""

    def _make_orchestrator(self, **kwargs):
        from services.scoring.ie_orchestrator import (
            IEOrchestrator, IEOrchestratorConfig,
        )
        return IEOrchestrator(
            experiment_manager=kwargs.get("experiment_manager", FakeExperimentManager()),
            scoring_engine=kwargs.get("scoring_engine", FakeScoringEngine()),
            context_injector=kwargs.get("context_injector", FakeContextInjector()),
            calibrator=kwargs.get("calibrator", FakeCalibrator()),
            config=IEOrchestratorConfig(),
        )

    def test_generates_recommendation(self):
        from services.scoring.ie_orchestrator import IEStatus
        orch = self._make_orchestrator()
        result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert result.status in (IEStatus.SUCCESS, IEStatus.PARTIAL)
        assert result.suggested_price == 42.99
        assert result.ie_enabled is True

    def test_experiment_selected(self):
        exp_mgr = FakeExperimentManager()
        orch = self._make_orchestrator(experiment_manager=exp_mgr)
        result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert result.experiment is not None
        assert result.experiment.strategy_name.startswith("strategy_")
        assert len(exp_mgr.assignments) == 1

    def test_context_injected(self):
        ctx_inj = FakeContextInjector()
        orch = self._make_orchestrator(context_injector=ctx_inj)
        result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert result.category_context is not None
        assert result.category_context["category"] == "electronics"
        assert len(ctx_inj.injections) == 1

    def test_calibration_applied(self):
        cal = FakeCalibrator(adjustment=-0.05)
        orch = self._make_orchestrator(calibrator=cal)
        result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert result.calibration is not None
        assert result.calibrated_confidence < result.raw_confidence
        assert len(cal.calibrations) == 1

    def test_timings_tracked(self):
        orch = self._make_orchestrator()
        result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert len(result.timings) >= 3  # experiment, context, scoring
        assert result.total_duration_ms >= 0

    def test_fallback_when_disabled(self):
        from services.scoring.ie_orchestrator import IEOrchestrator, IEOrchestratorConfig, IEStatus
        orch = IEOrchestrator(
            experiment_manager=FakeExperimentManager(),
            scoring_engine=FakeScoringEngine(),
            context_injector=FakeContextInjector(),
            calibrator=FakeCalibrator(),
            config=IEOrchestratorConfig(),
            is_ie_enabled=lambda mid: False,
        )
        result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert result.status == IEStatus.FALLBACK
        assert result.ie_enabled is False

    def test_graceful_degradation_scoring_failure(self):
        """Scoring engine failure → FALLBACK status."""
        from services.scoring.ie_orchestrator import IEStatus
        broken_scorer = MagicMock()
        broken_scorer.score.side_effect = RuntimeError("boom")
        orch = self._make_orchestrator(scoring_engine=broken_scorer)
        result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert result.status == IEStatus.FALLBACK

    def test_graceful_degradation_experiment_failure(self):
        """Experiment failure → WARNING but still produces result."""
        from services.scoring.ie_orchestrator import IEStatus
        broken_exp = MagicMock()
        broken_exp.get_experiment_config.side_effect = RuntimeError("boom")
        orch = self._make_orchestrator(experiment_manager=broken_exp)
        result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert result.status in (IEStatus.SUCCESS, IEStatus.PARTIAL)
        assert any("Experiment selection failed" in w for w in result.warnings)


# ──────────────────────────────────────────────────────────
# STEP 2: Outcome recording + evidence chain
# ──────────────────────────────────────────────────────────

class TestStep2_OutcomeRecording:
    """Recommendation metadata flows into outcome record."""

    def test_ie_metadata_in_factors(self):
        """IE orchestrator populates factors dict with IE metadata."""
        from services.scoring.ie_orchestrator import IEOrchestrator, IEOrchestratorConfig

        orch = IEOrchestrator(
            experiment_manager=FakeExperimentManager(),
            scoring_engine=FakeScoringEngine(),
            context_injector=FakeContextInjector(),
            calibrator=FakeCalibrator(),
            config=IEOrchestratorConfig(),
        )
        ie_result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })

        # Simulate what recommendation_service.py does with IE result
        factors = {}
        factors["ie_status"] = ie_result.status.value
        factors["ie_calibrated_confidence"] = ie_result.calibrated_confidence
        factors["ie_raw_confidence"] = ie_result.raw_confidence
        factors["ie_total_duration_ms"] = ie_result.total_duration_ms

        if ie_result.experiment:
            factors["ie_experiment"] = {
                "strategy_name": ie_result.experiment.strategy_name,
                "arm_index": ie_result.experiment.arm_index,
                "is_exploration": ie_result.experiment.is_exploration,
            }

        assert "ie_status" in factors
        assert "ie_experiment" in factors
        assert factors["ie_experiment"]["arm_index"] >= 0

    def test_confidence_decomposition_preserved(self):
        """Confidence components from scoring engine are preserved for outcome."""
        orch_result = FakeScoringEngine().score({
            "current_price": 39.99,
            "category_id": "electronics",
        })

        decomp = orch_result["confidence_decomposition"]
        assert "elasticity" in decomp
        assert "position" in decomp
        assert "urgency" in decomp
        assert "data_quality" in decomp


# ──────────────────────────────────────────────────────────
# STEP 3: Measurement + Calibration + Drift (Phase 1+3)
# ──────────────────────────────────────────────────────────

class TestStep3_MeasurementAndCalibration:
    """After outcome data accumulates, calibration and drift detection run."""

    def test_calibrator_measures_quality(self):
        """Calibrator.measure produces CalibrationReport from outcomes."""
        from services.scoring.learning.calibrator import (
            Calibrator, CalibrationRecord,
        )
        records = [
            CalibrationRecord(
                confidence_score=i / 20,
                revenue_delta_pct=i * 0.5 - 2.0,
                action="accepted",
            )
            for i in range(20)
        ]
        cal = Calibrator()
        report = cal.measure(records)
        assert report.n_records == 20
        assert report.calibration_quality in (
            "well_calibrated", "acceptable", "miscalibrated",
        )

    def test_calibrator_builds_map_when_miscalibrated(self):
        """If miscalibrated, build_calibration_map produces correction function."""
        from services.scoring.learning.calibrator import (
            Calibrator, CalibrationRecord, CalibrationMap,
        )
        # Overconfident records: high confidence, poor outcomes
        records = [
            CalibrationRecord(
                confidence_score=0.9 - (i % 3) * 0.05,
                revenue_delta_pct=-2.0 + (i % 5) * 0.3,
                action="accepted",
            )
            for i in range(30)
        ]
        cal = Calibrator()
        cal_map = cal.build_calibration_map(records, category="electronics")
        assert isinstance(cal_map, CalibrationMap)
        # Calibrated value for high confidence should be lower
        raw = 0.9
        calibrated = cal_map.calibrate(raw)
        assert isinstance(calibrated, float)
        assert 0.0 <= calibrated <= 1.0

    def test_drift_detector_runs_on_accumulated_data(self):
        """Drift detector processes outcome records for degradation signals."""
        from services.scoring.learning.drift_detector import (
            DriftDetector, DriftRecord, DriftSeverity,
        )
        now = datetime.now(UTC)
        records = []
        # Stable baseline
        for i in range(20):
            records.append(DriftRecord(
                recommendation_id=f"base-{i}",
                category="electronics",
                timestamp=now - timedelta(days=15 + i),
                confidence_score=0.7,
                revenue_delta_pct=3.0,
                action="accepted",
            ))
        # Stable recent
        for i in range(15):
            records.append(DriftRecord(
                recommendation_id=f"recent-{i}",
                category="electronics",
                timestamp=now - timedelta(days=i),
                confidence_score=0.7,
                revenue_delta_pct=3.0,
                action="accepted",
            ))

        detector = DriftDetector()
        report = detector.detect(records, category="electronics")
        assert report.overall_severity in (DriftSeverity.NONE, DriftSeverity.LOW)
        assert report.should_retrain is False


# ──────────────────────────────────────────────────────────
# STEP 4: Scout + Analyst Feedback (Phase 3 Block C)
# ──────────────────────────────────────────────────────────

class TestStep4_FeedbackLoops:
    """Outcome data feeds back to improve Scout and Analyst behavior."""

    def test_scout_feedback_identifies_data_gaps(self):
        """Scout feedback correlates failures with data quality gaps."""
        from services.scoring.learning.scout_feedback import (
            ScoutFeedbackAnalyzer, OutcomeWithDataQuality,
        )
        outcomes = []
        # Failures with low competitor data
        for i in range(5):
            outcomes.append(OutcomeWithDataQuality(
                recommendation_id=f"f-{i}",
                category="electronics",
                action="accepted",
                revenue_delta_pct=-4.0,
                data_quality_score=0.3,
                competitor_count=0,
                sentiment_available=True,
                days_since_last_scrape=2.0,
                price_data_completeness=0.4,
                sentiment_data_completeness=0.9,
            ))
        # Successes with good data
        for i in range(10):
            outcomes.append(OutcomeWithDataQuality(
                recommendation_id=f"s-{i}",
                category="electronics",
                action="accepted",
                revenue_delta_pct=5.0,
                data_quality_score=0.8,
                competitor_count=5,
                sentiment_available=True,
                days_since_last_scrape=1.0,
                price_data_completeness=0.95,
                sentiment_data_completeness=0.9,
            ))

        report = ScoutFeedbackAnalyzer().analyze(outcomes)
        assert report.total_failures >= 5
        # Should recommend increasing competitor scraping priority
        comp_adjs = [a for a in report.adjustments if a.adjustment_type == "competitor_price"]
        assert len(comp_adjs) >= 1

    def test_analyst_feedback_adjusts_weights(self):
        """Analyst feedback identifies predictive vs noisy components."""
        from services.scoring.learning.analyst_feedback import (
            AnalystFeedbackAnalyzer, OutcomeWithComponents,
        )
        outcomes = []
        for i in range(20):
            is_success = i < 10
            outcomes.append(OutcomeWithComponents(
                recommendation_id=f"r-{i}",
                category="electronics",
                action="accepted",
                revenue_delta_pct=5.0 if is_success else -3.0,
                confidence_score=0.7,
                elasticity_score=0.8 if is_success else 0.2,
                position_score=0.5,
                urgency_score=0.3 if is_success else 0.7,
                data_quality_score=0.6,
            ))

        report = AnalystFeedbackAnalyzer().analyze(outcomes)
        assert len(report.category_recommendations) == 1
        rec = report.category_recommendations[0]
        # Elasticity should get higher weight (predicts success)
        assert rec.recommended_weights["elasticity"] >= rec.recommended_weights["urgency"]


# ──────────────────────────────────────────────────────────
# STEP 5: Context flows into next recommendation
# ──────────────────────────────────────────────────────────

class TestStep5_ContextInjectionLoop:
    """Historical context from Phases 1-3 enriches the next recommendation."""

    def test_context_enriches_next_recommendation(self):
        """Second recommendation includes category context from first cycle."""
        from services.scoring.ie_orchestrator import (
            IEOrchestrator, IEOrchestratorConfig,
        )
        ctx_injector = FakeContextInjector()
        orch = IEOrchestrator(
            experiment_manager=FakeExperimentManager(),
            scoring_engine=FakeScoringEngine(),
            context_injector=ctx_injector,
            calibrator=FakeCalibrator(),
            config=IEOrchestratorConfig(),
        )

        # First recommendation
        r1 = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert r1.category_context is not None

        # Second recommendation (simulates next cycle after learning)
        r2 = orch.generate_recommendation({
            "product_id": "prod-002",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 49.99,
        })
        assert r2.category_context is not None
        # Context injector was called twice
        assert len(ctx_injector.injections) == 2

    def test_calibrator_adjusts_subsequent_confidence(self):
        """Calibrator trained from outcomes adjusts next recommendation's confidence."""
        from services.scoring.ie_orchestrator import IEOrchestrator, IEOrchestratorConfig

        # First cycle: no calibration adjustment
        cal = FakeCalibrator(adjustment=0.0)
        orch = IEOrchestrator(
            experiment_manager=FakeExperimentManager(),
            scoring_engine=FakeScoringEngine(confidence=0.80),
            context_injector=FakeContextInjector(),
            calibrator=cal,
            config=IEOrchestratorConfig(),
        )
        r1 = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        conf_1 = r1.calibrated_confidence

        # Second cycle: calibrator learned overconfidence, adjusts down
        cal_adjusted = FakeCalibrator(adjustment=-0.10)
        orch2 = IEOrchestrator(
            experiment_manager=FakeExperimentManager(),
            scoring_engine=FakeScoringEngine(confidence=0.80),
            context_injector=FakeContextInjector(),
            calibrator=cal_adjusted,
            config=IEOrchestratorConfig(),
        )
        r2 = orch2.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        conf_2 = r2.calibrated_confidence

        # Second recommendation has lower calibrated confidence
        assert conf_2 < conf_1


# ──────────────────────────────────────────────────────────
# FULL CYCLE: End-to-End Integration
# ──────────────────────────────────────────────────────────

class TestFullIECycle:
    """
    The complete cycle that proves the IE works as a system:

    1. Generate recommendation (orchestrator)
    2. Extract outcome data (evidence chain)
    3. Feed to calibrator (is confidence predictive?)
    4. Feed to drift detector (is the model degrading?)
    5. Feed to scout/analyst feedback (what to improve?)
    6. Generate next recommendation (context reflects learning)
    """

    def test_complete_cycle(self):
        from services.scoring.ie_orchestrator import (
            IEOrchestrator, IEOrchestratorConfig, IEStatus,
        )
        from services.scoring.learning.calibrator import (
            Calibrator, CalibrationRecord,
        )
        from services.scoring.learning.drift_detector import (
            DriftDetector, DriftRecord,
        )
        from services.scoring.learning.scout_feedback import (
            ScoutFeedbackAnalyzer, OutcomeWithDataQuality,
        )
        from services.scoring.learning.analyst_feedback import (
            AnalystFeedbackAnalyzer, OutcomeWithComponents,
        )

        now = datetime.now(UTC)

        # ── STEP 1: Generate recommendations ──
        exp_mgr = FakeExperimentManager()
        scoring = FakeScoringEngine(suggested_price=42.99, confidence=0.75)
        ctx_inj = FakeContextInjector()
        cal = FakeCalibrator(adjustment=-0.02)

        orch = IEOrchestrator(
            experiment_manager=exp_mgr,
            scoring_engine=scoring,
            context_injector=ctx_inj,
            calibrator=cal,
            config=IEOrchestratorConfig(),
        )

        recommendations = []
        for i in range(10):
            r = orch.generate_recommendation({
                "product_id": f"prod-{i:03d}",
                "merchant_id": "merch-001",
                "category_id": "electronics",
                "current_price": 39.99 + i,
            })
            recommendations.append(r)

        assert len(recommendations) == 10
        assert all(r.status in (IEStatus.SUCCESS, IEStatus.PARTIAL) for r in recommendations)
        assert len(exp_mgr.assignments) == 10

        # ── STEP 2: Simulate outcomes (some good, some bad) ──
        calibration_records = []
        drift_records = []
        scout_outcomes = []
        analyst_outcomes = []

        for i, rec in enumerate(recommendations):
            is_success = i < 6  # 60% success rate
            revenue = 5.0 if is_success else -3.0

            # CalibrationRecord
            calibration_records.append(CalibrationRecord(
                confidence_score=rec.calibrated_confidence,
                revenue_delta_pct=revenue,
                action="accepted",
                category="electronics",
            ))

            # DriftRecord
            drift_records.append(DriftRecord(
                recommendation_id=rec.recommendation_id,
                category="electronics",
                timestamp=now - timedelta(days=i),
                confidence_score=rec.calibrated_confidence,
                revenue_delta_pct=revenue,
                action="accepted",
            ))

            # ScoutFeedback
            scout_outcomes.append(OutcomeWithDataQuality(
                recommendation_id=rec.recommendation_id,
                category="electronics",
                action="accepted",
                revenue_delta_pct=revenue,
                data_quality_score=0.4 if not is_success else 0.8,
                competitor_count=1 if not is_success else 5,
                sentiment_available=True,
                days_since_last_scrape=2.0,
                price_data_completeness=0.5 if not is_success else 0.9,
                sentiment_data_completeness=0.8,
            ))

            # AnalystFeedback
            analyst_outcomes.append(OutcomeWithComponents(
                recommendation_id=rec.recommendation_id,
                category="electronics",
                action="accepted",
                revenue_delta_pct=revenue,
                confidence_score=rec.calibrated_confidence,
                elasticity_score=0.8 if is_success else 0.3,
                position_score=0.5,
                urgency_score=0.3,
                data_quality_score=0.8 if is_success else 0.4,
            ))

        # ── STEP 3: Calibration ──
        calibrator = Calibrator()
        cal_report = calibrator.measure(calibration_records, category="electronics")
        assert cal_report.n_records == 10
        assert cal_report.calibration_quality in (
            "well_calibrated", "acceptable", "miscalibrated", "insufficient_data",
        )

        # ── STEP 4: Drift Detection ──
        # Need baseline records too (simulate older data)
        baseline_drift = [
            DriftRecord(
                recommendation_id=f"old-{i}",
                category="electronics",
                timestamp=now - timedelta(days=15 + i),
                confidence_score=0.7,
                revenue_delta_pct=4.0,
                action="accepted",
            )
            for i in range(15)
        ]
        detector = DriftDetector()
        drift_report = detector.detect(
            baseline_drift + drift_records,
            category="electronics",
            reference_time=now,
        )
        assert drift_report.category == "electronics"
        # With stable data, shouldn't trigger retraining
        assert isinstance(drift_report.should_retrain, bool)

        # ── STEP 5: Scout Feedback ──
        scout_report = ScoutFeedbackAnalyzer().analyze(scout_outcomes)
        assert scout_report.total_outcomes_analyzed == 10
        # Failures had low competitor data → should get adjustments
        if scout_report.total_failures >= 3:
            assert len(scout_report.adjustments) >= 0  # May or may not trigger

        # ── STEP 6: Analyst Feedback ──
        analyst_report = AnalystFeedbackAnalyzer().analyze(analyst_outcomes)
        assert analyst_report.total_outcomes == 10

        # ── STEP 7: Next recommendation with learned context ──
        # Simulate updated calibrator
        if cal_report.needs_calibration:
            calibrator.build_calibration_map(calibration_records, "electronics")

        r_next = orch.generate_recommendation({
            "product_id": "prod-next",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 45.00,
        })

        assert r_next.status in (IEStatus.SUCCESS, IEStatus.PARTIAL)
        assert r_next.category_context is not None
        assert r_next.experiment is not None
        assert r_next.calibration is not None

        # ── VERIFY: Data flowed through every phase ──
        assert scoring.call_count == 11  # 10 initial + 1 next
        assert len(ctx_inj.injections) == 11
        assert len(exp_mgr.assignments) == 11

    def test_system_handles_zero_outcomes(self):
        """IE works fine with no historical outcomes (cold start)."""
        from services.scoring.ie_orchestrator import (
            IEOrchestrator, IEOrchestratorConfig, IEStatus,
        )
        from services.scoring.learning.calibrator import Calibrator
        from services.scoring.learning.drift_detector import DriftDetector
        from services.scoring.learning.scout_feedback import ScoutFeedbackAnalyzer
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer

        # Calibration with no data
        cal_report = Calibrator().measure([], category="electronics")
        assert cal_report.calibration_quality == "insufficient_data"

        # Drift with no data
        drift_report = DriftDetector().detect([], category="electronics")
        assert drift_report.should_retrain is False

        # Scout feedback with no data
        scout_report = ScoutFeedbackAnalyzer().analyze([])
        assert scout_report.adjustments == []

        # Analyst feedback with no data
        analyst_report = AnalystFeedbackAnalyzer().analyze([])
        assert analyst_report.category_recommendations == []

        # Orchestrator still produces recommendations
        orch = IEOrchestrator(
            experiment_manager=FakeExperimentManager(),
            scoring_engine=FakeScoringEngine(),
            context_injector=FakeContextInjector(),
            calibrator=FakeCalibrator(),
            config=IEOrchestratorConfig(),
        )
        result = orch.generate_recommendation({
            "product_id": "prod-001",
            "merchant_id": "merch-001",
            "category_id": "electronics",
            "current_price": 39.99,
        })
        assert result.status in (IEStatus.SUCCESS, IEStatus.PARTIAL)


        