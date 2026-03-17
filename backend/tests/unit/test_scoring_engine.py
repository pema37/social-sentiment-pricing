"""
Tests for ScoringEngine — Phase 2 deterministic scoring pipeline.

Place at: backend/tests/unit/test_scoring_engine.py

Tests cover:
  - Engine initialization (default + custom config)
  - Full scoring pipeline (happy path)
  - Component dispatchers (elasticity, position, urgency)
  - Bridge helpers (price extraction, sentiment, urgency signals)
  - AnalystOutput field builder
  - Edge cases (missing data, Decimal prices, zero competitors)
  - ScoringEngineResult structure

Run: pytest backend/tests/unit/test_scoring_engine.py -v
"""

import sys
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

# ──────────────────────────────────────────────────────────
# sys.modules isolation — prevents SQLAlchemy Table collisions
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
# Fake dataclasses matching real return types
# ──────────────────────────────────────────────────────────


class FakeElasticityResult:
    def __init__(self, **kwargs):
        self.estimate = kwargs.get("estimate", -1.5)
        self.ci_lower = kwargs.get("ci_lower", -2.0)
        self.ci_upper = kwargs.get("ci_upper", -1.0)
        self.confidence = kwargs.get("confidence", 0.7)
        self.method = kwargs.get("method", "bayesian_posterior")
        self.prior_source = kwargs.get("prior_source", "category_prior")
        self.n_observations = kwargs.get("n_observations", 0)


class FakePositionResult:
    def __init__(self, **kwargs):
        self.position_index = kwargs.get("position_index", 0.5)
        self.confidence = kwargs.get("confidence", 0.6)
        self.market_pressure = kwargs.get("market_pressure", "neutral")
        self.competitor_count = kwargs.get("competitor_count", 3)


class FakeUrgencyResult:
    def __init__(self, **kwargs):
        self.score = kwargs.get("score", 0.4)
        self.confidence = kwargs.get("confidence", 0.5)
        self.level_label = kwargs.get("level_label", "medium")
        self.reasons = kwargs.get("reasons", ["moderate sentiment shift"])


class FakeFusionResult:
    def __init__(self, **kwargs):
        self.direction = kwargs.get("direction", "increase")
        self.reasoning = kwargs.get("reasoning", "Positive sentiment + underpriced")
        self.confidence_components = kwargs.get(
            "confidence_components",
            {
                "data_quality": 0.6,
            },
        )


class FakeCompetitorPrice:
    def __init__(self, price=49.99, competitor_name="CompA", scraped_at=None, is_on_sale=False, sale_price=None):
        self.price = price
        self.competitor_name = competitor_name
        self.scraped_at = scraped_at or datetime.now(UTC)
        self.is_on_sale = is_on_sale
        self.sale_price = sale_price


class FakeSentiment:
    def __init__(self, overall_score=0.4, crisis_detected=False, crisis_severity=None):
        self.overall_score = overall_score
        self.crisis_detected = crisis_detected
        self.crisis_severity = crisis_severity


class FakeScoutOutput:
    def __init__(self, **kwargs):
        self.our_price = kwargs.get("our_price", 39.99)
        self.competitors = kwargs.get(
            "competitors",
            [
                FakeCompetitorPrice(49.99, "CompA"),
                FakeCompetitorPrice(44.99, "CompB"),
                FakeCompetitorPrice(35.99, "CompC"),
            ],
        )
        self.sentiment = kwargs.get("sentiment", FakeSentiment())
        self.competitor_count = kwargs.get("competitor_count", 3)
        self.data_completeness = kwargs.get("data_completeness", 0.85)
        self.product_id = kwargs.get("product_id", "prod-001")
        self.scouted_at = kwargs.get("scouted_at", datetime.now(UTC))


