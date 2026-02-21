"""
Tests for IE Orchestrator (Phase 5)
====================================
24 tests covering:
  - Happy path: full pipeline with all components
  - Feature flag: IE disabled for merchant
  - Component failures: each component fails independently
  - Fallback behavior: graceful degradation
  - Strategy overrides: experiment config applied correctly
  - Calibration: raw vs calibrated confidence
  - Timing tracking: latency observability
  - Edge cases: missing fields, zero price, no category

Pattern: sys.modules isolation, MagicMock() (not spec=), frozen dataclasses
Location: backend/tests/unit/test_ie_orchestrator.py
"""

import sys
import time
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Save/restore module state to prevent pollution
# ---------------------------------------------------------------------------
_saved_modules = dict(sys.modules)


def teardown_module():
    """Restore sys.modules after all tests."""
    to_remove = [k for k in sys.modules if k not in _saved_modules]
    for k in to_remove:
        del sys.modules[k]


# ---------------------------------------------------------------------------
# Import the module under test (no external deps needed)
# ---------------------------------------------------------------------------
from phase5.ie_orchestrator import (
    CalibrationAdjustment,
    ComponentTiming,
    ExperimentContext,
    IEOrchestrator,
    IEOrchestratorConfig,
    IERecommendation,
    IEStatus,
)


# ---------------------------------------------------------------------------
# Helpers: mock collaborators
# ---------------------------------------------------------------------------

def make_experiment_manager(
    config=None, record_result="assignment-123", fail_get=False, fail_record=False
):
    """Build a mock ExperimentManager."""
    mgr = MagicMock()
    if fail_get:
        mgr.get_experiment_config.side_effect = RuntimeError("Experiment selection failed")
    else:
        mgr.get_experiment_config.return_value = config or {
            "strategy_name": "elasticity_optimal",
            "arm_index": 1,
            "is_exploration": False,
            "magnitude_multiplier": 1.0,
            "guardrail_overrides": {},
            "weight_overrides": {"elasticity": 0.35},
        }
    if fail_record:
        mgr.record_assignment.side_effect = RuntimeError("Recording failed")
    else:
        mgr.record_assignment.return_value = record_result
    return mgr


def make_scoring_engine(result=None, fail=False):
    """Build a mock ScoringEngine."""
    engine = MagicMock()
    if fail:
        engine.score.side_effect = RuntimeError("Scoring failed")
    else:
        engine.score.return_value = result or {
            "suggested_price": 29.99,
            "confidence": 0.75,
            "confidence_decomposition": {
                "elasticity": 0.8,
                "position": 0.7,
                "urgency": 0.6,
                "data_quality": 0.9,
            },
            "evidence": {
                "elasticity_estimate": -1.2,
                "position_percentile": 65,
            },
        }
    return engine


def make_context_injector(context=None, fail=False):
    """Build a mock ContextInjector."""
    injector = MagicMock()
    if fail:
        injector.get_scoring_context.side_effect = RuntimeError("Context failed")
    else:
        injector.get_scoring_context.return_value = context or {
            "avg_acceptance_rate": 0.73,
            "avg_revenue_lift": 4.2,
            "confidence_accuracy_corr": 0.68,
        }
    injector.get_agent_context_string.return_value = "In Electronics, confidence > 0.8 produces 4.2% lift."
    return injector


def make_calibrator(calibrated=None, fail=False):
    """Build a mock Calibrator."""
    cal = MagicMock()
    if fail:
        cal.calibrate.side_effect = RuntimeError("Calibration failed")
    else:
        cal.calibrate.return_value = calibrated or {
            "calibrated": 0.68,
            "method": "isotonic",
            "sample_count": 50,
        }
    return cal


