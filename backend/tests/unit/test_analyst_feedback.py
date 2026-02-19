"""
Tests for AnalystFeedbackAnalyzer — Phase 3 scoring weight adjustments.

Place at: backend/tests/unit/test_analyst_feedback.py

Tests cover:
  - OutcomeWithComponents properties
  - ComponentAnalysis structure
  - WeightAdjustmentRecommendation properties
  - AnalystFeedbackReport properties
  - AnalystFeedbackAnalyzer.analyze (happy path, insufficient data, auto-apply)
  - Component analysis (separation, correlation, reasoning)
  - Weight computation (normalization, dampening, bounds)
  - Pearson r per-component
  - Edge cases

Run: pytest backend/tests/unit/test_analyst_feedback.py -v
"""

import sys
import pytest
from datetime import datetime, UTC


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

def _make_outcome(**kwargs):
    from services.scoring.learning.analyst_feedback import OutcomeWithComponents
    defaults = dict(
        recommendation_id="rec-001",
        category="electronics",
        action="accepted",
        revenue_delta_pct=3.0,
        confidence_score=0.7,
        elasticity_score=0.6,
        position_score=0.5,
        urgency_score=0.4,
        data_quality_score=0.7,
        elasticity_weight=0.30,
        position_weight=0.25,
        urgency_weight=0.20,
        data_quality_weight=0.25,
    )
    defaults.update(kwargs)
    return OutcomeWithComponents(**defaults)


def _make_success(**kwargs):
    defaults = dict(action="accepted", revenue_delta_pct=5.0)
    defaults.update(kwargs)
    return _make_outcome(**defaults)


def _make_failure(**kwargs):
    defaults = dict(action="accepted", revenue_delta_pct=-3.0)
    defaults.update(kwargs)
    return _make_outcome(**defaults)


def _make_predictive_dataset(n=20):
    """Dataset where elasticity predicts success, urgency anti-predicts."""
    outcomes = []
    for i in range(n):
        is_success = i < n // 2
        outcomes.append(_make_outcome(
            recommendation_id=f"r-{i}",
            action="accepted",
            revenue_delta_pct=5.0 if is_success else -3.0,
            # Elasticity: high for successes, low for failures
            elasticity_score=0.8 if is_success else 0.2,
            # Urgency: high for failures, low for successes (anti-predicts)
            urgency_score=0.2 if is_success else 0.8,
            # Position/quality: no signal
            position_score=0.5,
            data_quality_score=0.5,
        ))
    return outcomes


# ──────────────────────────────────────────────────────────
# TESTS: OutcomeWithComponents
# ──────────────────────────────────────────────────────────

class TestOutcomeWithComponents:

    def test_was_successful(self):
        o = _make_outcome(action="accepted", revenue_delta_pct=5.0)
        assert o.was_successful is True

    def test_was_successful_modified(self):
        o = _make_outcome(action="modified", revenue_delta_pct=2.0)
        assert o.was_successful is True

    def test_not_successful_negative(self):
        o = _make_outcome(action="accepted", revenue_delta_pct=-1.0)
        assert o.was_successful is False

    def test_not_successful_rejected(self):
        o = _make_outcome(action="rejected", revenue_delta_pct=5.0)
        assert o.was_successful is False

    def test_was_failure_rejected(self):
        o = _make_outcome(action="rejected")
        assert o.was_failure is True

    def test_was_failure_negative_accepted(self):
        o = _make_outcome(action="accepted", revenue_delta_pct=-2.0)
        assert o.was_failure is True

    def test_component_scores(self):
        o = _make_outcome(
            elasticity_score=0.6, position_score=0.5,
            urgency_score=0.4, data_quality_score=0.7,
        )
        scores = o.component_scores
        assert scores["elasticity"] == 0.6
        assert scores["position"] == 0.5
        assert scores["urgency"] == 0.4
        assert scores["data_quality"] == 0.7

    def test_component_weights(self):
        o = _make_outcome()
        weights = o.component_weights
        assert abs(sum(weights.values()) - 1.0) < 0.01


# ──────────────────────────────────────────────────────────
# TESTS: WeightAdjustmentRecommendation
# ──────────────────────────────────────────────────────────

