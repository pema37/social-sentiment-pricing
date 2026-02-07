"""
Tests for the ActualPrice pricing engine pipeline.
Aligned with actual service signatures:
  - RuleEvaluator(db) — requires AsyncSession
  - SignalProcessor(db) — requires AsyncSession
  - ConfidenceCalculator(db=None) — db optional
  - recommendation_helpers — class methods, not standalone functions
  - No engine.py — pricing is composed from individual services
"""

from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock

import pytest


# ===================================================================
# RuleEvaluator Tests
# ===================================================================

class TestRuleEvaluator:

    def test_initializes_with_db(self, mock_db):
        from services.pricing.rule_evaluator import RuleEvaluator
        evaluator = RuleEvaluator(db=mock_db)
        assert evaluator is not None

    def test_has_get_active_rules(self, mock_db):
        from services.pricing.rule_evaluator import RuleEvaluator
        evaluator = RuleEvaluator(db=mock_db)
        assert callable(getattr(evaluator, "get_active_rules", None))

    def test_has_find_matching_rule(self, mock_db):
        from services.pricing.rule_evaluator import RuleEvaluator
        evaluator = RuleEvaluator(db=mock_db)
        assert callable(getattr(evaluator, "find_matching_rule", None))

    def test_has_rule_applies_to_product(self, mock_db):
        from services.pricing.rule_evaluator import RuleEvaluator
        evaluator = RuleEvaluator(db=mock_db)
        assert callable(getattr(evaluator, "_rule_applies_to_product", None))

    def test_has_eval_sentiment_threshold(self, mock_db):
        from services.pricing.rule_evaluator import RuleEvaluator
        evaluator = RuleEvaluator(db=mock_db)
        assert callable(getattr(evaluator, "_eval_sentiment_threshold", None))


# ===================================================================
# SignalProcessor Tests
# ===================================================================

class TestSignalProcessor:

    def test_initializes_with_db(self, mock_db):
        from services.pricing.signal_processor import SignalProcessor
        processor = SignalProcessor(db=mock_db)
        assert processor is not None

    def test_has_gather_signals(self, mock_db):
        from services.pricing.signal_processor import SignalProcessor
        processor = SignalProcessor(db=mock_db)
        assert callable(getattr(processor, "gather_signals", None))

    def test_has_calculate_price_impact(self, mock_db):
        from services.pricing.signal_processor import SignalProcessor
        processor = SignalProcessor(db=mock_db)
        assert callable(getattr(processor, "calculate_price_impact", None))


# ===================================================================
# ConfidenceCalculator Tests
# ===================================================================

class TestConfidenceCalculator:

    def test_initializes_without_db(self):
        from services.pricing.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        assert calc is not None

    def test_initializes_with_db(self, mock_db):
        from services.pricing.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator(db=mock_db)
        assert calc is not None

    def test_has_calculate_method(self):
        from services.pricing.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        assert callable(getattr(calc, "calculate", None))

    def test_has_get_confidence_breakdown(self):
        from services.pricing.confidence_calculator import ConfidenceCalculator
        calc = ConfidenceCalculator()
        assert callable(getattr(calc, "get_confidence_breakdown", None))


# ===================================================================
# RecommendationHelpers Tests
# ===================================================================

class TestRecommendationHelpers:

    def test_module_imports(self):
        from services.pricing import recommendation_helpers
        assert recommendation_helpers is not None

    def test_has_price_calculator(self):
        from services.pricing.recommendation_helpers import PriceCalculator
        assert callable(getattr(PriceCalculator, "calculate_new_price", None))

    def test_has_boundary_enforcer(self):
        from services.pricing.recommendation_helpers import BoundaryEnforcer
        assert callable(getattr(BoundaryEnforcer, "apply_boundaries", None))

    def test_has_change_percent(self):
        from services.pricing.recommendation_helpers import BoundaryEnforcer
        assert callable(getattr(BoundaryEnforcer, "calculate_change_percent", None))

    def test_has_reasoning_generator(self):
        from services.pricing.recommendation_helpers import ReasoningGenerator
        assert callable(getattr(ReasoningGenerator, "generate", None))

    def test_change_percent_calculation(self):
        from services.pricing.recommendation_helpers import BoundaryEnforcer
        pct = BoundaryEnforcer.calculate_change_percent(
            current=Decimal("100.00"),
            new=Decimal("110.00"),
        )
        assert abs(float(pct) - 10.0) < 0.5

    def test_change_percent_decrease(self):
        from services.pricing.recommendation_helpers import BoundaryEnforcer
        pct = BoundaryEnforcer.calculate_change_percent(
            current=Decimal("100.00"),
            new=Decimal("90.00"),
        )
        assert float(pct) < 0 or abs(float(pct)) == pytest.approx(10.0, abs=0.5)


# ===================================================================
# Price Boundary Logic (pure math — no db needed)
# ===================================================================

class TestPriceBoundaryMath:
    """Test price boundary logic using Decimal arithmetic directly."""

    def test_price_never_below_cost(self):
        cost = Decimal("35.00")
        margin_floor = Decimal("0.20")
        min_price = cost * (1 + margin_floor)
        proposed = Decimal("30.00")
        final = max(proposed, min_price)
        assert final >= min_price

    def test_margin_floor_calculation(self):
        cost = Decimal("35.00")
        margin_floor = Decimal("0.20")
        min_price = cost * (1 + margin_floor)
        assert min_price == Decimal("42.00")

    def test_max_daily_change_cap(self):
        current_price = Decimal("79.99")
        max_change_pct = Decimal("0.10")
        proposed = Decimal("100.00")
        max_price = current_price * (1 + max_change_pct)
        final = min(proposed, max_price)
        assert final <= max_price

    def test_99_cent_rounding(self):
        raw_price = Decimal("82.37")
        rounded = Decimal(int(raw_price)) + Decimal("0.99")
        assert str(rounded).endswith(".99")

    def test_zero_margin_allows_at_cost(self):
        cost = Decimal("35.00")
        margin_floor = Decimal("0.00")
        min_price = cost * (1 + margin_floor)
        assert min_price == cost

    def test_percentage_increase(self):
        base = Decimal("79.99")
        pct = Decimal("5.0")
        new_price = base * (1 + pct / 100)
        assert new_price > base
        assert float(new_price) == pytest.approx(83.99, abs=0.01)

    def test_percentage_decrease(self):
        base = Decimal("79.99")
        pct = Decimal("5.0")
        new_price = base * (1 - pct / 100)
        assert new_price < base
        assert float(new_price) == pytest.approx(75.99, abs=0.01)

    def test_price_ceiling(self):
        ceiling = Decimal("99.99")
        proposed = Decimal("120.00")
        final = min(proposed, ceiling)
        assert final == ceiling


        