class FakeSignals:
    def __init__(self, **kwargs):
        self.sentiment_change_24h = kwargs.get("sentiment_change_24h", 0.1)
        self.viral_detected = kwargs.get("viral_detected", False)
        self.mention_growth_rate = kwargs.get("mention_growth_rate", 0.05)
        self.trend_velocity = kwargs.get("trend_velocity", 0.3)
        self.sentiment_momentum = kwargs.get("sentiment_momentum", 0.2)
        self.is_trending = kwargs.get("is_trending", False)


# ──────────────────────────────────────────────────────────
# TESTS: Engine Initialization
# ──────────────────────────────────────────────────────────


class TestScoringEngineInit:
    """Test engine construction with various configs."""

    def test_default_init(self):
        """Engine initializes with default config."""
        from services.scoring.engine import ScoringEngine

        engine = ScoringEngine()
        assert engine._prior_store is not None
        assert engine._elasticity_calc is not None
        assert engine._position_calc is not None
        assert engine._urgency_scorer is not None
        assert engine._fusion is not None

    def test_custom_guardrail_config(self):
        """Engine accepts custom GuardrailConfig."""
        from services.scoring.engine import ScoringEngine
        from services.scoring.fusion_types import GuardrailConfig

        config = GuardrailConfig()
        engine = ScoringEngine(guardrail_config=config)
        assert engine._fusion is not None

    def test_custom_prior_store(self):
        """Engine accepts injected CategoryPriorStore."""
        from services.scoring.category_priors import CategoryPriorStore
        from services.scoring.engine import ScoringEngine

        store = CategoryPriorStore()
        engine = ScoringEngine(prior_store=store)
        assert engine._prior_store is store

    def test_prior_store_property(self):
        """prior_store property exposes the store for batch jobs."""
        from services.scoring.engine import ScoringEngine

        engine = ScoringEngine()
        assert engine.prior_store is engine._prior_store


# ──────────────────────────────────────────────────────────
# TESTS: Full Scoring Pipeline
# ──────────────────────────────────────────────────────────