class TestWeightAdjustmentRecommendation:

    def test_summary_with_changes(self):
        from services.scoring.learning.analyst_feedback import (
            WeightAdjustmentRecommendation, ComponentAnalysis,
        )
        rec = WeightAdjustmentRecommendation(
            category="electronics", n_outcomes=50,
            n_successes=30, n_failures=20,
            component_analyses=[],
            recommended_weights={"elasticity": 0.35, "position": 0.25,
                                 "urgency": 0.15, "data_quality": 0.25},
            current_weights={"elasticity": 0.30, "position": 0.25,
                             "urgency": 0.20, "data_quality": 0.25},
            max_weight_change=0.05,
            should_apply=True,
            apply_reason="test",
        )
        s = rec.summary
        assert "electronics" in s
        assert "50 outcomes" in s

    def test_summary_no_changes(self):
        from services.scoring.learning.analyst_feedback import WeightAdjustmentRecommendation
        rec = WeightAdjustmentRecommendation(
            category="electronics", n_outcomes=50,
            n_successes=30, n_failures=20,
            component_analyses=[],
            recommended_weights={"elasticity": 0.30, "position": 0.25,
                                 "urgency": 0.20, "data_quality": 0.25},
            current_weights={"elasticity": 0.30, "position": 0.25,
                             "urgency": 0.20, "data_quality": 0.25},
            max_weight_change=0.0,
            should_apply=False,
        )
        s = rec.summary
        assert "no changes" in s


# ──────────────────────────────────────────────────────────
# TESTS: AnalystFeedbackReport
# ──────────────────────────────────────────────────────────