def make_product_context(**overrides):
    """Build a standard product context dict."""
    ctx = {
        "product_id": "prod-001",
        "merchant_id": "merch-001",
        "category_id": "electronics",
        "current_price": 24.99,
        "cost": 12.00,
        "competitor_prices": [22.99, 25.99, 27.99],
    }
    ctx.update(overrides)
    return ctx


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIEOrchestratorHappyPath(unittest.TestCase):
    """Full pipeline with all components succeeding."""

    def test_full_pipeline_success(self):
        """All 4 components succeed → IEStatus.SUCCESS (or PARTIAL with warnings)."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context())

        assert isinstance(result, IERecommendation)
        assert result.ie_enabled is True
        assert result.suggested_price == 29.99
        assert result.raw_confidence == 0.75
        assert result.calibrated_confidence == 0.68  # Calibrator adjusted
        assert result.direction == "increase"  # 24.99 → 29.99
        assert result.experiment is not None
        assert result.experiment.strategy_name == "elasticity_optimal"
        assert result.calibration is not None
        assert result.calibration.calibration_method == "isotonic"
        assert result.pipeline_version == "ie-v1.0"

    def test_recommendation_id_is_uuid(self):
        """Each recommendation gets a unique UUID."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        r1 = orch.generate_recommendation(make_product_context())
        r2 = orch.generate_recommendation(make_product_context())
        assert r1.recommendation_id != r2.recommendation_id
        assert len(r1.recommendation_id) == 36  # UUID format

    def test_change_pct_calculated_correctly(self):
        """change_pct = (suggested - current) / current * 100."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine({"suggested_price": 30.0, "confidence": 0.8}),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context(current_price=25.0))
        assert result.change_pct == 20.0  # (30 - 25) / 25 * 100

    def test_direction_hold_when_no_change(self):
        """Direction is 'hold' when suggested ≈ current."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine({"suggested_price": 25.0, "confidence": 0.5}),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context(current_price=25.0))
        assert result.direction == "hold"

    def test_direction_decrease(self):
        """Direction is 'decrease' when suggested < current."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine({"suggested_price": 20.0, "confidence": 0.6}),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context(current_price=25.0))
        assert result.direction == "decrease"


class TestIEOrchestratorFeatureFlags(unittest.TestCase):
    """Feature flag behavior."""

    def test_ie_disabled_returns_fallback(self):
        """When IE is disabled for merchant, return FALLBACK status."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
            is_ie_enabled=lambda mid: False,
        )
        result = orch.generate_recommendation(make_product_context())

        assert result.status == IEStatus.FALLBACK
        assert result.ie_enabled is False
        assert result.suggested_price == 24.99  # No change
        assert result.direction == "hold"
        assert "IE disabled" in result.warnings[0]

    def test_ie_enabled_per_merchant(self):
        """Feature flag checks merchant_id correctly."""
        flags = {"merch-001": True, "merch-002": False}
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
            is_ie_enabled=lambda mid: flags.get(mid, False),
        )

        r1 = orch.generate_recommendation(make_product_context(merchant_id="merch-001"))
        assert r1.ie_enabled is True

        r2 = orch.generate_recommendation(make_product_context(merchant_id="merch-002"))
        assert r2.status == IEStatus.FALLBACK


class TestIEOrchestratorComponentFailures(unittest.TestCase):
    """Each component can fail independently."""

    def test_experiment_failure_continues_with_defaults(self):
        """Experiment failure → continue with default weights."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(fail_get=True),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context())

        assert result.experiment is None
        assert result.suggested_price == 29.99  # Scoring still works
        assert any("Experiment selection failed" in w for w in result.warnings)

    def test_context_failure_continues_without_history(self):
        """Context injection failure → score without historical context."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(fail=True),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context())

        assert result.category_context is None
        assert result.suggested_price == 29.99
        assert any("Context injection failed" in w for w in result.warnings)

    def test_scoring_failure_returns_fallback(self):
        """Scoring engine failure with fallback enabled → FALLBACK."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(fail=True),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
            config=IEOrchestratorConfig(fallback_on_error=True),
        )
        result = orch.generate_recommendation(make_product_context())

        assert result.status == IEStatus.FALLBACK
        assert result.direction == "hold"

    def test_scoring_failure_returns_error_when_no_fallback(self):
        """Scoring engine failure with fallback disabled → ERROR."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(fail=True),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
            config=IEOrchestratorConfig(fallback_on_error=False),
        )
        result = orch.generate_recommendation(make_product_context())

        assert result.status == IEStatus.ERROR

    def test_calibration_failure_uses_raw_confidence(self):
        """Calibration failure → use raw confidence instead."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(fail=True),
        )
        result = orch.generate_recommendation(make_product_context())

        assert result.raw_confidence == 0.75
        assert result.calibrated_confidence == 0.75  # Falls back to raw
        assert result.calibration is None
        assert any("Calibration failed" in w for w in result.warnings)

    def test_experiment_recording_failure_doesnt_break_result(self):
        """Record assignment failure is fire-and-forget."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(fail_record=True),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context())

        # Result still valid despite recording failure
        assert result.suggested_price == 29.99
        assert result.experiment is not None