class TestScoringEnginePipeline:
    """Test the complete score() method."""

    def _make_engine_with_mocks(self):
        """Create engine with mocked internal components."""
        from services.scoring.engine import ScoringEngine

        engine = ScoringEngine()

        # Mock each component calculator
        engine._elasticity_calc = MagicMock()
        engine._elasticity_calc.compute.return_value = FakeElasticityResult()

        engine._position_calc = MagicMock()
        engine._position_calc.compute.return_value = FakePositionResult()

        engine._urgency_scorer = MagicMock()
        engine._urgency_scorer.compute.return_value = FakeUrgencyResult()

        engine._fusion = MagicMock()
        engine._fusion.compute.return_value = FakeFusionResult()

        return engine

    def test_happy_path_returns_result(self):
        """Full pipeline returns ScoringEngineResult with all components."""
        from services.scoring.engine import ScoringEngineResult

        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        result = engine.score(scout_output=scout, product_category="electronics")

        assert isinstance(result, ScoringEngineResult)
        assert result.elasticity is not None
        assert result.position is not None
        assert result.urgency is not None
        assert result.fusion is not None
        assert result.analyst_fields is not None
        assert result.processing_time_ms >= 0

    def test_calls_all_four_components(self):
        """Pipeline invokes elasticity, position, urgency, and fusion."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        engine.score(scout_output=scout)

        engine._elasticity_calc.compute.assert_called_once()
        engine._position_calc.compute.assert_called_once()
        engine._urgency_scorer.compute.assert_called_once()
        engine._fusion.compute.assert_called_once()

    def test_passes_category_to_elasticity(self):
        """Elasticity calculator receives the product category."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        engine.score(scout_output=scout, product_category="fashion")

        call_kwargs = engine._elasticity_calc.compute.call_args
        assert call_kwargs[1]["category"] == "fashion"

    def test_passes_price_history_to_elasticity(self):
        """Elasticity calculator receives price change events."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()
        history = [MagicMock(), MagicMock()]

        engine.score(scout_output=scout, price_change_history=history)

        call_kwargs = engine._elasticity_calc.compute.call_args
        assert call_kwargs[1]["price_change_events"] == history

    def test_none_price_history_passed_as_none(self):
        """None price history is passed through (not converted to empty list)."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        engine.score(scout_output=scout, price_change_history=None)

        call_kwargs = engine._elasticity_calc.compute.call_args
        assert call_kwargs[1]["price_change_events"] is None

    def test_product_cost_reaches_fusion(self):
        """Product cost is passed to ScoreFusion via ProductContext."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        engine.score(scout_output=scout, product_cost=15.0)

        call_kwargs = engine._fusion.compute.call_args
        product_ctx = call_kwargs[1]["product"]
        assert product_ctx.cost == 15.0

    def test_merchant_bias_reaches_fusion(self):
        """Merchant bias is included in ProductContext."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        engine.score(scout_output=scout, merchant_bias=0.05)

        call_kwargs = engine._fusion.compute.call_args
        product_ctx = call_kwargs[1]["product"]
        assert product_ctx.merchant_bias == 0.05

    def test_recent_price_changes_in_product_context(self):
        """Recent price changes reach fusion via ProductContext."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()
        changes = [MagicMock(), MagicMock()]

        engine.score(scout_output=scout, recent_price_changes=changes)

        call_kwargs = engine._fusion.compute.call_args
        product_ctx = call_kwargs[1]["product"]
        assert len(product_ctx.recent_changes) == 2

    def test_sentiment_score_passed_to_fusion(self):
        """Sentiment score extracted from ScoutOutput reaches fusion."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput(sentiment=FakeSentiment(overall_score=0.7))

        engine.score(scout_output=scout)

        call_kwargs = engine._fusion.compute.call_args
        assert call_kwargs[1]["sentiment_score"] == 0.7

    def test_processing_time_tracked(self):
        """Processing time is a non-negative integer."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        result = engine.score(scout_output=scout)

        assert isinstance(result.processing_time_ms, int)
        assert result.processing_time_ms >= 0


# ──────────────────────────────────────────────────────────
# TESTS: Bridge Helpers
# ──────────────────────────────────────────────────────────


class TestBridgeHelpers:
    """Test static helper methods for data extraction."""

    def test_get_our_price_float(self):
        """Extracts float price from ScoutOutput."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput(our_price=42.50)
        assert ScoringEngine._get_our_price(scout) == 42.50

    def test_get_our_price_decimal(self):
        """Converts Decimal price to float."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput(our_price=Decimal("42.50"))
        result = ScoringEngine._get_our_price(scout)
        assert isinstance(result, float)
        assert result == 42.50

    def test_get_our_price_zero(self):
        """Zero price returns 0.0."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput(our_price=0)
        assert ScoringEngine._get_our_price(scout) == 0.0

    def test_get_our_price_none(self):
        """None price returns 0.0."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput(our_price=None)
        assert ScoringEngine._get_our_price(scout) == 0.0

    def test_get_our_price_missing_attr(self):
        """Object without our_price returns 0.0."""
        from services.scoring.engine import ScoringEngine

        obj = MagicMock(spec=[])  # Empty spec — no attributes
        assert ScoringEngine._get_our_price(obj) == 0.0

    def test_get_sentiment_score_normal(self):
        """Extracts sentiment score from nested sentiment object."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput(sentiment=FakeSentiment(overall_score=0.65))
        assert ScoringEngine._get_sentiment_score(scout) == 0.65

    def test_get_sentiment_score_none_sentiment(self):
        """No sentiment returns None."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput(sentiment=None)
        assert ScoringEngine._get_sentiment_score(scout) is None

    def test_get_sentiment_score_none_overall(self):
        """Sentiment with no overall_score returns None."""
        from services.scoring.engine import ScoringEngine

        sentiment = MagicMock(spec=[])  # No overall_score
        scout = FakeScoutOutput(sentiment=sentiment)
        assert ScoringEngine._get_sentiment_score(scout) is None

    def test_get_sentiment_score_decimal(self):
        """Decimal sentiment score converted to float."""
        from services.scoring.engine import ScoringEngine

        sentiment = FakeSentiment(overall_score=Decimal("0.55"))
        scout = FakeScoutOutput(sentiment=sentiment)
        result = ScoringEngine._get_sentiment_score(scout)
        assert isinstance(result, float)
        assert result == 0.55


# ──────────────────────────────────────────────────────────
# TESTS: Urgency Signal Building
# ──────────────────────────────────────────────────────────


class TestUrgencySignalBuilding:
    """Test _build_urgency_signals bridge method."""

    def test_full_signals(self):
        """All signals available — all fields populated."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput()
        signals = FakeSignals()
        position = FakePositionResult()

        result = ScoringEngine._build_urgency_signals(scout, signals, position)

        assert result.sentiment_score == 0.4
        assert result.sentiment_change_24h == 0.1
        assert result.mention_growth_rate == 0.05
        assert result.trend_velocity == 0.3
        assert result.sentiment_momentum == 0.2
        assert result.competitive_position_index == 0.5
        assert result.competitor_count == 3

    def test_no_signals(self):
        """No MarketSignals — trend fields are None."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput()
        position = FakePositionResult()

        result = ScoringEngine._build_urgency_signals(scout, None, position)

        assert result.sentiment_score == 0.4  # From scout sentiment
        assert result.sentiment_change_24h is None
        assert result.mention_growth_rate is None
        assert result.trend_velocity is None
        assert result.is_trending is False

    def test_no_sentiment(self):
        """No sentiment on ScoutOutput — sentiment fields are None."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput(sentiment=None)
        signals = FakeSignals()
        position = FakePositionResult()

        result = ScoringEngine._build_urgency_signals(scout, signals, position)

        assert result.sentiment_score is None
        assert result.crisis_detected is False

    def test_crisis_from_scout(self):
        """Crisis detected via scout sentiment."""
        from services.scoring.engine import ScoringEngine

        sentiment = FakeSentiment(overall_score=-0.8, crisis_detected=True, crisis_severity=0.9)
        scout = FakeScoutOutput(sentiment=sentiment)
        position = FakePositionResult()

        result = ScoringEngine._build_urgency_signals(scout, None, position)

        assert result.crisis_detected is True
        assert result.crisis_severity == 0.9

    def test_crisis_from_viral_negative(self):
        """Crisis inferred from viral + negative sentiment (scout didn't catch it)."""
        from services.scoring.engine import ScoringEngine

        sentiment = FakeSentiment(overall_score=-0.7, crisis_detected=False)
        scout = FakeScoutOutput(sentiment=sentiment)
        signals = FakeSignals(viral_detected=True)
        position = FakePositionResult()

        result = ScoringEngine._build_urgency_signals(scout, signals, position)

        assert result.crisis_detected is True

    def test_no_crisis_from_viral_positive(self):
        """Viral + positive sentiment does NOT trigger crisis."""
        from services.scoring.engine import ScoringEngine

        sentiment = FakeSentiment(overall_score=0.5, crisis_detected=False)
        scout = FakeScoutOutput(sentiment=sentiment)
        signals = FakeSignals(viral_detected=True)
        position = FakePositionResult()

        result = ScoringEngine._build_urgency_signals(scout, signals, position)

        assert result.crisis_detected is False

    def test_inventory_fields_are_none(self):
        """Inventory/search signals not yet connected — always None."""
        from services.scoring.engine import ScoringEngine

        scout = FakeScoutOutput()
        position = FakePositionResult()

        result = ScoringEngine._build_urgency_signals(scout, None, position)

        assert result.days_of_inventory is None
        assert result.stockout_risk is False
        assert result.search_volume_trend is None
        assert result.search_volume_index is None


