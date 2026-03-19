"""
Tests for PipelineAdapter (services/pricing/pipeline_adapter.py).

Covers:
1. build_scout_output() — competitor data, sentiment snapshot, data gaps
2. build_analyst_output() — confidence decomposition mapping, urgency, direction
3. build_strategist_output() — guardrails, direction from change, evidence serialization
4. End-to-end chain — all three outputs in sequence, empty signals, round-trip

NOTE: isinstance() checks use type(x).__name__ because sys.modules isolation
can cause the test and source to import different class objects with the same name.

Place at: backend/tests/unit/test_pipeline_adapter.py
Run: pytest backend/tests/unit/test_pipeline_adapter.py -v
"""

import sys
import types
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

# ══════════════════════════════════════════════════════════════════
# sys.modules ISOLATION
# ══════════════════════════════════════════════════════════════════

_SENTINEL = object()
_saved_attrs = {}

for _key in ["db.session", "core.db.session"]:
    if _key in sys.modules:
        _saved_attrs[_key] = sys.modules[_key]

_mock_db = types.ModuleType("db.session")
_mock_db.get_session = MagicMock()
sys.modules.setdefault("db.session", _mock_db)

_mock_core_db = types.ModuleType("core.db.session")
_mock_core_db.get_session = MagicMock()
sys.modules.setdefault("core.db.session", _mock_core_db)

from services.pricing.pipeline_adapter import PipelineAdapter  # noqa: E402

# ══════════════════════════════════════════════════════════════════
# HELPER: cross-module-safe isinstance
# ══════════════════════════════════════════════════════════════════


def _is_type(obj, type_name: str) -> bool:
    """Check type by name to avoid cross-module identity mismatch."""
    return type(obj).__name__ == type_name


# ══════════════════════════════════════════════════════════════════
# FIXTURES
#
# Source reads FLAT attributes on signals:
#   signals.competitor_prices      → dict {comp_id: Decimal price}
#   signals.sentiment_score        → float or None
#   signals.mention_count_24h      → int or None
#   signals.viral_detected         → bool
#   signals.sentiment_change_24h   → float or None
#   signals.is_trending            → bool
#   signals.trend_direction        → str or None
# ══════════════════════════════════════════════════════════════════


@pytest.fixture
def product_id():
    return uuid4()


@pytest.fixture
def mock_product(product_id):
    p = MagicMock()
    p.id = product_id
    p.current_price = Decimal("32.00")
    p.name = "Test Widget"
    p.category = "Electronics"
    return p


@pytest.fixture
def mock_signals_full():
    """Signals with all data populated — FLAT attributes matching pipeline_adapter.py."""
    signals = MagicMock()

    # competitor_prices is a DICT {comp_id: price}, NOT a list
    signals.competitor_prices = {
        "Store A": Decimal("27.50"),
        "Store B": Decimal("29.99"),
        "Store C": Decimal("35.00"),
    }

    # Flat sentiment attributes
    signals.sentiment_score = 0.35
    signals.mention_count_24h = 127
    signals.viral_detected = False
    signals.sentiment_change_24h = -0.1
    signals.is_trending = False
    signals.trend_direction = "down"

    return signals


@pytest.fixture
def mock_signals_empty():
    """Signals with no data — FLAT attributes."""
    signals = MagicMock()
    signals.competitor_prices = {}  # Empty dict, not list
    signals.sentiment_score = None
    signals.mention_count_24h = 0
    signals.viral_detected = False
    signals.sentiment_change_24h = None
    signals.is_trending = False
    signals.trend_direction = None
    return signals


@pytest.fixture
def mock_rule():
    rule = MagicMock()
    rule.id = uuid4()
    rule.name = "Test competitor rule"
    rule.rule_type = MagicMock()
    rule.rule_type.value = "competitor_relative"
    rule.action = MagicMock()
    rule.action.value = "decrease_percent"
    rule.action_value = Decimal("5.0")
    # Source reads rule.min_price / rule.max_price
    rule.min_price = Decimal("25.00")
    rule.max_price = Decimal("45.00")
    return rule


