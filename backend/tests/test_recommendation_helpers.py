# backend/tests/test_recommendation_helpers.py
"""
Comprehensive tests for recommendation_helpers.py — pure price calculation,
boundary enforcement, and reasoning generation.

Three static utility classes:
- PriceCalculator: Rule-based price computation
- BoundaryEnforcer: Min/max boundaries + max change clamping
- ReasoningGenerator: Human-readable explanations

Total: ~75 tests
"""

import sys
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

# === Import isolation ===
for mod in [
    "db.session",
    "models.product",
    "models.pricing_rule",
    "models.competitor",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


from services.pricing.recommendation_helpers import (
    BoundaryEnforcer,
    PriceCalculator,
    ReasoningGenerator,
)
from services.pricing.rule_evaluator import MarketSignals

# Get RuleAction from models (may be mocked)
try:
    from models.pricing_rule import RuleAction as _RA

    INCREASE_PERCENT = _RA.INCREASE_PERCENT
    DECREASE_PERCENT = _RA.DECREASE_PERCENT
    SET_ABSOLUTE = _RA.SET_ABSOLUTE
    MATCH_COMPETITOR = _RA.MATCH_COMPETITOR
    UNDERCUT_COMPETITOR = _RA.UNDERCUT_COMPETITOR
except (ImportError, AttributeError):

    class _Fake:
        def __init__(self, v):
            self.value = v

        def __eq__(self, o):
            return self.value == getattr(o, "value", o)

        def __hash__(self):
            return hash(self.value)

    INCREASE_PERCENT = _Fake("increase_percent")
    DECREASE_PERCENT = _Fake("decrease_percent")
    SET_ABSOLUTE = _Fake("set_absolute")
    MATCH_COMPETITOR = _Fake("match_competitor")
    UNDERCUT_COMPETITOR = _Fake("undercut_competitor")

# ============================================================
# Helpers
# ============================================================

COMP_ID = uuid4()


def make_product(
    name="Test Product",
    current_price=Decimal("100.00"),
    min_price=None,
    max_price=None,
):
    p = MagicMock()
    p.name = name
    p.current_price = current_price
    p.min_price = min_price
    p.max_price = max_price
    return p


def make_rule(
    action=None,
    action_value=Decimal("10"),
    competitor_id=None,
    competitor_margin_percent=None,
    min_price=None,
    max_price=None,
    max_change_percent=Decimal("15"),
    name="Test Rule",
):
    r = MagicMock()
    r.action = action
    r.action_value = action_value
    r.competitor_id = competitor_id
    r.competitor_margin_percent = competitor_margin_percent
    r.min_price = min_price
    r.max_price = max_price
    r.max_change_percent = max_change_percent
    r.name = name
    return r


def make_signals(**kwargs):
    return MarketSignals(**kwargs)


# ============================================================
# 1. PriceCalculator — calculate_new_price
# ============================================================


class TestCalculateNewPrice:
    def test_increase_percent(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(action=INCREASE_PERCENT, action_value=Decimal("10"))
        result = PriceCalculator.calculate_new_price(product, rule, make_signals())
        assert result == Decimal("110")

    def test_decrease_percent(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(action=DECREASE_PERCENT, action_value=Decimal("10"))
        result = PriceCalculator.calculate_new_price(product, rule, make_signals())
        assert result == Decimal("90")

    def test_increase_percent_fractional(self):
        product = make_product(current_price=Decimal("99.99"))
        rule = make_rule(action=INCREASE_PERCENT, action_value=Decimal("5.5"))
        result = PriceCalculator.calculate_new_price(product, rule, make_signals())
        expected = Decimal("99.99") * (1 + Decimal("5.5") / 100)
        assert result == expected

    def test_set_absolute(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(action=SET_ABSOLUTE, action_value=Decimal("79.99"))
        result = PriceCalculator.calculate_new_price(product, rule, make_signals())
        assert result == Decimal("79.99")

    def test_match_competitor(self):
        product = make_product()
        rule = make_rule(action=MATCH_COMPETITOR, competitor_id=COMP_ID)
        signals = make_signals(competitor_prices={COMP_ID: Decimal("89.99")})
        result = PriceCalculator.calculate_new_price(product, rule, signals)
        assert result == Decimal("89.99")

    def test_match_competitor_not_found(self):
        product = make_product()
        rule = make_rule(action=MATCH_COMPETITOR, competitor_id=COMP_ID)
        signals = make_signals(competitor_prices={})
        result = PriceCalculator.calculate_new_price(product, rule, signals)
        assert result is None

    def test_undercut_competitor(self):
        product = make_product()
        rule = make_rule(
            action=UNDERCUT_COMPETITOR,
            competitor_id=COMP_ID,
            competitor_margin_percent=Decimal("5"),
        )
        signals = make_signals(competitor_prices={COMP_ID: Decimal("100")})
        result = PriceCalculator.calculate_new_price(product, rule, signals)
        assert result == Decimal("95")

    def test_undercut_competitor_default_margin(self):
        """Default margin is 5%."""
        product = make_product()
        rule = make_rule(
            action=UNDERCUT_COMPETITOR,
            competitor_id=COMP_ID,
            competitor_margin_percent=None,
        )
        signals = make_signals(competitor_prices={COMP_ID: Decimal("200")})
        result = PriceCalculator.calculate_new_price(product, rule, signals)
        # 200 * (1 - 5/100) = 190
        assert result == Decimal("190")

    def test_undercut_competitor_not_found(self):
        product = make_product()
        rule = make_rule(action=UNDERCUT_COMPETITOR, competitor_id=COMP_ID)
        signals = make_signals(competitor_prices={})
        result = PriceCalculator.calculate_new_price(product, rule, signals)
        assert result is None

    def test_unknown_action_returns_none(self):
        product = make_product()
        rule = make_rule(action=MagicMock())  # Unknown action
        result = PriceCalculator.calculate_new_price(product, rule, make_signals())
        assert result is None

    def test_zero_percent_increase(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(action=INCREASE_PERCENT, action_value=Decimal("0"))
        result = PriceCalculator.calculate_new_price(product, rule, make_signals())
        assert result == Decimal("100")

    def test_100_percent_decrease(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(action=DECREASE_PERCENT, action_value=Decimal("100"))
        result = PriceCalculator.calculate_new_price(product, rule, make_signals())
        assert result == Decimal("0")


# ============================================================
# 2. PriceCalculator — _match_competitor
# ============================================================


class TestMatchCompetitor:
    def test_direct_match(self):
        rule = make_rule(competitor_id=COMP_ID)
        signals = make_signals(competitor_prices={COMP_ID: Decimal("55.50")})
        result = PriceCalculator._match_competitor(rule, signals)
        assert result == Decimal("55.50")

    def test_no_competitor_id(self):
        rule = make_rule(competitor_id=None)
        signals = make_signals(competitor_prices={COMP_ID: Decimal("55.50")})
        result = PriceCalculator._match_competitor(rule, signals)
        assert result is None

    def test_competitor_not_in_prices(self):
        rule = make_rule(competitor_id=uuid4())
        signals = make_signals(competitor_prices={COMP_ID: Decimal("55.50")})
        result = PriceCalculator._match_competitor(rule, signals)
        assert result is None

    def test_empty_competitor_prices(self):
        rule = make_rule(competitor_id=COMP_ID)
        signals = make_signals(competitor_prices={})
        result = PriceCalculator._match_competitor(rule, signals)
        assert result is None


# ============================================================
# 3. PriceCalculator — _undercut_competitor
# ============================================================


class TestUndercutCompetitor:
    def test_undercut_by_margin(self):
        rule = make_rule(
            competitor_id=COMP_ID,
            competitor_margin_percent=Decimal("10"),
        )
        signals = make_signals(competitor_prices={COMP_ID: Decimal("100")})
        result = PriceCalculator._undercut_competitor(rule, signals)
        assert result == Decimal("90")

    def test_default_margin_5_percent(self):
        rule = make_rule(
            competitor_id=COMP_ID,
            competitor_margin_percent=None,
        )
        signals = make_signals(competitor_prices={COMP_ID: Decimal("80")})
        result = PriceCalculator._undercut_competitor(rule, signals)
        assert result == Decimal("76")  # 80 * 0.95

    def test_no_competitor_id_returns_none(self):
        rule = make_rule(competitor_id=None)
        signals = make_signals(competitor_prices={COMP_ID: Decimal("100")})
        result = PriceCalculator._undercut_competitor(rule, signals)
        assert result is None

    def test_zero_margin_falls_back_to_default(self):
        """Decimal('0') is falsy, so `or Decimal('5.0')` kicks in → 5% undercut."""
        rule = make_rule(
            competitor_id=COMP_ID,
            competitor_margin_percent=Decimal("0"),
        )
        signals = make_signals(competitor_prices={COMP_ID: Decimal("100")})
        result = PriceCalculator._undercut_competitor(rule, signals)
        assert result == Decimal("95.00")  # Default 5% applied


# ============================================================
# 4. BoundaryEnforcer — apply_boundaries
# ============================================================


class TestApplyBoundaries:
    def test_no_boundaries_returns_price(self):
        product = make_product(
            current_price=Decimal("100"),
            min_price=None,
            max_price=None,
        )
        rule = make_rule(min_price=None, max_price=None, max_change_percent=Decimal("50"))
        result = BoundaryEnforcer.apply_boundaries(Decimal("110"), product, rule)
        assert result == Decimal("110.00")

    def test_clamps_to_min_price(self):
        product = make_product(
            current_price=Decimal("100"),
            min_price=Decimal("50"),
            max_price=None,
        )
        rule = make_rule(min_price=None, max_price=None, max_change_percent=Decimal("100"))
        result = BoundaryEnforcer.apply_boundaries(Decimal("30"), product, rule)
        assert result >= Decimal("50.00")

    def test_clamps_to_max_price(self):
        product = make_product(
            current_price=Decimal("100"),
            min_price=None,
            max_price=Decimal("150"),
        )
        rule = make_rule(min_price=None, max_price=None, max_change_percent=Decimal("100"))
        result = BoundaryEnforcer.apply_boundaries(Decimal("200"), product, rule)
        assert result <= Decimal("150.00")

    def test_rule_min_overrides_product_min(self):
        product = make_product(
            current_price=Decimal("100"),
            min_price=Decimal("50"),
        )
        rule = make_rule(min_price=Decimal("70"), max_price=None, max_change_percent=Decimal("100"))
        result = BoundaryEnforcer.apply_boundaries(Decimal("40"), product, rule)
        assert result >= Decimal("70.00")

    def test_rule_max_overrides_product_max(self):
        product = make_product(
            current_price=Decimal("100"),
            max_price=Decimal("200"),
        )
        rule = make_rule(min_price=None, max_price=Decimal("130"), max_change_percent=Decimal("100"))
        result = BoundaryEnforcer.apply_boundaries(Decimal("180"), product, rule)
        assert result <= Decimal("130.00")

    def test_rounds_to_two_decimals(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(min_price=None, max_price=None, max_change_percent=Decimal("50"))
        result = BoundaryEnforcer.apply_boundaries(Decimal("99.999"), product, rule)
        assert result == result.quantize(Decimal("0.01"))

    def test_max_change_percent_caps_increase(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(min_price=None, max_price=None, max_change_percent=Decimal("10"))
        result = BoundaryEnforcer.apply_boundaries(Decimal("150"), product, rule)
        assert result <= Decimal("110.00")

    def test_max_change_percent_caps_decrease(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(min_price=None, max_price=None, max_change_percent=Decimal("10"))
        result = BoundaryEnforcer.apply_boundaries(Decimal("50"), product, rule)
        assert result >= Decimal("90.00")


# ============================================================
# 5. BoundaryEnforcer — _apply_max_change
# ============================================================


class TestApplyMaxChange:
    def test_within_range_unchanged(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(max_change_percent=Decimal("10"))
        result = BoundaryEnforcer._apply_max_change(Decimal("105"), product, rule)
        assert result == Decimal("105")

    def test_above_max_clamped(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(max_change_percent=Decimal("10"))
        result = BoundaryEnforcer._apply_max_change(Decimal("120"), product, rule)
        assert result == Decimal("110")

    def test_below_min_clamped(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(max_change_percent=Decimal("10"))
        result = BoundaryEnforcer._apply_max_change(Decimal("80"), product, rule)
        assert result == Decimal("90")

    def test_exactly_at_max(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(max_change_percent=Decimal("15"))
        result = BoundaryEnforcer._apply_max_change(Decimal("115"), product, rule)
        assert result == Decimal("115")

    def test_exactly_at_min(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(max_change_percent=Decimal("15"))
        result = BoundaryEnforcer._apply_max_change(Decimal("85"), product, rule)
        assert result == Decimal("85")


# ============================================================
# 6. BoundaryEnforcer — calculate_change_percent
# ============================================================


class TestCalculateChangePercent:
    def test_positive_change(self):
        result = BoundaryEnforcer.calculate_change_percent(Decimal("100"), Decimal("110"))
        assert result == Decimal("10.00")

    def test_negative_change(self):
        result = BoundaryEnforcer.calculate_change_percent(Decimal("100"), Decimal("90"))
        assert result == Decimal("-10.00")

    def test_no_change(self):
        result = BoundaryEnforcer.calculate_change_percent(Decimal("100"), Decimal("100"))
        assert result == Decimal("0.00")

    def test_fractional_change(self):
        result = BoundaryEnforcer.calculate_change_percent(Decimal("99.99"), Decimal("102.49"))
        assert isinstance(result, Decimal)
        assert result == result.quantize(Decimal("0.01"))

    def test_large_increase(self):
        result = BoundaryEnforcer.calculate_change_percent(Decimal("50"), Decimal("100"))
        assert result == Decimal("100.00")

    def test_small_decrease(self):
        result = BoundaryEnforcer.calculate_change_percent(Decimal("100"), Decimal("99.50"))
        assert result == Decimal("-0.50")


# ============================================================
# 7. ReasoningGenerator — generate
# ============================================================


class TestReasoningGenerate:
    def test_increase_wording(self):
        product = make_product(name="Widget", current_price=Decimal("100"))
        rule = make_rule()
        match_details = {
            "rule_type": "sentiment_threshold",
            "sentiment_score": 0.8,
            "threshold": 0.5,
            "direction": "above",
        }
        result = ReasoningGenerator.generate(
            product, rule, match_details, Decimal("110"), Decimal("10.00"), make_signals()
        )
        assert "increase" in result
        assert "Widget" in result
        assert "$100" in result
        assert "$110" in result

    def test_decrease_wording(self):
        product = make_product(name="Gadget", current_price=Decimal("100"))
        rule = make_rule()
        match_details = {
            "rule_type": "sentiment_threshold",
            "sentiment_score": -0.5,
            "threshold": -0.3,
            "direction": "below",
        }
        result = ReasoningGenerator.generate(
            product, rule, match_details, Decimal("90"), Decimal("-10.00"), make_signals()
        )
        assert "decrease" in result

    def test_includes_change_percent(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule()
        match_details = {"rule_type": "volume_surge"}
        result = ReasoningGenerator.generate(
            product, rule, match_details, Decimal("105"), Decimal("5.00"), make_signals()
        )
        assert "5" in result


# ============================================================
# 8. ReasoningGenerator — _get_rule_type_detail
# ============================================================


class TestGetRuleTypeDetail:
    def test_sentiment_detail(self):
        details = {
            "rule_type": "sentiment_threshold",
            "sentiment_score": 0.85,
            "threshold": 0.5,
            "direction": "above",
        }
        result = ReasoningGenerator._get_rule_type_detail("sentiment_threshold", details, make_rule())
        assert "0.85" in result
        assert "above" in result

    def test_sentiment_below_direction(self):
        details = {
            "rule_type": "sentiment_threshold",
            "sentiment_score": -0.5,
            "threshold": -0.3,
            "direction": "below",
        }
        result = ReasoningGenerator._get_rule_type_detail("sentiment_threshold", details, make_rule())
        assert "below" in result

    def test_competitor_detail(self):
        details = {
            "rule_type": "competitor_relative",
            "competitor_price": 89.99,
        }
        result = ReasoningGenerator._get_rule_type_detail("competitor_relative", details, make_rule())
        assert "89.99" in result

    def test_time_based_detail(self):
        details = {
            "rule_type": "time_based",
            "allowed_days": ["Monday", "Friday"],
        }
        result = ReasoningGenerator._get_rule_type_detail("time_based", details, make_rule())
        assert "Monday" in result
        assert "Friday" in result

    def test_volume_detail(self):
        details = {
            "rule_type": "volume_surge",
            "mention_count": 500,
            "threshold": 200,
        }
        result = ReasoningGenerator._get_rule_type_detail("volume_surge", details, make_rule())
        assert "500" in result

    def test_viral_detail(self):
        details = {
            "rule_type": "viral_detection",
            "reach": 50000,
        }
        result = ReasoningGenerator._get_rule_type_detail("viral_detection", details, make_rule())
        assert "50,000" in result

    def test_unknown_rule_type_fallback(self):
        rule = make_rule(name="Custom Rule")
        result = ReasoningGenerator._get_rule_type_detail("unknown_type", {}, rule)
        assert "Custom Rule" in result

    def test_returns_string(self):
        result = ReasoningGenerator._get_rule_type_detail(
            "sentiment_threshold",
            {"sentiment_score": 0.5, "threshold": 0.3, "direction": "above"},
            make_rule(),
        )
        assert isinstance(result, str)


# ============================================================
# 9. Edge Cases
# ============================================================


class TestEdgeCases:
    def test_very_small_price(self):
        product = make_product(current_price=Decimal("0.01"))
        rule = make_rule(action=INCREASE_PERCENT, action_value=Decimal("10"))
        result = PriceCalculator.calculate_new_price(product, rule, make_signals())
        assert result == Decimal("0.011")

    def test_very_large_price(self):
        product = make_product(current_price=Decimal("999999.99"))
        rule = make_rule(action=INCREASE_PERCENT, action_value=Decimal("1"))
        result = PriceCalculator.calculate_new_price(product, rule, make_signals())
        expected = Decimal("999999.99") * Decimal("1.01")
        assert result == expected

    def test_boundary_enforcer_rounds_half_up(self):
        product = make_product(current_price=Decimal("100"))
        rule = make_rule(min_price=None, max_price=None, max_change_percent=Decimal("50"))
        result = BoundaryEnforcer.apply_boundaries(Decimal("100.005"), product, rule)
        assert result == Decimal("100.01")  # ROUND_HALF_UP

    def test_change_percent_precision(self):
        result = BoundaryEnforcer.calculate_change_percent(Decimal("3"), Decimal("4"))
        assert result == Decimal("33.33")

    def test_reasoning_with_zero_change(self):
        product = make_product(name="X", current_price=Decimal("100"))
        rule = make_rule()
        result = ReasoningGenerator.generate(
            product,
            rule,
            {"rule_type": "time_based", "allowed_days": []},
            Decimal("100"),
            Decimal("0.00"),
            make_signals(),
        )
        assert isinstance(result, str)
