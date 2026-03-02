"""
Tests for ContextInjector — Phase 2/3 context injection layer.

Place at: backend/tests/unit/test_context_injector.py

Tests cover:
  - ScoringContext defaults and construction
  - build_scoring_context (insufficient data, staleness, merchant bias,
    magnitude cap, calibration factor, data quality bonus)
  - build_agent_context (text generation, all paragraph branches)
  - build_minimal_context (one-liner summary)
  - build() convenience method
  - Edge cases (None features, zero outcomes, boundary values)

Run: pytest backend/tests/unit/test_context_injector.py -v
"""

import sys
import pytest
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock


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
# Fake CategoryFeatures (duck-typed to match feature_engineer.py)
# ──────────────────────────────────────────────────────────

class FakeConfidenceBand:
    def __init__(self, band_lower, band_upper, band_label, count,
                 avg_revenue_lift_pct):
        self.band_lower = band_lower
        self.band_upper = band_upper
        self.band_label = band_label
        self.count = count
        self.avg_revenue_lift_pct = avg_revenue_lift_pct


class FakeCategoryFeatures:
    """Mimics CategoryFeatures from feature_engineer.py."""

    def __init__(self, **kwargs):
        self.category = kwargs.get("category", "electronics")
        self.n_outcomes = kwargs.get("n_outcomes", 20)
        self.computed_at = kwargs.get("computed_at", datetime.now(UTC))
        self.acceptance_rate = kwargs.get("acceptance_rate", 0.75)
        self.accepted_rate = kwargs.get("accepted_rate", 0.60)
        self.modified_rate = kwargs.get("modified_rate", 0.15)
        self.rejected_rate = kwargs.get("rejected_rate", 0.25)
        self.mean_revenue_lift_pct = kwargs.get("mean_revenue_lift_pct", 3.5)
        self.positive_outcome_rate = kwargs.get("positive_outcome_rate", 0.65)
        self.mean_modification_ratio = kwargs.get("mean_modification_ratio", None)
        self.modification_direction_bias = kwargs.get("modification_direction_bias", 0.0)
        self.best_magnitude_bucket = kwargs.get("best_magnitude_bucket", "2-5%")
        self.mean_observed_elasticity = kwargs.get("mean_observed_elasticity", None)
        self.mean_margin_delta = kwargs.get("mean_margin_delta", None)
        self.confidence_band_performance = kwargs.get("confidence_band_performance", [])
        self.pct_with_impact_data = kwargs.get("pct_with_impact_data", 0.8)


# ──────────────────────────────────────────────────────────
# TESTS: ScoringContext defaults
# ──────────────────────────────────────────────────────────

class TestScoringContextDefaults:
    """Test ScoringContext dataclass defaults."""

    def test_default_values(self):
        from services.scoring.learning.context_injector import ScoringContext
        ctx = ScoringContext(category="test")
        assert ctx.category == "test"
        assert ctx.merchant_bias == 0.0
        assert ctx.merchant_acceptance_rate == 0.0
        assert ctx.suggested_magnitude_cap is None
        assert ctx.best_performing_magnitude is None
        assert ctx.confidence_calibration_factor == 1.0
        assert ctx.data_quality_bonus == 0.0
        assert ctx.avg_revenue_lift_pct is None
        assert ctx.positive_outcome_rate == 0.0
        assert ctx.n_historical_outcomes == 0
        assert ctx.features_computed_at is None
        assert ctx.is_stale is False


# ──────────────────────────────────────────────────────────
# TESTS: build_scoring_context
# ──────────────────────────────────────────────────────────