class TestIEOrchestratorStrategyOverrides(unittest.TestCase):
    """Experiment strategy overrides applied to scoring."""

    def test_strategy_overrides_injected_into_context(self):
        """Strategy overrides appear in product_context for ScoringEngine."""
        engine = make_scoring_engine()
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(config={
                "strategy_name": "aggressive",
                "arm_index": 2,
                "is_exploration": True,
                "magnitude_multiplier": 1.5,
                "guardrail_overrides": {"max_change_pct": 15},
                "weight_overrides": {"urgency": 0.4},
            }),
            scoring_engine=engine,
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        orch.generate_recommendation(make_product_context())

        # Verify scoring engine received strategy overrides
        call_args = engine.score.call_args[0][0]
        assert "strategy_overrides" in call_args
        assert call_args["strategy_overrides"]["magnitude_multiplier"] == 1.5
        assert call_args["strategy_overrides"]["is_exploration"] is True


class TestIEOrchestratorTimings(unittest.TestCase):
    """Latency tracking and observability."""

    def test_timings_recorded_for_all_components(self):
        """Each component gets a ComponentTiming entry."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context())

        component_names = [t.component for t in result.timings]
        assert "experiment_manager" in component_names
        assert "context_injector" in component_names
        assert "scoring_engine" in component_names
        assert "calibrator" in component_names
        assert result.total_duration_ms > 0

    def test_failed_components_show_in_timings(self):
        """Failed components have success=False and error message."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(fail_get=True),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context())

        exp_timing = [t for t in result.timings if t.component == "experiment_manager"][0]
        assert exp_timing.success is False
        assert exp_timing.error is not None


class TestIEOrchestratorEdgeCases(unittest.TestCase):
    """Edge cases and boundary conditions."""

    def test_no_category_skips_experiments_and_context(self):
        """Without category_id, experiments and context injection are skipped."""
        exp_mgr = make_experiment_manager()
        ctx_inj = make_context_injector()
        orch = IEOrchestrator(
            experiment_manager=exp_mgr,
            scoring_engine=make_scoring_engine(),
            context_injector=ctx_inj,
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context(category_id=None))

        exp_mgr.get_experiment_config.assert_not_called()
        ctx_inj.get_scoring_context.assert_not_called()
        assert result.experiment is None
        assert result.category_context is None

    def test_zero_current_price_handles_gracefully(self):
        """Zero current price → change_pct = 0, no division error."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine({"suggested_price": 10.0, "confidence": 0.5}),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context(current_price=0.0))

        assert result.change_pct == 0.0  # No division by zero

    def test_disabled_experiments_config(self):
        """enable_experiments=False skips experiment selection."""
        exp_mgr = make_experiment_manager()
        orch = IEOrchestrator(
            experiment_manager=exp_mgr,
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
            config=IEOrchestratorConfig(enable_experiments=False),
        )
        result = orch.generate_recommendation(make_product_context())

        exp_mgr.get_experiment_config.assert_not_called()
        assert result.experiment is None

    def test_disabled_calibration_config(self):
        """enable_calibration=False uses raw confidence."""
        cal = make_calibrator()
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=cal,
            config=IEOrchestratorConfig(enable_calibration=False),
        )
        result = orch.generate_recommendation(make_product_context())

        cal.calibrate.assert_not_called()
        assert result.calibrated_confidence == result.raw_confidence

    def test_frozen_dataclasses_are_immutable(self):
        """IERecommendation and ExperimentContext are frozen."""
        orch = IEOrchestrator(
            experiment_manager=make_experiment_manager(),
            scoring_engine=make_scoring_engine(),
            context_injector=make_context_injector(),
            calibrator=make_calibrator(),
        )
        result = orch.generate_recommendation(make_product_context())

        with self.assertRaises(AttributeError):
            result.suggested_price = 999.99  # type: ignore


if __name__ == "__main__":
    unittest.main()


    