@pytest.fixture
def confidence_breakdown_full():
    return {
        "overall": 0.72,
        "components": {
            "signal_agreement": {"score": 0.75, "weight": 0.3, "factors": {"competitor_aligned": True}},
            "market_stability": {"score": 0.7, "weight": 0.2, "factors": {"volatility": "low"}},
            "rule_confidence": {"score": 0.65, "weight": 0.15, "rule_type": "competitor_relative"},
            "data_quality": {
                "score": 0.8,
                "weight": 0.2,
                "factors": {"competitor_count": 3, "has_sentiment": True, "mention_count_24h": 127},
            },
            "historical_accuracy": {"score": 0.6, "weight": 0.15},
        },
    }


@pytest.fixture
def confidence_breakdown_empty():
    return {"overall": 0.5, "components": {}}


# ══════════════════════════════════════════════════════════════════
# SCOUT OUTPUT TESTS
# ══════════════════════════════════════════════════════════════════


class TestBuildScoutOutput:
    def test_full_data(self, mock_product, mock_signals_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)

        assert _is_type(scout, "ScoutOutput")
        assert scout.product_id == mock_product.id
        assert scout.our_price == Decimal("32.00")
        assert scout.competitor_count == 3

    def test_competitive_position_index(self, mock_product, mock_signals_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)

        # $32 among $27.50, $29.99, $35.00 → above median
        assert scout.competitive_position_index is not None
        assert 0.0 <= scout.competitive_position_index <= 1.0
        assert scout.competitive_position_index > 0.5

    def test_our_position_label(self, mock_product, mock_signals_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)

        assert scout.our_position in ["cheapest", "below_median", "at_median", "above_median", "most_expensive"]

    def test_sentiment_snapshot(self, mock_product, mock_signals_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)

        # Source stores as scout.sentiment (not sentiment_snapshot)
        assert scout.sentiment is not None
        assert scout.sentiment.overall_score == 0.35
        assert scout.sentiment.mention_count == 127
        assert scout.sentiment.crisis_detected is False

    def test_data_sources_populated(self, mock_product, mock_signals_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)

        source_values = [s.value if hasattr(s, "value") else str(s) for s in scout.data_sources]
        assert any("competitor" in s.lower() for s in source_values)

    def test_data_gaps_identified_when_empty(self, mock_product, mock_signals_empty):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_empty)

        assert len(scout.data_gaps) > 0
        assert "no_competitor_prices" in scout.data_gaps

    def test_empty_signals(self, mock_product, mock_signals_empty):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_empty)

        assert scout.competitor_count == 0
        assert scout.sentiment is None
        assert scout.data_completeness == 0.0

    def test_price_trend_mapping(self, mock_product, mock_signals_full):
        mock_signals_full.trend_direction = "up"
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)

        assert scout.price_trend == "rising"

    def test_crisis_detection(self, mock_product, mock_signals_full):
        mock_signals_full.viral_detected = True
        mock_signals_full.sentiment_score = -0.6
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)

        assert scout.sentiment.crisis_detected is True

    def test_evidence_serialization(self, mock_product, mock_signals_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)

        # Schema may expose to_evidence() or to_evidence_dict()
        to_ev = getattr(scout, "to_evidence", None) or getattr(scout, "to_evidence_dict", None)
        assert to_ev is not None
        evidence = to_ev()
        assert isinstance(evidence, dict)

    def test_scout_version(self, mock_product, mock_signals_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        assert scout.scout_version == "1.0-adapter"

    def test_single_competitor(self, mock_product, mock_signals_full):
        mock_signals_full.competitor_prices = {"Solo": Decimal("30.00")}
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)

        assert scout.competitor_count == 1
        assert scout.competitive_position_index is not None

    def test_data_completeness_with_full(self, mock_product, mock_signals_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        assert scout.data_completeness > 0.0
        assert scout.data_completeness <= 1.0

    def test_no_social_data_gap(self, mock_product, mock_signals_full):
        mock_signals_full.sentiment_score = None
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        assert "no_social_data" in scout.data_gaps


# ══════════════════════════════════════════════════════════════════
# ANALYST OUTPUT TESTS
# ══════════════════════════════════════════════════════════════════


class TestBuildAnalystOutput:
    def test_full_data(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        assert _is_type(analyst, "AnalystOutput")
        assert analyst.product_id == mock_product.id

    def test_confidence_decomposition_mapped(
        self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule
    ):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        cd = analyst.confidence
        assert _is_type(cd, "ConfidenceDecomposition")
        assert cd.elasticity == 0.75  # signal_agreement.score
        assert cd.position == 0.7  # market_stability.score
        assert cd.urgency == 0.65  # rule_confidence.score
        assert cd.data_quality == 0.8  # data_quality.score

    def test_urgency_from_viral(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        mock_signals_full.viral_detected = True
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        assert analyst.urgency_score >= 0.8
        assert "viral_content_detected" in analyst.urgency_reasons

    def test_urgency_from_sentiment_spike(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        mock_signals_full.sentiment_change_24h = -0.4
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        assert analyst.urgency_score >= 0.7

    def test_urgency_from_trending(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        mock_signals_full.is_trending = True
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        assert "trending_detected" in analyst.urgency_reasons

    def test_direction_from_decrease_action(
        self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule
    ):
        mock_rule.action.value = "decrease_percent"
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        direction_val = (
            analyst.recommended_direction.value
            if hasattr(analyst.recommended_direction, "value")
            else analyst.recommended_direction
        )
        assert direction_val.lower() == "decrease"

    def test_direction_from_increase_action(
        self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule
    ):
        mock_rule.action.value = "increase_percent"
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        direction_val = (
            analyst.recommended_direction.value
            if hasattr(analyst.recommended_direction, "value")
            else analyst.recommended_direction
        )
        assert direction_val.lower() == "increase"

    def test_sentiment_interpretation(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        mock_signals_full.sentiment_score = 0.5
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        assert analyst.sentiment_score == 0.5
        assert analyst.sentiment_impact == "supports_increase"

    def test_no_rule_defaults_to_hold(self, mock_product, mock_signals_full, confidence_breakdown_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, rule=None)

        direction_val = (
            analyst.recommended_direction.value
            if hasattr(analyst.recommended_direction, "value")
            else analyst.recommended_direction
        )
        assert direction_val.lower() == "hold"

    def test_empty_confidence_defaults(self, mock_product, mock_signals_full, confidence_breakdown_empty, mock_rule):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_empty, mock_signals_full, mock_rule)

        assert analyst.confidence.elasticity == 0.5
        assert analyst.confidence.position == 0.5
        assert analyst.confidence.urgency == 0.5
        assert analyst.confidence.data_quality == 0.5

    def test_analyst_version(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        assert analyst.analyst_version == "1.0-adapter"
        assert analyst.model_used == "rule_engine"

    def test_data_completeness(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

        assert analyst.data_completeness > 0.0
        assert analyst.competitor_count == 3

    def test_market_pressure(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)
        assert analyst.market_pressure in ["underpriced", "fairly_priced", "overpriced", "no_data"]


# ══════════════════════════════════════════════════════════════════
# STRATEGIST OUTPUT TESTS
# ══════════════════════════════════════════════════════════════════


class TestBuildStrategistOutput:
    def _build_analyst(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        return PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)

    def test_full_data(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Reducing price to match competition.",
            factors={"test": True},
            rule=mock_rule,
        )

        assert _is_type(strategist, "StrategistOutput")
        assert strategist.recommended_price == Decimal("29.49")
        assert strategist.reasoning == "Reducing price to match competition."

    def test_direction_from_negative_change(
        self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule
    ):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=mock_rule,
        )

        direction_val = (
            strategist.change_direction.value
            if hasattr(strategist.change_direction, "value")
            else strategist.change_direction
        )
        assert direction_val.lower() == "decrease"

    def test_direction_from_positive_change(
        self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule
    ):
        mock_rule.action.value = "increase_percent"
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("35.00"),
            change_percent=Decimal("9.38"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=mock_rule,
        )

        direction_val = (
            strategist.change_direction.value
            if hasattr(strategist.change_direction, "value")
            else strategist.change_direction
        )
        assert direction_val.lower() == "increase"

    def test_direction_hold_near_zero(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("32.00"),
            change_percent=Decimal("0.01"),
            confidence_score=Decimal("0.72"),
            reasoning="No change needed.",
            factors={},
            rule=mock_rule,
        )

        direction_val = (
            strategist.change_direction.value
            if hasattr(strategist.change_direction, "value")
            else strategist.change_direction
        )
        assert direction_val.lower() == "hold"

    def test_guardrail_clamping_detected(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("25.00"),
            change_percent=Decimal("-21.88"),
            confidence_score=Decimal("0.72"),
            reasoning="Clamped to floor.",
            factors={},
            rule=mock_rule,
            raw_price_before_boundaries=Decimal("20.00"),
        )

        assert strategist.was_clamped is True
        assert strategist.raw_recommended_price == Decimal("20.00")

    def test_guardrails_include_min_max(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=mock_rule,
        )

        guardrail_names = [g.name for g in strategist.guardrails_applied]
        assert "min_price_floor" in guardrail_names
        assert "max_price_ceiling" in guardrail_names

    def test_no_rule_no_guardrails(self, mock_product, mock_signals_full, confidence_breakdown_full):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, rule=None)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=None,
        )

        assert len(strategist.guardrails_applied) == 0

    def test_pipeline_source(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=mock_rule,
        )

        assert strategist.pipeline_source == "rule_based"
        assert strategist.strategist_version == "1.0-adapter"

    def test_evidence_serialization(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=mock_rule,
        )

        to_ev = getattr(strategist, "to_evidence", None) or getattr(strategist, "to_evidence_dict", None)
        assert to_ev is not None
        evidence = to_ev()
        assert isinstance(evidence, dict)

    def test_confidence_score_passthrough(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=mock_rule,
        )

        assert strategist.confidence_score == 0.72

    def test_current_price_captured(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=mock_rule,
        )

        assert strategist.current_price == Decimal("32.00")

    def test_confidence_decomposition_from_analyst(
        self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule
    ):
        analyst = self._build_analyst(mock_product, mock_signals_full, confidence_breakdown_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=mock_rule,
        )

        cd = strategist.confidence_decomposition
        assert cd.elasticity == 0.75
        assert cd.data_quality == 0.8


# ══════════════════════════════════════════════════════════════════
# END-TO-END ADAPTER CHAIN
# ══════════════════════════════════════════════════════════════════


class TestEndToEndAdapterChain:
    def test_full_chain_produces_serializable_evidence(
        self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule
    ):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test chain",
            factors={},
            rule=mock_rule,
        )

        for obj in [scout, analyst, strategist]:
            to_ev = getattr(obj, "to_evidence", None) or getattr(obj, "to_evidence_dict", None)
            assert to_ev is not None, f"{type(obj).__name__} missing evidence method"
            assert isinstance(to_ev(), dict)

    def test_empty_signals_chain(self, mock_product, mock_signals_empty, confidence_breakdown_empty):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_empty)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_empty, mock_signals_empty, rule=None)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("32.00"),
            change_percent=Decimal("0.00"),
            confidence_score=Decimal("0.50"),
            reasoning="No signals.",
            factors={},
            rule=None,
        )

        assert scout.data_completeness == 0.0
        direction_val = (
            strategist.change_direction.value
            if hasattr(strategist.change_direction, "value")
            else strategist.change_direction
        )
        assert direction_val.lower() == "hold"

    def test_factors_dict_round_trip(self, mock_product, mock_signals_full, confidence_breakdown_full, mock_rule):
        scout = PipelineAdapter.build_scout_output(mock_product, mock_signals_full)
        analyst = PipelineAdapter.build_analyst_output(scout, confidence_breakdown_full, mock_signals_full, mock_rule)
        strategist = PipelineAdapter.build_strategist_output(
            analyst=analyst,
            product=mock_product,
            recommended_price=Decimal("29.49"),
            change_percent=Decimal("-7.84"),
            confidence_score=Decimal("0.72"),
            reasoning="Test",
            factors={},
            rule=mock_rule,
        )

        scout_ev_fn = getattr(scout, "to_evidence", None) or getattr(scout, "to_evidence_dict", None)
        analyst_ev_fn = getattr(analyst, "to_evidence", None) or getattr(analyst, "to_evidence_dict", None)
        strategist_ev_fn = getattr(strategist, "to_evidence", None) or getattr(strategist, "to_evidence_dict", None)

        factors = {
            "scout_evidence": scout_ev_fn(),
            "analyst_evidence": analyst_ev_fn(),
            "strategist_evidence": strategist_ev_fn(),
        }

        assert isinstance(factors["scout_evidence"], dict)
        assert isinstance(factors["analyst_evidence"], dict)
        assert isinstance(factors["strategist_evidence"], dict)
        assert factors["strategist_evidence"]["pipeline_source"] == "rule_based"


# ══════════════════════════════════════════════════════════════════
# RESTORE sys.modules
# ══════════════════════════════════════════════════════════════════

for _key, _orig in _saved_attrs.items():
    sys.modules[_key] = _orig