class TestBuildScoringContext:
    """Test structured context for the scoring engine."""

    def _injector(self):
        from services.scoring.learning.context_injector import ContextInjector
        return ContextInjector()

    def test_none_features_returns_default(self):
        """None features → default ScoringContext with 'unknown' category."""
        ctx = self._injector().build_scoring_context(None)
        assert ctx.category == "unknown"
        assert ctx.n_historical_outcomes == 0

    def test_insufficient_data(self):
        """Below MIN_OUTCOMES_FOR_CONTEXT → minimal context."""
        features = FakeCategoryFeatures(n_outcomes=3)
        ctx = self._injector().build_scoring_context(features)
        assert ctx.category == "electronics"
        assert ctx.n_historical_outcomes == 3
        assert ctx.merchant_bias == 0.0  # Not computed

    def test_sufficient_data_populates_fields(self):
        """Enough outcomes → full context populated."""
        features = FakeCategoryFeatures(n_outcomes=20)
        ctx = self._injector().build_scoring_context(features)
        assert ctx.n_historical_outcomes == 20
        assert ctx.merchant_acceptance_rate == 0.75
        assert ctx.best_performing_magnitude == "2-5%"
        assert ctx.positive_outcome_rate == 0.65
        assert ctx.avg_revenue_lift_pct == 3.5

    def test_staleness_detection(self):
        """Features older than 14 days flagged stale."""
        old_time = datetime.now(UTC) - timedelta(days=20)
        features = FakeCategoryFeatures(n_outcomes=20, computed_at=old_time)
        ctx = self._injector().build_scoring_context(features)
        assert ctx.is_stale is True

    def test_fresh_features_not_stale(self):
        """Recent features not flagged stale."""
        fresh_time = datetime.now(UTC) - timedelta(days=2)
        features = FakeCategoryFeatures(n_outcomes=20, computed_at=fresh_time)
        ctx = self._injector().build_scoring_context(features)
        assert ctx.is_stale is False

    def test_none_computed_at_not_stale(self):
        """None computed_at doesn't crash — not flagged stale."""
        features = FakeCategoryFeatures(n_outcomes=20, computed_at=None)
        ctx = self._injector().build_scoring_context(features)
        assert ctx.is_stale is False

    # ── Merchant bias ──

    def test_merchant_bias_zero_when_no_direction_bias(self):
        """Zero direction bias → zero merchant bias."""
        features = FakeCategoryFeatures(
            n_outcomes=20, modification_direction_bias=0.0
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.merchant_bias == 0.0

    def test_merchant_bias_zero_when_low_modified_rate(self):
        """Modified rate < 5% → zero merchant bias (insufficient signal)."""
        features = FakeCategoryFeatures(
            n_outcomes=20,
            modification_direction_bias=0.08,
            modified_rate=0.03,
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.merchant_bias == 0.0

    def test_merchant_bias_positive(self):
        """Positive direction bias → positive merchant bias."""
        features = FakeCategoryFeatures(
            n_outcomes=20,
            modification_direction_bias=0.05,
            modified_rate=0.20,
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.merchant_bias == 0.05

    def test_merchant_bias_clamped_high(self):
        """Large positive bias clamped to 0.10."""
        features = FakeCategoryFeatures(
            n_outcomes=20,
            modification_direction_bias=0.25,
            modified_rate=0.20,
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.merchant_bias == 0.10

    def test_merchant_bias_clamped_low(self):
        """Large negative bias clamped to -0.10."""
        features = FakeCategoryFeatures(
            n_outcomes=20,
            modification_direction_bias=-0.20,
            modified_rate=0.20,
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.merchant_bias == -0.10

    # ── Magnitude cap ──

    def test_magnitude_cap_2_5_pct(self):
        """Best bucket '2-5%' → cap at 0.05."""
        features = FakeCategoryFeatures(
            n_outcomes=20, best_magnitude_bucket="2-5%"
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.suggested_magnitude_cap == 0.05

    def test_magnitude_cap_0_2_pct(self):
        """Best bucket '0-2%' → cap at 0.02."""
        features = FakeCategoryFeatures(
            n_outcomes=20, best_magnitude_bucket="0-2%"
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.suggested_magnitude_cap == 0.02

    def test_magnitude_cap_10_plus(self):
        """Best bucket '10%+' → no cap (None)."""
        features = FakeCategoryFeatures(
            n_outcomes=20, best_magnitude_bucket="10%+"
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.suggested_magnitude_cap is None

    def test_magnitude_cap_none_bucket(self):
        """No best bucket → no cap."""
        features = FakeCategoryFeatures(
            n_outcomes=20, best_magnitude_bucket=None
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.suggested_magnitude_cap is None

    def test_magnitude_cap_unknown_bucket(self):
        """Unknown bucket string → None."""
        features = FakeCategoryFeatures(
            n_outcomes=20, best_magnitude_bucket="weird-bucket"
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.suggested_magnitude_cap is None

    # ── Calibration factor ──

    def test_calibration_factor_insufficient_data(self):
        """Below MIN_OUTCOMES_FOR_CALIBRATION → 1.0."""
        features = FakeCategoryFeatures(n_outcomes=8)
        ctx = self._injector().build_scoring_context(features)
        assert ctx.confidence_calibration_factor == 1.0

    def test_calibration_factor_no_bands(self):
        """No confidence band data → 1.0."""
        features = FakeCategoryFeatures(
            n_outcomes=20, confidence_band_performance=[]
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.confidence_calibration_factor == 1.0

    def test_calibration_factor_high_underperforms(self):
        """High-confidence underperforms low → factor < 1.0."""
        bands = [
            FakeConfidenceBand(0.0, 0.5, "0.0-0.5", 5, 8.0),   # low band, good
            FakeConfidenceBand(0.7, 1.0, "0.7-1.0", 5, 2.0),   # high band, worse
        ]
        features = FakeCategoryFeatures(
            n_outcomes=20, confidence_band_performance=bands
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.confidence_calibration_factor < 1.0
        assert ctx.confidence_calibration_factor >= 0.5

    def test_calibration_factor_high_outperforms(self):
        """High-confidence outperforms low → factor > 1.0."""
        bands = [
            FakeConfidenceBand(0.0, 0.5, "0.0-0.5", 5, 2.0),   # low band
            FakeConfidenceBand(0.7, 1.0, "0.7-1.0", 5, 10.0),  # high band, better
        ]
        features = FakeCategoryFeatures(
            n_outcomes=20, confidence_band_performance=bands
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.confidence_calibration_factor > 1.0
        assert ctx.confidence_calibration_factor <= 1.5

    def test_calibration_factor_insufficient_per_band(self):
        """Bands with count < 2 are excluded → 1.0."""
        bands = [
            FakeConfidenceBand(0.0, 0.5, "0.0-0.5", 1, 8.0),   # too few
            FakeConfidenceBand(0.7, 1.0, "0.7-1.0", 1, 2.0),   # too few
        ]
        features = FakeCategoryFeatures(
            n_outcomes=20, confidence_band_performance=bands
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.confidence_calibration_factor == 1.0

    # ── Data quality bonus ──

    def test_data_quality_bonus_insufficient_outcomes(self):
        """Below threshold → 0.0 bonus."""
        features = FakeCategoryFeatures(n_outcomes=3)
        ctx = self._injector().build_scoring_context(features)
        assert ctx.data_quality_bonus == 0.0

    def test_data_quality_bonus_rich_data(self):
        """High outcomes + high coverage → positive bonus."""
        features = FakeCategoryFeatures(
            n_outcomes=100, pct_with_impact_data=0.9
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.data_quality_bonus > 0.0
        assert ctx.data_quality_bonus <= 0.2

    def test_data_quality_bonus_max(self):
        """Very high outcomes + full coverage → max ~0.2."""
        features = FakeCategoryFeatures(
            n_outcomes=300, pct_with_impact_data=1.0
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.data_quality_bonus <= 0.2

    def test_data_quality_bonus_zero_coverage(self):
        """Zero impact coverage → only volume component."""
        features = FakeCategoryFeatures(
            n_outcomes=100, pct_with_impact_data=0.0
        )
        ctx = self._injector().build_scoring_context(features)
        # volume_score = min(0.1, 100/200) = 0.05
        # coverage_score = 0.0 * 0.1 = 0.0
        assert ctx.data_quality_bonus == 0.1


# ──────────────────────────────────────────────────────────
# TESTS: build_agent_context
# ──────────────────────────────────────────────────────────

class TestBuildAgentContext:
    """Test human-readable context for LLM prompts."""

    def _injector(self):
        from services.scoring.learning.context_injector import ContextInjector
        return ContextInjector()

    def test_none_features_empty_string(self):
        """None features → empty string."""
        result = self._injector().build_agent_context(None)
        assert result == ""

    def test_insufficient_data_empty_string(self):
        """Below threshold → empty string."""
        features = FakeCategoryFeatures(n_outcomes=3)
        result = self._injector().build_agent_context(features)
        assert result == ""

    def test_contains_category_name(self):
        """Output mentions the category."""
        features = FakeCategoryFeatures(category="electronics")
        result = self._injector().build_agent_context(features)
        assert "Electronics" in result

    def test_contains_outcome_count(self):
        """Output mentions the number of outcomes."""
        features = FakeCategoryFeatures(n_outcomes=42)
        result = self._injector().build_agent_context(features)
        assert "42" in result

    def test_positive_revenue_lift(self):
        """Positive revenue lift described as 'positive'."""
        features = FakeCategoryFeatures(mean_revenue_lift_pct=5.2)
        result = self._injector().build_agent_context(features)
        assert "positive" in result.lower()
        assert "5.2%" in result

    def test_negative_revenue_lift(self):
        """Negative revenue lift described as 'negative'."""
        features = FakeCategoryFeatures(mean_revenue_lift_pct=-3.1)
        result = self._injector().build_agent_context(features)
        assert "negative" in result.lower()
        assert "3.1%" in result

    def test_none_revenue_lift_no_crash(self):
        """None revenue lift doesn't crash."""
        features = FakeCategoryFeatures(mean_revenue_lift_pct=None)
        result = self._injector().build_agent_context(features)
        assert isinstance(result, str)

    def test_acceptance_rates_included(self):
        """Acceptance breakdown included."""
        features = FakeCategoryFeatures(
            acceptance_rate=0.80,
            accepted_rate=0.60,
            modified_rate=0.20,
            rejected_rate=0.20,
        )
        result = self._injector().build_agent_context(features)
        assert "80%" in result
        assert "60%" in result

    def test_conservative_modification_hint(self):
        """Low modification ratio → conservative suggestion."""
        features = FakeCategoryFeatures(
            mean_modification_ratio=0.6,
            modified_rate=0.20,
        )
        result = self._injector().build_agent_context(features)
        assert "conservative" in result.lower()

    def test_aggressive_modification_hint(self):
        """High modification ratio → aggressive suggestion."""
        features = FakeCategoryFeatures(
            mean_modification_ratio=1.4,
            modified_rate=0.20,
        )
        result = self._injector().build_agent_context(features)
        assert "aggressive" in result.lower()

    def test_no_modification_hint_when_low_modified_rate(self):
        """Low modified_rate → no modification hint even with extreme ratio."""
        features = FakeCategoryFeatures(
            mean_modification_ratio=1.0,
            modified_rate=0.0,
        )
        result = self._injector().build_agent_context(features)
        assert "conservative" not in result.lower()

    def test_no_modification_hint_when_none_ratio(self):
        """None modification ratio → no modification hint."""
        features = FakeCategoryFeatures(
            mean_modification_ratio=None,
            modified_rate=0.20,
        )
        result = self._injector().build_agent_context(features)
        assert "conservative" not in result.lower()
        assert "aggressive" not in result.lower()

    def test_magnitude_bucket_mentioned(self):
        """Best magnitude bucket included."""
        features = FakeCategoryFeatures(best_magnitude_bucket="5-8%")
        result = self._injector().build_agent_context(features)
        assert "5-8%" in result

    def test_no_magnitude_when_none(self):
        """None bucket → no magnitude line."""
        features = FakeCategoryFeatures(best_magnitude_bucket=None)
        result = self._injector().build_agent_context(features)
        assert "range" not in result.lower() or "best" not in result.lower()

    def test_highly_elastic_category(self):
        """High elasticity → 'highly price-sensitive'."""
        features = FakeCategoryFeatures(mean_observed_elasticity=-2.5)
        result = self._injector().build_agent_context(features)
        assert "highly price-sensitive" in result

    def test_moderately_elastic_category(self):
        """Moderate elasticity → 'moderately price-sensitive'."""
        features = FakeCategoryFeatures(mean_observed_elasticity=-1.5)
        result = self._injector().build_agent_context(features)
        assert "moderately price-sensitive" in result

    def test_inelastic_category(self):
        """Low elasticity → 'relatively price-insensitive'."""
        features = FakeCategoryFeatures(mean_observed_elasticity=-0.5)
        result = self._injector().build_agent_context(features)
        assert "price-insensitive" in result

    def test_margin_warning(self):
        """Negative margin delta → warning about margins."""
        features = FakeCategoryFeatures(mean_margin_delta=-0.05)
        result = self._injector().build_agent_context(features)
        assert "margin" in result.lower()
        assert "warning" in result.lower()

    def test_no_margin_warning_when_positive(self):
        """Positive margin delta → no warning."""
        features = FakeCategoryFeatures(mean_margin_delta=0.02)
        result = self._injector().build_agent_context(features)
        assert "warning" not in result.lower()

    def test_no_margin_warning_when_small_negative(self):
        """Small negative margin delta → no warning."""
        features = FakeCategoryFeatures(mean_margin_delta=-0.01)
        result = self._injector().build_agent_context(features)
        assert "warning" not in result.lower()

    def test_confidence_insight_best_band(self):
        """Confidence bands with data → best band mentioned."""
        bands = [
            FakeConfidenceBand(0.0, 0.5, "0.0-0.5", 5, -1.0),
            FakeConfidenceBand(0.7, 1.0, "0.7-1.0", 5, 8.0),
        ]
        features = FakeCategoryFeatures(confidence_band_performance=bands)
        result = self._injector().build_agent_context(features)
        assert "0.7-1.0" in result

    def test_confidence_insight_negative_impact(self):
        """Worst band with negative impact mentioned."""
        bands = [
            FakeConfidenceBand(0.0, 0.5, "0.0-0.5", 5, -3.0),
            FakeConfidenceBand(0.7, 1.0, "0.7-1.0", 5, 8.0),
        ]
        features = FakeCategoryFeatures(confidence_band_performance=bands)
        result = self._injector().build_agent_context(features)
        assert "negative" in result.lower()


# ──────────────────────────────────────────────────────────
# TESTS: build_minimal_context
# ──────────────────────────────────────────────────────────

class TestBuildMinimalContext:
    """Test one-line context summary."""

    def _injector(self):
        from services.scoring.learning.context_injector import ContextInjector
        return ContextInjector()

    def test_none_features(self):
        """None features → standard message."""
        result = self._injector().build_minimal_context(None)
        assert "No historical data" in result

    def test_insufficient_outcomes(self):
        """Below threshold → mentions threshold."""
        features = FakeCategoryFeatures(n_outcomes=3)
        result = self._injector().build_minimal_context(features)
        assert "3 outcomes" in result
        assert "threshold" in result

    def test_sufficient_outcomes(self):
        """Enough data → one-line summary with key metrics."""
        features = FakeCategoryFeatures(
            n_outcomes=25,
            acceptance_rate=0.80,
            mean_revenue_lift_pct=4.2,
            positive_outcome_rate=0.70,
        )
        result = self._injector().build_minimal_context(features)
        assert "25 outcomes" in result
        assert "80%" in result
        assert "+4.2%" in result
        assert "70%" in result

    def test_none_revenue_lift(self):
        """None lift → 'unmeasured'."""
        features = FakeCategoryFeatures(mean_revenue_lift_pct=None)
        result = self._injector().build_minimal_context(features)
        assert "unmeasured" in result

    def test_negative_revenue_lift(self):
        """Negative lift shows minus sign."""
        features = FakeCategoryFeatures(mean_revenue_lift_pct=-2.3)
        result = self._injector().build_minimal_context(features)
        assert "-2.3%" in result


# ──────────────────────────────────────────────────────────
# TESTS: build() convenience method
# ──────────────────────────────────────────────────────────

class TestBuildConvenience:
    """Test the combined build() method."""

    def _injector(self):
        from services.scoring.learning.context_injector import ContextInjector
        return ContextInjector()

    def test_returns_tuple(self):
        """build() returns (ScoringContext, str)."""
        features = FakeCategoryFeatures(n_outcomes=20)
        scoring_ctx, agent_text = self._injector().build(features)
        from services.scoring.learning.context_injector import ScoringContext
        assert isinstance(scoring_ctx, ScoringContext)
        assert isinstance(agent_text, str)

    def test_both_populated(self):
        """Both outputs populated with sufficient data."""
        features = FakeCategoryFeatures(n_outcomes=20)
        scoring_ctx, agent_text = self._injector().build(features)
        assert scoring_ctx.n_historical_outcomes == 20
        assert len(agent_text) > 0

    def test_insufficient_data_both_minimal(self):
        """Insufficient data → minimal context + empty string."""
        features = FakeCategoryFeatures(n_outcomes=2)
        scoring_ctx, agent_text = self._injector().build(features)
        assert scoring_ctx.merchant_bias == 0.0
        assert agent_text == ""

    def test_merchant_id_passed_through(self):
        """merchant_id parameter accepted (for future personalization)."""
        features = FakeCategoryFeatures(n_outcomes=20)
        scoring_ctx, agent_text = self._injector().build(
            features, merchant_id="m-123"
        )
        assert isinstance(agent_text, str)


# ──────────────────────────────────────────────────────────
# TESTS: Edge Cases
# ──────────────────────────────────────────────────────────

class TestContextInjectorEdgeCases:
    """Boundary conditions and edge cases."""

    def _injector(self):
        from services.scoring.learning.context_injector import ContextInjector
        return ContextInjector()

    def test_exactly_threshold_outcomes(self):
        """Exactly 5 outcomes (MIN_OUTCOMES_FOR_CONTEXT) → context generated."""
        features = FakeCategoryFeatures(n_outcomes=5)
        ctx = self._injector().build_scoring_context(features)
        assert ctx.n_historical_outcomes == 5
        assert ctx.merchant_acceptance_rate == 0.75

    def test_exactly_calibration_threshold(self):
        """Exactly 10 outcomes (MIN_OUTCOMES_FOR_CALIBRATION) — calibration runs."""
        bands = [
            FakeConfidenceBand(0.0, 0.5, "0.0-0.5", 3, 5.0),
            FakeConfidenceBand(0.7, 1.0, "0.7-1.0", 3, 5.0),
        ]
        features = FakeCategoryFeatures(
            n_outcomes=10, confidence_band_performance=bands
        )
        ctx = self._injector().build_scoring_context(features)
        # Equal performance → factor stays 1.0
        assert ctx.confidence_calibration_factor == 1.0

    def test_category_with_underscores(self):
        """Category 'home_garden' → 'Home Garden' in agent text."""
        features = FakeCategoryFeatures(category="home_garden")
        result = self._injector().build_agent_context(features)
        assert "Home Garden" in result

    def test_zero_acceptance_rate(self):
        """Zero acceptance rate doesn't crash."""
        features = FakeCategoryFeatures(
            acceptance_rate=0.0,
            accepted_rate=0.0,
            modified_rate=0.0,
            rejected_rate=1.0,
        )
        result = self._injector().build_agent_context(features)
        assert "0%" in result

    def test_all_fields_none_features(self):
        """Features with many None fields don't crash."""
        features = FakeCategoryFeatures(
            mean_revenue_lift_pct=None,
            mean_modification_ratio=None,
            best_magnitude_bucket=None,
            mean_observed_elasticity=None,
            mean_margin_delta=None,
            confidence_band_performance=[],
        )
        result = self._injector().build_agent_context(features)
        assert isinstance(result, str)

    def test_calibration_factor_equal_bands(self):
        """Equal high/low band performance → factor = 1.0."""
        bands = [
            FakeConfidenceBand(0.0, 0.5, "0.0-0.5", 5, 5.0),
            FakeConfidenceBand(0.7, 1.0, "0.7-1.0", 5, 5.0),
        ]
        features = FakeCategoryFeatures(
            n_outcomes=20, confidence_band_performance=bands
        )
        ctx = self._injector().build_scoring_context(features)
        assert ctx.confidence_calibration_factor == 1.0

    def test_confidence_insight_all_negative(self):
        """All bands negative → no confidence insight (best_lift <= 0)."""
        bands = [
            FakeConfidenceBand(0.0, 0.5, "0.0-0.5", 5, -2.0),
            FakeConfidenceBand(0.7, 1.0, "0.7-1.0", 5, -1.0),
        ]
        features = FakeCategoryFeatures(confidence_band_performance=bands)
        result = self._injector().build_agent_context(features)
        # Should not mention confidence bands since all negative
        assert "produced the best results" not in result

        