class TestAnalystFeedbackReport:

    def test_categories_with_changes(self):
        from services.scoring.learning.analyst_feedback import (
            AnalystFeedbackReport, WeightAdjustmentRecommendation,
        )
        rec1 = WeightAdjustmentRecommendation(
            category="a", n_outcomes=20, n_successes=10, n_failures=10,
            component_analyses=[], recommended_weights={}, current_weights={},
            should_apply=True,
        )
        rec2 = WeightAdjustmentRecommendation(
            category="b", n_outcomes=20, n_successes=10, n_failures=10,
            component_analyses=[], recommended_weights={}, current_weights={},
            should_apply=False,
        )
        report = AnalystFeedbackReport(
            analyzed_at=datetime.now(UTC),
            total_outcomes=40,
            category_recommendations=[rec1, rec2],
        )
        assert len(report.categories_with_changes) == 1

    def test_summary_string(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackReport
        report = AnalystFeedbackReport(
            analyzed_at=datetime.now(UTC),
            total_outcomes=100,
            category_recommendations=[],
        )
        assert "100 outcomes" in report.summary


# ──────────────────────────────────────────────────────────
# TESTS: Analyzer — Happy Path
# ──────────────────────────────────────────────────────────

class TestAnalyzerHappyPath:

    def _analyzer(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        return AnalystFeedbackAnalyzer()

    def test_empty_outcomes(self):
        report = self._analyzer().analyze([])
        assert report.total_outcomes == 0
        assert report.category_recommendations == []

    def test_insufficient_outcomes(self):
        """< 10 outcomes → no recommendation."""
        outcomes = [_make_success(recommendation_id=f"r-{i}") for i in range(5)]
        outcomes += [_make_failure(recommendation_id=f"f-{i}") for i in range(3)]
        report = self._analyzer().analyze(outcomes)
        assert len(report.category_recommendations) == 0

    def test_insufficient_failures(self):
        """< 3 failures → no recommendation."""
        outcomes = [_make_success(recommendation_id=f"r-{i}") for i in range(15)]
        outcomes += [_make_failure(recommendation_id=f"f-{i}") for i in range(2)]
        report = self._analyzer().analyze(outcomes)
        assert len(report.category_recommendations) == 0

    def test_insufficient_successes(self):
        """< 3 successes → no recommendation."""
        outcomes = [_make_failure(recommendation_id=f"f-{i}") for i in range(15)]
        outcomes += [_make_success(recommendation_id=f"s-{i}") for i in range(2)]
        report = self._analyzer().analyze(outcomes)
        assert len(report.category_recommendations) == 0

    def test_sufficient_data_produces_recommendation(self):
        """Balanced dataset → recommendation produced."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        assert len(report.category_recommendations) == 1
        rec = report.category_recommendations[0]
        assert rec.category == "electronics"
        assert rec.n_outcomes == 20

    def test_component_analyses_present(self):
        """4 component analyses in recommendation."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        assert len(rec.component_analyses) == 4
        names = {a.component for a in rec.component_analyses}
        assert names == {"elasticity", "position", "urgency", "data_quality"}


# ──────────────────────────────────────────────────────────
# TESTS: Component Analysis
# ──────────────────────────────────────────────────────────

class TestComponentAnalysis:

    def _analyzer(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        return AnalystFeedbackAnalyzer()

    def test_predictive_component_positive_separation(self):
        """Elasticity predicts success → positive separation."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        elasticity_analysis = next(a for a in rec.component_analyses if a.component == "elasticity")
        assert elasticity_analysis.separation > 0
        assert "predicts success" in elasticity_analysis.reasoning

    def test_anti_predictive_component_negative_separation(self):
        """Urgency anti-predicts → negative separation."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        urgency_analysis = next(a for a in rec.component_analyses if a.component == "urgency")
        assert urgency_analysis.separation < 0
        assert "anti-predicts" in urgency_analysis.reasoning

    def test_neutral_component_weak_signal(self):
        """Position has no signal → weak reasoning."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        position_analysis = next(a for a in rec.component_analyses if a.component == "position")
        assert abs(position_analysis.separation) < 0.1
        assert "weak" in position_analysis.reasoning

    def test_success_failure_means(self):
        """Success and failure means are computed correctly."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        elasticity = next(a for a in rec.component_analyses if a.component == "elasticity")
        assert elasticity.success_mean > elasticity.failure_mean


# ──────────────────────────────────────────────────────────
# TESTS: Weight Computation
# ──────────────────────────────────────────────────────────

class TestWeightComputation:

    def _analyzer(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        return AnalystFeedbackAnalyzer()

    def test_weights_sum_to_one(self):
        """Recommended weights always sum to 1.0."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        total = sum(rec.recommended_weights.values())
        assert abs(total - 1.0) < 0.01

    def test_weights_within_bounds(self):
        """No weight below 10% or above 50%."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        for comp, w in rec.recommended_weights.items():
            assert w >= 0.10 - 0.001, f"{comp} weight {w} below min"
            assert w <= 0.50 + 0.001, f"{comp} weight {w} above max"

    def test_predictive_component_gets_higher_weight(self):
        """Elasticity (strong predictor) gets higher recommended weight than urgency (anti)."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        # Elasticity should be recommended higher than urgency
        assert rec.recommended_weights["elasticity"] >= rec.recommended_weights["urgency"]

    def test_dampened_adjustment(self):
        """Weights blend 80% current + 20% ideal (conservative)."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        # Max change should be moderate due to dampening
        assert rec.max_weight_change < 0.15  # 80/20 blend limits change

    def test_no_change_when_all_equal(self):
        """All components equally predictive → minimal weight changes."""
        outcomes = []
        for i in range(20):
            is_success = i < 10
            outcomes.append(_make_outcome(
                recommendation_id=f"r-{i}",
                revenue_delta_pct=3.0 if is_success else -2.0,
                elasticity_score=0.5,
                position_score=0.5,
                urgency_score=0.5,
                data_quality_score=0.5,
            ))
        report = self._analyzer().analyze(outcomes)
        if report.category_recommendations:
            rec = report.category_recommendations[0]
            # All components equal → weights should barely change
            assert rec.max_weight_change < 0.05


# ──────────────────────────────────────────────────────────
# TESTS: Auto-Apply Logic
# ──────────────────────────────────────────────────────────

class TestAutoApplyLogic:

    def _analyzer(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        return AnalystFeedbackAnalyzer()

    def test_small_change_auto_applies(self):
        """Change <= 4% → should_apply=True."""
        outcomes = _make_predictive_dataset(n=20)
        report = self._analyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        if rec.max_weight_change <= 0.04 and rec.max_weight_change > 0.005:
            assert rec.should_apply is True

    def test_large_change_manual_review(self):
        """Change > 4% → should_apply=False, needs manual review."""
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        # We test the reason generation directly
        reason = AnalystFeedbackAnalyzer._get_apply_reason(0.06, [])
        assert "manual review" in reason.lower()

    def test_tiny_change_not_applied(self):
        """Change <= 0.5% → too small to matter."""
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        reason = AnalystFeedbackAnalyzer._get_apply_reason(0.003, [])
        assert "too small" in reason.lower()


# ──────────────────────────────────────────────────────────
# TESTS: Pearson r Per-Component
# ──────────────────────────────────────────────────────────

class TestPearsonRPerComponent:

    def test_perfect_correlation(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        records = [
            _make_outcome(
                recommendation_id=f"r-{i}",
                elasticity_score=float(i) / 10,
                revenue_delta_pct=float(i),
            )
            for i in range(1, 11)
        ]
        r = AnalystFeedbackAnalyzer._pearson_r("elasticity", records)
        assert r is not None
        assert r > 0.99

    def test_insufficient_pairs(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        records = [_make_outcome(recommendation_id=f"r-{i}") for i in range(3)]
        r = AnalystFeedbackAnalyzer._pearson_r("elasticity", records)
        assert r is None

    def test_none_revenue_excluded(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        records = [
            _make_outcome(recommendation_id=f"r-{i}", revenue_delta_pct=None)
            for i in range(10)
        ]
        r = AnalystFeedbackAnalyzer._pearson_r("elasticity", records)
        assert r is None

    def test_correlation_present_in_analysis(self):
        """Component analysis includes correlation value."""
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        outcomes = _make_predictive_dataset(n=20)
        report = AnalystFeedbackAnalyzer().analyze(outcomes)
        rec = report.category_recommendations[0]
        elasticity = next(a for a in rec.component_analyses if a.component == "elasticity")
        assert elasticity.correlation_with_revenue is not None


# ──────────────────────────────────────────────────────────
# TESTS: Multiple Categories
# ──────────────────────────────────────────────────────────

class TestMultipleCategories:

    def _analyzer(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        return AnalystFeedbackAnalyzer()

    def test_separate_categories(self):
        """Different categories get independent analyses."""
        elec = [_make_outcome(
            recommendation_id=f"e-{i}", category="electronics",
            action="accepted",
            revenue_delta_pct=5.0 if i < 7 else -2.0,
            elasticity_score=0.8 if i < 7 else 0.2,
        ) for i in range(14)]

        fash = [_make_outcome(
            recommendation_id=f"f-{i}", category="fashion",
            action="accepted",
            revenue_delta_pct=4.0 if i < 6 else -3.0,
            position_score=0.8 if i < 6 else 0.2,
        ) for i in range(12)]

        report = self._analyzer().analyze(elec + fash)
        categories = {r.category for r in report.category_recommendations}
        assert "electronics" in categories
        assert "fashion" in categories


# ──────────────────────────────────────────────────────────
# TESTS: Edge Cases
# ──────────────────────────────────────────────────────────

class TestAnalystFeedbackEdgeCases:

    def _analyzer(self):
        from services.scoring.learning.analyst_feedback import AnalystFeedbackAnalyzer
        return AnalystFeedbackAnalyzer()

    def test_all_same_scores(self):
        """All components at 0.5 → no predictive signal → minimal changes."""
        outcomes = [
            _make_outcome(
                recommendation_id=f"r-{i}",
                revenue_delta_pct=3.0 if i % 2 == 0 else -2.0,
                elasticity_score=0.5,
                position_score=0.5,
                urgency_score=0.5,
                data_quality_score=0.5,
            )
            for i in range(20)
        ]
        report = self._analyzer().analyze(outcomes)
        # Should produce a recommendation but with minimal changes
        if report.category_recommendations:
            rec = report.category_recommendations[0]
            for comp, w in rec.recommended_weights.items():
                assert abs(w - rec.current_weights[comp]) < 0.05

    def test_all_zero_revenue(self):
        """Zero revenue deltas → no signal."""
        outcomes = [
            _make_outcome(
                recommendation_id=f"r-{i}",
                revenue_delta_pct=0.0,
                action="accepted" if i < 15 else "rejected",
            )
            for i in range(20)
        ]
        report = self._analyzer().analyze(outcomes)
        # Might not produce recommendations (rejected=failure, accepted+0=not successful)
        assert isinstance(report.category_recommendations, list)

    def test_extreme_scores(self):
        """Scores at 0.0 and 1.0 boundaries."""
        outcomes = []
        for i in range(10):
            outcomes.append(_make_success(
                recommendation_id=f"s-{i}",
                elasticity_score=1.0, urgency_score=0.0,
            ))
        for i in range(10):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                elasticity_score=0.0, urgency_score=1.0,
            ))
        report = self._analyzer().analyze(outcomes)
        assert len(report.category_recommendations) == 1
        rec = report.category_recommendations[0]
        # Even with extreme differences, weights stay in bounds
        for w in rec.recommended_weights.values():
            assert 0.10 <= w <= 0.50


            