# ──────────────────────────────────────────────────────────
# TESTS: Competitive Position Bridge
# ──────────────────────────────────────────────────────────


class TestPositionBridge:
    """Test _compute_position bridges ScoutOutput competitors correctly."""

    def test_competitors_converted_to_price_points(self):
        """ScoutOutput competitors are bridged to CompetitorPricePoint."""
        from services.scoring.engine import ScoringEngine

        engine = ScoringEngine()
        engine._position_calc = MagicMock()
        engine._position_calc.compute.return_value = FakePositionResult()

        scout = FakeScoutOutput(
            our_price=39.99,
            competitors=[
                FakeCompetitorPrice(49.99, "A"),
                FakeCompetitorPrice(44.99, "B"),
            ],
        )

        engine._compute_position(scout)

        call_args = engine._position_calc.compute.call_args
        assert call_args[1]["our_price"] == 39.99
        comps = call_args[1]["competitors"]
        assert len(comps) == 2
        assert comps[0].price == 49.99
        assert comps[0].competitor_name == "A"

    def test_empty_competitors(self):
        """No competitors — empty list passed to calculator."""
        from services.scoring.engine import ScoringEngine

        engine = ScoringEngine()
        engine._position_calc = MagicMock()
        engine._position_calc.compute.return_value = FakePositionResult(competitor_count=0)

        scout = FakeScoutOutput(our_price=39.99, competitors=[])

        engine._compute_position(scout)

        call_args = engine._position_calc.compute.call_args
        assert call_args[1]["competitors"] == []

    def test_none_competitors(self):
        """None competitors treated as empty list."""
        from services.scoring.engine import ScoringEngine

        engine = ScoringEngine()
        engine._position_calc = MagicMock()
        engine._position_calc.compute.return_value = FakePositionResult(competitor_count=0)

        scout = FakeScoutOutput(our_price=39.99, competitors=None)

        engine._compute_position(scout)

        call_args = engine._position_calc.compute.call_args
        assert call_args[1]["competitors"] == []

    def test_sale_price_bridged(self):
        """Competitor sale_price converted to float."""
        from services.scoring.engine import ScoringEngine

        engine = ScoringEngine()
        engine._position_calc = MagicMock()
        engine._position_calc.compute.return_value = FakePositionResult()

        comp = FakeCompetitorPrice(49.99, "A", is_on_sale=True, sale_price=Decimal("39.99"))
        scout = FakeScoutOutput(competitors=[comp])

        engine._compute_position(scout)

        call_args = engine._position_calc.compute.call_args
        bridged = call_args[1]["competitors"][0]
        assert bridged.sale_price == 39.99
        assert bridged.is_on_sale is True

    def test_none_sale_price(self):
        """None sale_price stays None."""
        from services.scoring.engine import ScoringEngine

        engine = ScoringEngine()
        engine._position_calc = MagicMock()
        engine._position_calc.compute.return_value = FakePositionResult()

        comp = FakeCompetitorPrice(49.99, "A", sale_price=None)
        scout = FakeScoutOutput(competitors=[comp])

        engine._compute_position(scout)

        call_args = engine._position_calc.compute.call_args
        bridged = call_args[1]["competitors"][0]
        assert bridged.sale_price is None


