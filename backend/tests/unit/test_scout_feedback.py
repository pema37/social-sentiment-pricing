"""
Tests for ScoutFeedbackAnalyzer — Phase 3 backward learning for Scout.

Place at: backend/tests/unit/test_scout_feedback.py

Tests cover:
  - OutcomeWithDataQuality properties (was_successful, was_failure, has_data_gap)
  - ScrapingPriorityAdjustment properties
  - ScoutFeedbackReport properties
  - ScoutFeedbackAnalyzer.analyze (happy path, empty, insufficient failures)
  - Competitor gap detection
  - Sentiment gap detection
  - Freshness gap detection
  - Priority ordering and confidence
  - Category summaries
  - Edge cases

Run: pytest backend/tests/unit/test_scout_feedback.py -v
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
    from services.scoring.learning.scout_feedback import OutcomeWithDataQuality
    defaults = dict(
        recommendation_id="rec-001",
        category="electronics",
        action="accepted",
        revenue_delta_pct=3.0,
        data_quality_score=0.7,
        competitor_count=4,
        sentiment_available=True,
        days_since_last_scrape=2.0,
        price_data_completeness=0.9,
        sentiment_data_completeness=0.85,
    )
    defaults.update(kwargs)
    return OutcomeWithDataQuality(**defaults)


def _make_failure(**kwargs):
    """Convenience: outcome that is a failure."""
    defaults = dict(action="accepted", revenue_delta_pct=-3.0)
    defaults.update(kwargs)
    return _make_outcome(**defaults)


def _make_success(**kwargs):
    """Convenience: outcome that is a success."""
    defaults = dict(action="accepted", revenue_delta_pct=5.0)
    defaults.update(kwargs)
    return _make_outcome(**defaults)


# ──────────────────────────────────────────────────────────
# TESTS: OutcomeWithDataQuality Properties
# ──────────────────────────────────────────────────────────

class TestOutcomeWithDataQuality:

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

    def test_was_failure_ignored(self):
        o = _make_outcome(action="ignored")
        assert o.was_failure is True

    def test_was_failure_negative_revenue(self):
        o = _make_outcome(action="accepted", revenue_delta_pct=-2.0)
        assert o.was_failure is True

    def test_not_failure_positive(self):
        o = _make_outcome(action="accepted", revenue_delta_pct=5.0)
        assert o.was_failure is False

    def test_has_data_gap_low_quality(self):
        o = _make_outcome(data_quality_score=0.3)
        assert o.has_data_gap is True

    def test_has_data_gap_few_competitors(self):
        o = _make_outcome(competitor_count=1)
        assert o.has_data_gap is True

    def test_has_data_gap_no_sentiment(self):
        o = _make_outcome(sentiment_available=False)
        assert o.has_data_gap is True

    def test_has_data_gap_low_price_completeness(self):
        o = _make_outcome(price_data_completeness=0.5)
        assert o.has_data_gap is True

    def test_has_data_gap_low_sentiment_completeness(self):
        o = _make_outcome(sentiment_data_completeness=0.5)
        assert o.has_data_gap is True

    def test_has_data_gap_stale(self):
        o = _make_outcome(days_since_last_scrape=10.0)
        assert o.has_data_gap is True

    def test_no_data_gap(self):
        o = _make_outcome()
        assert o.has_data_gap is False


# ──────────────────────────────────────────────────────────
# TESTS: ScrapingPriorityAdjustment
# ──────────────────────────────────────────────────────────

class TestScrapingPriorityAdjustment:

    def test_is_significant(self):
        from services.scoring.learning.scout_feedback import ScrapingPriorityAdjustment
        adj = ScrapingPriorityAdjustment(
            category="electronics", adjustment_type="competitor_price",
            priority_boost=0.3, reason="test",
            confidence=0.5,
        )
        assert adj.is_significant is True

    def test_not_significant_low_boost(self):
        from services.scoring.learning.scout_feedback import ScrapingPriorityAdjustment
        adj = ScrapingPriorityAdjustment(
            category="electronics", adjustment_type="competitor_price",
            priority_boost=0.01, reason="test",
            confidence=0.5,
        )
        assert adj.is_significant is False

    def test_not_significant_low_confidence(self):
        from services.scoring.learning.scout_feedback import ScrapingPriorityAdjustment
        adj = ScrapingPriorityAdjustment(
            category="electronics", adjustment_type="competitor_price",
            priority_boost=0.3, reason="test",
            confidence=0.1,
        )
        assert adj.is_significant is False


# ──────────────────────────────────────────────────────────
# TESTS: ScoutFeedbackReport
# ──────────────────────────────────────────────────────────

class TestScoutFeedbackReport:

    def test_significant_adjustments_filter(self):
        from services.scoring.learning.scout_feedback import (
            ScoutFeedbackReport, ScrapingPriorityAdjustment,
        )
        adj1 = ScrapingPriorityAdjustment(
            category="a", adjustment_type="t", priority_boost=0.3,
            reason="r", confidence=0.5,
        )
        adj2 = ScrapingPriorityAdjustment(
            category="b", adjustment_type="t", priority_boost=0.01,
            reason="r", confidence=0.5,
        )
        report = ScoutFeedbackReport(
            analyzed_at=datetime.now(UTC),
            total_outcomes_analyzed=10,
            total_failures=5,
            total_failures_with_data_gaps=3,
            adjustments=[adj1, adj2],
            category_summaries={},
        )
        sig = report.significant_adjustments
        assert len(sig) == 1
        assert sig[0].category == "a"

    def test_summary_string(self):
        from services.scoring.learning.scout_feedback import ScoutFeedbackReport
        report = ScoutFeedbackReport(
            analyzed_at=datetime.now(UTC),
            total_outcomes_analyzed=20,
            total_failures=8,
            total_failures_with_data_gaps=5,
            adjustments=[],
            category_summaries={},
        )
        s = report.summary
        assert "20 outcomes" in s
        assert "8 failures" in s


# ──────────────────────────────────────────────────────────
# TESTS: Analyzer — Happy Path
# ──────────────────────────────────────────────────────────

class TestAnalyzerHappyPath:

    def _analyzer(self):
        from services.scoring.learning.scout_feedback import ScoutFeedbackAnalyzer
        return ScoutFeedbackAnalyzer()

    def test_empty_outcomes(self):
        report = self._analyzer().analyze([])
        assert report.total_outcomes_analyzed == 0
        assert report.adjustments == []

    def test_no_failures(self):
        """All successes → no adjustments."""
        outcomes = [_make_success(recommendation_id=f"r-{i}") for i in range(10)]
        report = self._analyzer().analyze(outcomes)
        assert report.total_failures == 0
        assert report.adjustments == []

    def test_insufficient_failures(self):
        """< 3 failures → no adjustments."""
        outcomes = [_make_success(recommendation_id=f"r-{i}") for i in range(10)]
        outcomes.append(_make_failure(recommendation_id="f-1"))
        outcomes.append(_make_failure(recommendation_id="f-2"))
        report = self._analyzer().analyze(outcomes)
        assert report.adjustments == []

    def test_category_summaries(self):
        """Category summaries populated."""
        outcomes = [
            _make_success(recommendation_id=f"s-{i}", category="electronics")
            for i in range(5)
        ] + [
            _make_failure(recommendation_id=f"f-{i}", category="electronics")
            for i in range(5)
        ]
        report = self._analyzer().analyze(outcomes)
        assert "electronics" in report.category_summaries
        summary = report.category_summaries["electronics"]
        assert summary["total"] == 10
        assert summary["failures"] == 5

    def test_adjustments_sorted_by_priority(self):
        """Adjustments sorted by priority_boost descending."""
        outcomes = []
        # Failures with low competitor count
        for i in range(5):
            outcomes.append(_make_failure(
                recommendation_id=f"fc-{i}",
                competitor_count=0,
                revenue_delta_pct=-5.0,
            ))
        # Failures with no sentiment
        for i in range(5):
            outcomes.append(_make_failure(
                recommendation_id=f"fs-{i}",
                sentiment_available=False,
                revenue_delta_pct=-3.0,
            ))
        # Some successes for comparison
        for i in range(10):
            outcomes.append(_make_success(
                recommendation_id=f"s-{i}",
                competitor_count=5,
            ))

        report = self._analyzer().analyze(outcomes)
        if len(report.adjustments) >= 2:
            assert report.adjustments[0].priority_boost >= report.adjustments[1].priority_boost


# ──────────────────────────────────────────────────────────
# TESTS: Competitor Gap Detection
# ──────────────────────────────────────────────────────────

class TestCompetitorGapDetection:

    def _analyzer(self):
        from services.scoring.learning.scout_feedback import ScoutFeedbackAnalyzer
        return ScoutFeedbackAnalyzer()

    def test_low_competitor_count_detected(self):
        """Failures with < 2 competitors → competitor_price adjustment."""
        outcomes = []
        for i in range(5):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                competitor_count=0,
                revenue_delta_pct=-4.0,
            ))
        for i in range(5):
            outcomes.append(_make_success(
                recommendation_id=f"s-{i}",
                competitor_count=5,
            ))
        report = self._analyzer().analyze(outcomes)
        comp_adjs = [a for a in report.adjustments if a.adjustment_type == "competitor_price"]
        assert len(comp_adjs) >= 1
        assert comp_adjs[0].priority_boost > 0

    def test_low_price_completeness_detected(self):
        """Failures with low price_data_completeness → adjustment."""
        outcomes = []
        for i in range(5):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                price_data_completeness=0.3,
                revenue_delta_pct=-3.0,
            ))
        for i in range(5):
            outcomes.append(_make_success(recommendation_id=f"s-{i}"))
        report = self._analyzer().analyze(outcomes)
        comp_adjs = [a for a in report.adjustments if a.adjustment_type == "competitor_price"]
        assert len(comp_adjs) >= 1

    def test_no_gap_when_failures_have_good_data(self):
        """Failures with good competitor data → no competitor adjustment."""
        outcomes = []
        for i in range(5):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                competitor_count=5,
                price_data_completeness=0.95,
                revenue_delta_pct=-2.0,
            ))
        for i in range(5):
            outcomes.append(_make_success(
                recommendation_id=f"s-{i}",
                competitor_count=5,
            ))
        report = self._analyzer().analyze(outcomes)
        comp_adjs = [a for a in report.adjustments if a.adjustment_type == "competitor_price"]
        # May or may not have adjustments, but shouldn't be high priority
        for adj in comp_adjs:
            assert adj.priority_boost < 0.5


# ──────────────────────────────────────────────────────────
# TESTS: Sentiment Gap Detection
# ──────────────────────────────────────────────────────────

class TestSentimentGapDetection:

    def _analyzer(self):
        from services.scoring.learning.scout_feedback import ScoutFeedbackAnalyzer
        return ScoutFeedbackAnalyzer()

    def test_no_sentiment_detected(self):
        """Failures with no sentiment → sentiment adjustment."""
        outcomes = []
        for i in range(5):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                sentiment_available=False,
                revenue_delta_pct=-3.0,
            ))
        for i in range(5):
            outcomes.append(_make_success(recommendation_id=f"s-{i}"))
        report = self._analyzer().analyze(outcomes)
        sent_adjs = [a for a in report.adjustments if a.adjustment_type == "sentiment"]
        assert len(sent_adjs) >= 1

    def test_low_sentiment_completeness_detected(self):
        """Failures with low sentiment completeness → adjustment."""
        outcomes = []
        for i in range(5):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                sentiment_data_completeness=0.3,
                revenue_delta_pct=-3.0,
            ))
        for i in range(5):
            outcomes.append(_make_success(recommendation_id=f"s-{i}"))
        report = self._analyzer().analyze(outcomes)
        sent_adjs = [a for a in report.adjustments if a.adjustment_type == "sentiment"]
        assert len(sent_adjs) >= 1


# ──────────────────────────────────────────────────────────
# TESTS: Freshness Gap Detection
# ──────────────────────────────────────────────────────────

class TestFreshnessGapDetection:

    def _analyzer(self):
        from services.scoring.learning.scout_feedback import ScoutFeedbackAnalyzer
        return ScoutFeedbackAnalyzer()

    def test_stale_data_detected(self):
        """Failures with stale data → freshness adjustment."""
        outcomes = []
        for i in range(5):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                days_since_last_scrape=14.0,
                revenue_delta_pct=-4.0,
            ))
        for i in range(5):
            outcomes.append(_make_success(
                recommendation_id=f"s-{i}",
                days_since_last_scrape=1.0,
            ))
        report = self._analyzer().analyze(outcomes)
        fresh_adjs = [a for a in report.adjustments if a.adjustment_type == "freshness"]
        assert len(fresh_adjs) >= 1
        assert fresh_adjs[0].priority_boost > 0

    def test_fresh_data_no_adjustment(self):
        """Failures with fresh data → no freshness adjustment."""
        outcomes = []
        for i in range(5):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                days_since_last_scrape=1.0,
                revenue_delta_pct=-2.0,
            ))
        for i in range(5):
            outcomes.append(_make_success(recommendation_id=f"s-{i}"))
        report = self._analyzer().analyze(outcomes)
        fresh_adjs = [a for a in report.adjustments if a.adjustment_type == "freshness"]
        assert len(fresh_adjs) == 0


# ──────────────────────────────────────────────────────────
# TESTS: Multiple Categories
# ──────────────────────────────────────────────────────────

class TestMultipleCategories:

    def _analyzer(self):
        from services.scoring.learning.scout_feedback import ScoutFeedbackAnalyzer
        return ScoutFeedbackAnalyzer()

    def test_separate_category_analysis(self):
        """Each category analyzed independently."""
        outcomes = []
        # Electronics: failures with low competitors
        for i in range(4):
            outcomes.append(_make_failure(
                recommendation_id=f"ef-{i}", category="electronics",
                competitor_count=0, revenue_delta_pct=-3.0,
            ))
        for i in range(4):
            outcomes.append(_make_success(
                recommendation_id=f"es-{i}", category="electronics",
                competitor_count=5,
            ))
        # Fashion: all good
        for i in range(8):
            outcomes.append(_make_success(
                recommendation_id=f"fs-{i}", category="fashion",
            ))

        report = self._analyzer().analyze(outcomes)
        assert "electronics" in report.category_summaries
        assert "fashion" in report.category_summaries
        # Electronics should have adjustments, fashion shouldn't
        elec_adjs = [a for a in report.adjustments if a.category == "electronics"]
        fash_adjs = [a for a in report.adjustments if a.category == "fashion"]
        assert len(elec_adjs) >= 1
        assert len(fash_adjs) == 0


# ──────────────────────────────────────────────────────────
# TESTS: Edge Cases
# ──────────────────────────────────────────────────────────

class TestScoutFeedbackEdgeCases:

    def _analyzer(self):
        from services.scoring.learning.scout_feedback import ScoutFeedbackAnalyzer
        return ScoutFeedbackAnalyzer()

    def test_all_failures(self):
        """100% failure rate doesn't crash."""
        outcomes = [
            _make_failure(recommendation_id=f"f-{i}", competitor_count=0)
            for i in range(10)
        ]
        report = self._analyzer().analyze(outcomes)
        assert report.total_failures == 10

    def test_none_revenue_delta(self):
        """None revenue_delta_pct handled gracefully."""
        outcomes = [
            _make_outcome(recommendation_id=f"r-{i}", revenue_delta_pct=None, action="ignored")
            for i in range(10)
        ]
        report = self._analyzer().analyze(outcomes)
        assert report.total_outcomes_analyzed == 10

    def test_priority_boost_capped_at_1(self):
        """Priority boost never exceeds 1.0."""
        outcomes = []
        for i in range(20):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                competitor_count=0,
                revenue_delta_pct=-50.0,
            ))
        for i in range(5):
            outcomes.append(_make_success(
                recommendation_id=f"s-{i}",
                competitor_count=10,
            ))
        report = self._analyzer().analyze(outcomes)
        for adj in report.adjustments:
            assert adj.priority_boost <= 1.0

    def test_confidence_capped_at_1(self):
        """Confidence never exceeds 1.0."""
        outcomes = []
        for i in range(30):
            outcomes.append(_make_failure(
                recommendation_id=f"f-{i}",
                sentiment_available=False,
            ))
        for i in range(5):
            outcomes.append(_make_success(recommendation_id=f"s-{i}"))
        report = self._analyzer().analyze(outcomes)
        for adj in report.adjustments:
            assert adj.confidence <= 1.0


            