# ──────────────────────────────────────────────────────────
# TESTS: Analyst Field Builder
# ──────────────────────────────────────────────────────────


class TestAnalystFieldBuilder:
    """Test _build_analyst_fields output structure."""

    def _build(self, **overrides):
        from services.scoring.engine import ScoringEngine

        scout = overrides.pop("scout", FakeScoutOutput())
        elasticity = overrides.pop("elasticity", FakeElasticityResult())
        position = overrides.pop("position", FakePositionResult())
        urgency = overrides.pop("urgency", FakeUrgencyResult())
        fusion = overrides.pop("fusion", FakeFusionResult())
        return ScoringEngine._build_analyst_fields(
            scout,
            elasticity,
            position,
            urgency,
            fusion,
        )

    def test_returns_dict(self):
        """Returns a dict usable as AnalystOutput kwargs."""
        fields = self._build()
        assert isinstance(fields, dict)

    def test_has_analyzed_at(self):
        """analyzed_at is a datetime."""
        fields = self._build()
        assert isinstance(fields["analyzed_at"], datetime)

    def test_elasticity_nested(self):
        """Elasticity data is nested dict with expected keys."""
        fields = self._build()
        e = fields["elasticity"]
        assert e["point_estimate"] == -1.5
        assert e["confidence_interval_low"] == -2.0
        assert e["confidence_interval_high"] == -1.0
        assert e["method"] == "bayesian_posterior"

    def test_confidence_nested(self):
        """Confidence decomposition has 4 components."""
        fields = self._build()
        c = fields["confidence"]
        assert "elasticity" in c
        assert "position" in c
        assert "urgency" in c
        assert "data_quality" in c

    def test_urgency_mapping(self):
        """Urgency level mapped correctly."""
        fields = self._build(urgency=FakeUrgencyResult(level_label="critical"))
        assert fields["urgency_level"] == "critical"

    def test_urgency_unknown_maps_to_medium(self):
        """Unknown urgency label defaults to medium."""
        fields = self._build(urgency=FakeUrgencyResult(level_label="unknown_level"))
        assert fields["urgency_level"] == "medium"

    def test_direction_increase(self):
        """Fusion direction 'increase' maps correctly."""
        fields = self._build(fusion=FakeFusionResult(direction="increase"))
        assert fields["recommended_direction"] == "increase"

    def test_direction_decrease(self):
        """Fusion direction 'decrease' maps correctly."""
        fields = self._build(fusion=FakeFusionResult(direction="decrease"))
        assert fields["recommended_direction"] == "decrease"

    def test_direction_hold(self):
        """Fusion direction 'hold' maps correctly."""
        fields = self._build(fusion=FakeFusionResult(direction="hold"))
        assert fields["recommended_direction"] == "hold"

    def test_direction_unknown_maps_to_hold(self):
        """Unknown direction defaults to hold."""
        fields = self._build(fusion=FakeFusionResult(direction="wat"))
        assert fields["recommended_direction"] == "hold"

    def test_sentiment_positive(self):
        """Positive sentiment maps to supports_increase."""
        scout = FakeScoutOutput(sentiment=FakeSentiment(overall_score=0.5))
        fields = self._build(scout=scout)
        assert fields["sentiment_impact"] == "supports_increase"

    def test_sentiment_negative(self):
        """Negative sentiment maps to suggests_decrease."""
        scout = FakeScoutOutput(sentiment=FakeSentiment(overall_score=-0.5))
        fields = self._build(scout=scout)
        assert fields["sentiment_impact"] == "suggests_decrease"

    def test_sentiment_neutral(self):
        """Neutral sentiment maps to neutral."""
        scout = FakeScoutOutput(sentiment=FakeSentiment(overall_score=0.1))
        fields = self._build(scout=scout)
        assert fields["sentiment_impact"] == "neutral"

    def test_sentiment_crisis_override(self):
        """Crisis overrides normal sentiment interpretation."""
        sentiment = FakeSentiment(overall_score=0.5, crisis_detected=True)
        scout = FakeScoutOutput(sentiment=sentiment)
        fields = self._build(scout=scout)
        assert fields["sentiment_impact"] == "crisis_override"

    def test_no_sentiment(self):
        """No sentiment → None for score and impact."""
        scout = FakeScoutOutput(sentiment=None)
        fields = self._build(scout=scout)
        assert fields["sentiment_score"] is None
        assert fields["sentiment_impact"] is None

    def test_data_completeness(self):
        """Data completeness extracted from scout."""
        scout = FakeScoutOutput(data_completeness=0.92)
        fields = self._build(scout=scout)
        assert fields["data_completeness"] == 0.92

    def test_analyst_version(self):
        """Version string is set."""
        fields = self._build()
        assert fields["analyst_version"] == "2.0-scoring-engine"

    def test_model_used(self):
        """Model string is set."""
        fields = self._build()
        assert fields["model_used"] == "deterministic_scoring_v1.0"

    def test_processing_time_is_none(self):
        """Processing time is None (set by caller)."""
        fields = self._build()
        assert fields["processing_time_ms"] is None

    def test_position_fields(self):
        """Competitive position fields populated."""
        fields = self._build(
            position=FakePositionResult(position_index=0.7, market_pressure="downward", competitor_count=5)
        )
        assert fields["competitive_position_index"] == 0.7
        assert fields["market_pressure"] == "downward"
        assert fields["competitor_count"] == 5

    def test_urgency_score_and_reasons(self):
        """Urgency score and reasons populated."""
        fields = self._build(urgency=FakeUrgencyResult(score=0.8, reasons=["crisis detected", "price undercut"]))
        assert fields["urgency_score"] == 0.8
        assert len(fields["urgency_reasons"]) == 2


# ──────────────────────────────────────────────────────────
# TESTS: ScoringEngineResult
# ──────────────────────────────────────────────────────────


class TestScoringEngineResult:
    """Test the result container."""

    def test_slots(self):
        """Result uses __slots__ for memory efficiency."""
        from services.scoring.engine import ScoringEngineResult

        result = ScoringEngineResult(
            elasticity=FakeElasticityResult(),
            position=FakePositionResult(),
            urgency=FakeUrgencyResult(),
            fusion=FakeFusionResult(),
            analyst_fields={"test": True},
            processing_time_ms=42,
        )
        assert result.processing_time_ms == 42
        assert result.analyst_fields["test"] is True

    def test_no_extra_attributes(self):
        """__slots__ prevents adding extra attributes."""
        from services.scoring.engine import ScoringEngineResult

        result = ScoringEngineResult(
            elasticity=FakeElasticityResult(),
            position=FakePositionResult(),
            urgency=FakeUrgencyResult(),
            fusion=FakeFusionResult(),
            analyst_fields={},
            processing_time_ms=0,
        )
        with pytest.raises(AttributeError):
            result.extra_field = "nope"


# ──────────────────────────────────────────────────────────
# TESTS: Edge Cases
# ──────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def _make_engine_with_mocks(self):
        from services.scoring.engine import ScoringEngine

        engine = ScoringEngine()
        engine._elasticity_calc = MagicMock()
        engine._elasticity_calc.compute.return_value = FakeElasticityResult()
        engine._position_calc = MagicMock()
        engine._position_calc.compute.return_value = FakePositionResult()
        engine._urgency_scorer = MagicMock()
        engine._urgency_scorer.compute.return_value = FakeUrgencyResult()
        engine._fusion = MagicMock()
        engine._fusion.compute.return_value = FakeFusionResult()
        return engine

    def test_zero_price_scout(self):
        """ScoutOutput with zero price doesn't crash."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput(our_price=0)
        result = engine.score(scout_output=scout)
        assert result is not None

    def test_decimal_price_scout(self):
        """ScoutOutput with Decimal price works correctly."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput(our_price=Decimal("99.99"))
        result = engine.score(scout_output=scout)
        assert result is not None

    def test_empty_category(self):
        """Empty category string doesn't crash."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()
        result = engine.score(scout_output=scout, product_category="")
        assert result is not None

    def test_default_category_is_unknown(self):
        """Default category is 'unknown'."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        engine.score(scout_output=scout)

        call_kwargs = engine._elasticity_calc.compute.call_args
        assert call_kwargs[1]["category"] == "unknown"

    def test_no_signals_no_crash(self):
        """Missing signals parameter uses None throughout."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()
        result = engine.score(scout_output=scout, signals=None)
        assert result is not None

    def test_negative_merchant_bias(self):
        """Negative merchant bias passed through."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        engine.score(scout_output=scout, merchant_bias=-0.05)

        call_kwargs = engine._fusion.compute.call_args
        assert call_kwargs[1]["product"].merchant_bias == -0.05

    def test_none_product_cost(self):
        """None product cost passed to ProductContext."""
        engine = self._make_engine_with_mocks()
        scout = FakeScoutOutput()

        engine.score(scout_output=scout, product_cost=None)

        call_kwargs = engine._fusion.compute.call_args
        assert call_kwargs[1]["product"].cost is None
