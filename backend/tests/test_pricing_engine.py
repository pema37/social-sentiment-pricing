# backend/tests/test_pricing_engine.py
"""
Comprehensive tests for the core PricingEngine.

Tests cover:
- PricingEngine initialization and defaults
- Sentiment adjustment calculation
- Competitor adjustment calculation
- Combined weighted adjustments
- Change percent clamping
- Price boundary enforcement
- Confidence scoring
- Trend detection
- Reasoning generation
- Competitive position analysis
- Price war detection
- Full calculate_suggestion integration
- Edge cases (zero prices, empty data, boundary conditions)

Total: ~120 tests
"""

import sys
from unittest.mock import MagicMock

# === Import isolation: prevent db.session from loading asyncpg ===
if "db.session" not in sys.modules:
    sys.modules["db.session"] = MagicMock()
if "models.product" not in sys.modules:
    sys.modules["models.product"] = MagicMock()

import pytest
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from dataclasses import dataclass

# Now safe to import
from services.pricing_engine import (
    PricingEngine,
    CompetitorPriceData,
    PriceSuggestion,
    pricing_engine,
)


# ============================================================
# Helpers
# ============================================================

def make_product(
    id="prod-123",
    current_price=Decimal("100.00"),
    base_price=Decimal("80.00"),
    sentiment_multiplier=None,
    min_price=None,
    max_price=None,
):
    """Create a mock Product with required attributes."""
    product = MagicMock()
    product.id = id
    product.current_price = current_price
    product.base_price = base_price
    product.sentiment_multiplier = sentiment_multiplier
    product.min_price = min_price
    product.max_price = max_price
    return product


def make_competitor(
    name="CompetitorA",
    price=Decimal("95.00"),
    difference=Decimal("5.00"),
    difference_percent=Decimal("5.00"),
    is_promotion=False,
):
    """Create a CompetitorPriceData instance."""
    return CompetitorPriceData(
        competitor_name=name,
        competitor_price=price,
        price_difference=difference,
        price_difference_percent=difference_percent,
        last_updated=datetime.now(timezone.utc),
        is_promotion=is_promotion,
    )


# ============================================================
# 1. Dataclass Tests
# ============================================================

class TestCompetitorPriceData:
    """Tests for CompetitorPriceData dataclass."""

    def test_basic_creation(self):
        cpd = make_competitor()
        assert cpd.competitor_name == "CompetitorA"
        assert cpd.competitor_price == Decimal("95.00")
        assert cpd.is_promotion is False

    def test_promotion_flag_default_false(self):
        cpd = CompetitorPriceData(
            competitor_name="X",
            competitor_price=Decimal("10"),
            price_difference=Decimal("1"),
            price_difference_percent=Decimal("10"),
            last_updated=datetime.now(timezone.utc),
        )
        assert cpd.is_promotion is False

    def test_promotion_flag_explicit_true(self):
        cpd = make_competitor(is_promotion=True)
        assert cpd.is_promotion is True

    def test_negative_price_difference(self):
        cpd = make_competitor(difference=Decimal("-5.00"))
        assert cpd.price_difference == Decimal("-5.00")


class TestPriceSuggestion:
    """Tests for PriceSuggestion dataclass."""

    def test_basic_creation(self):
        ps = PriceSuggestion(
            product_id="p1",
            current_price=Decimal("100"),
            suggested_price=Decimal("105"),
            change_percent=Decimal("5.0"),
            reasoning="Test",
            confidence=Decimal("0.8"),
            factors={"sentiment_score": Decimal("0.5")},
        )
        assert ps.product_id == "p1"
        assert ps.competitor_analysis is None

    def test_with_competitor_analysis(self):
        ps = PriceSuggestion(
            product_id="p1",
            current_price=Decimal("100"),
            suggested_price=Decimal("105"),
            change_percent=Decimal("5.0"),
            reasoning="Test",
            confidence=Decimal("0.8"),
            factors={},
            competitor_analysis={"position": "middle"},
        )
        assert ps.competitor_analysis == {"position": "middle"}


# ============================================================
# 2. PricingEngine Initialization
# ============================================================

class TestPricingEngineInit:
    """Tests for PricingEngine constructor and defaults."""

    def test_default_values(self):
        engine = PricingEngine()
        assert engine.default_multiplier == Decimal("0.1")
        assert engine.min_change_percent == Decimal("1.0")
        assert engine.max_change_percent == Decimal("15.0")
        assert engine.sentiment_weight == Decimal("0.6")
        assert engine.competitor_weight == Decimal("0.4")

    def test_custom_multiplier(self):
        engine = PricingEngine(default_multiplier=Decimal("0.2"))
        assert engine.default_multiplier == Decimal("0.2")

    def test_custom_weights(self):
        engine = PricingEngine(
            sentiment_weight=Decimal("0.7"),
            competitor_weight=Decimal("0.3"),
        )
        assert engine.sentiment_weight == Decimal("0.7")
        assert engine.competitor_weight == Decimal("0.3")

    def test_custom_change_limits(self):
        engine = PricingEngine(
            min_change_percent=Decimal("0.5"),
            max_change_percent=Decimal("20.0"),
        )
        assert engine.min_change_percent == Decimal("0.5")
        assert engine.max_change_percent == Decimal("20.0")

    def test_weights_sum_to_one_by_default(self):
        engine = PricingEngine()
        assert engine.sentiment_weight + engine.competitor_weight == Decimal("1.0")


# ============================================================
# 3. Sentiment Adjustment
# ============================================================

class TestSentimentAdjustment:
    """Tests for _calculate_sentiment_adjustment."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_positive_sentiment(self):
        result = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("80"),
            current_price=Decimal("100"),
            sentiment_score=Decimal("0.5"),
            multiplier=Decimal("0.1"),
        )
        # 80 * 0.5 * 0.1 = 4.0
        assert result == Decimal("4.0")

    def test_negative_sentiment(self):
        result = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("80"),
            current_price=Decimal("100"),
            sentiment_score=Decimal("-0.5"),
            multiplier=Decimal("0.1"),
        )
        assert result == Decimal("-4.0")

    def test_zero_sentiment(self):
        result = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("80"),
            current_price=Decimal("100"),
            sentiment_score=Decimal("0"),
            multiplier=Decimal("0.1"),
        )
        assert result == Decimal("0")

    def test_max_positive_sentiment(self):
        result = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("100"),
            current_price=Decimal("100"),
            sentiment_score=Decimal("1.0"),
            multiplier=Decimal("0.1"),
        )
        # 100 * 1.0 * 0.1 = 10
        assert result == Decimal("10.0")

    def test_max_negative_sentiment(self):
        result = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("100"),
            current_price=Decimal("100"),
            sentiment_score=Decimal("-1.0"),
            multiplier=Decimal("0.1"),
        )
        assert result == Decimal("-10.0")

    def test_custom_multiplier(self):
        result = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("50"),
            current_price=Decimal("60"),
            sentiment_score=Decimal("0.8"),
            multiplier=Decimal("0.2"),
        )
        # 50 * 0.8 * 0.2 = 8.0
        assert result == Decimal("8.0")

    def test_formula_uses_base_price_not_current(self):
        """Sentiment adjustment is based on base_price, not current_price."""
        result_base80 = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("80"),
            current_price=Decimal("200"),  # current doesn't matter
            sentiment_score=Decimal("0.5"),
            multiplier=Decimal("0.1"),
        )
        result_base160 = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("160"),
            current_price=Decimal("200"),
            sentiment_score=Decimal("0.5"),
            multiplier=Decimal("0.1"),
        )
        assert result_base160 == result_base80 * 2

    def test_zero_base_price(self):
        result = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("0"),
            current_price=Decimal("100"),
            sentiment_score=Decimal("0.5"),
            multiplier=Decimal("0.1"),
        )
        assert result == Decimal("0")


# ============================================================
# 4. Competitor Adjustment
# ============================================================

class TestCompetitorAdjustment:
    """Tests for _calculate_competitor_adjustment."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_empty_competitor_list(self):
        adjustment, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=[],
        )
        assert adjustment == Decimal("0")
        assert analysis is None

    def test_single_competitor_lower(self):
        """When we're priced higher than competitor."""
        competitors = [make_competitor(price=Decimal("90.00"))]
        adjustment, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=competitors,
        )
        # target = 90 * 0.98 = 88.2, adjustment = 88.2 - 100 = -11.8
        expected_target = Decimal("90") * Decimal("0.98")
        expected_adj = expected_target - Decimal("100")
        assert adjustment == expected_adj
        assert analysis["your_position"] == "highest"

    def test_single_competitor_higher(self):
        """When we're priced lower than competitor."""
        competitors = [make_competitor(price=Decimal("120.00"))]
        adjustment, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=competitors,
        )
        # target = 120 * 0.98 = 117.6, adjustment = 117.6 - 100 = 17.6
        expected_target = Decimal("120") * Decimal("0.98")
        expected_adj = expected_target - Decimal("100")
        assert adjustment == expected_adj
        assert analysis["your_position"] == "lowest"

    def test_multiple_competitors_middle_position(self):
        """When we're between competitors."""
        competitors = [
            make_competitor(name="Low", price=Decimal("80")),
            make_competitor(name="High", price=Decimal("120")),
        ]
        _, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=competitors,
        )
        assert analysis["your_position"] == "middle"
        assert analysis["competitor_count"] == 2
        assert analysis["average_price"] == Decimal("100.00")

    def test_analysis_price_statistics(self):
        competitors = [
            make_competitor(name="A", price=Decimal("80")),
            make_competitor(name="B", price=Decimal("100")),
            make_competitor(name="C", price=Decimal("120")),
        ]
        _, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("95"),
            competitor_prices=competitors,
        )
        assert analysis["min_price"] == Decimal("80")
        assert analysis["max_price"] == Decimal("120")
        assert analysis["competitor_count"] == 3

    def test_promotion_pressure_reduces_adjustment(self):
        """When >50% competitors on promotion, adjustment is halved."""
        competitors = [
            make_competitor(name="A", price=Decimal("70"), is_promotion=True),
            make_competitor(name="B", price=Decimal("75"), is_promotion=True),
            make_competitor(name="C", price=Decimal("90"), is_promotion=False),
        ]
        adjustment_with_promos, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=competitors,
        )
        # promotion_pressure = 2/3 ≈ 0.667 > 0.5 → adjustment halved
        assert analysis["active_promotions"] == 2
        assert float(analysis["promotion_pressure"]) > 0.5

        # Without promotions, same prices
        competitors_no_promo = [
            make_competitor(name="A", price=Decimal("70")),
            make_competitor(name="B", price=Decimal("75")),
            make_competitor(name="C", price=Decimal("90")),
        ]
        adjustment_no_promos, _ = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=competitors_no_promo,
        )
        # With promotions, adjustment should be half
        assert adjustment_with_promos == adjustment_no_promos * Decimal("0.5")

    def test_low_promotion_pressure_no_reduction(self):
        """When <50% on promotion, no reduction."""
        competitors = [
            make_competitor(name="A", price=Decimal("90"), is_promotion=True),
            make_competitor(name="B", price=Decimal("95")),
            make_competitor(name="C", price=Decimal("100")),
        ]
        _, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=competitors,
        )
        assert analysis["active_promotions"] == 1
        # 1/3 ≈ 0.33, not > 0.5

    def test_analysis_includes_competitor_details(self):
        competitors = [make_competitor(name="TestCo", price=Decimal("85"))]
        _, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=competitors,
        )
        assert len(analysis["competitors"]) == 1
        assert analysis["competitors"][0]["name"] == "TestCo"
        assert analysis["competitors"][0]["price"] == Decimal("85")

    def test_price_gap_calculation(self):
        competitors = [make_competitor(price=Decimal("80"))]
        _, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=competitors,
        )
        # price_gap = 100 - 80 = 20
        assert analysis["price_gap"] == Decimal("20.00")
        # price_gap_percent = (20/80)*100 = 25.00
        assert analysis["price_gap_percent"] == Decimal("25.00")


# ============================================================
# 5. Clamp Change
# ============================================================

class TestClampChange:
    """Tests for _clamp_change."""

    def setup_method(self):
        self.engine = PricingEngine()  # min=1%, max=15%

    def test_below_min_returns_zero(self):
        assert self.engine._clamp_change(Decimal("0.5")) == Decimal("0")

    def test_negative_below_min_returns_zero(self):
        assert self.engine._clamp_change(Decimal("-0.5")) == Decimal("0")

    def test_exactly_at_min(self):
        result = self.engine._clamp_change(Decimal("1.0"))
        assert result == Decimal("1.0")

    def test_above_max_clamped(self):
        assert self.engine._clamp_change(Decimal("20.0")) == Decimal("15.0")

    def test_negative_above_max_clamped(self):
        assert self.engine._clamp_change(Decimal("-20.0")) == Decimal("-15.0")

    def test_exactly_at_max(self):
        assert self.engine._clamp_change(Decimal("15.0")) == Decimal("15.0")

    def test_within_range_unchanged(self):
        assert self.engine._clamp_change(Decimal("7.5")) == Decimal("7.5")

    def test_negative_within_range(self):
        assert self.engine._clamp_change(Decimal("-7.5")) == Decimal("-7.5")

    def test_zero_returns_zero(self):
        assert self.engine._clamp_change(Decimal("0")) == Decimal("0")

    def test_custom_limits(self):
        engine = PricingEngine(min_change_percent=Decimal("2.0"), max_change_percent=Decimal("10.0"))
        assert engine._clamp_change(Decimal("1.5")) == Decimal("0")
        assert engine._clamp_change(Decimal("12.0")) == Decimal("10.0")
        assert engine._clamp_change(Decimal("5.0")) == Decimal("5.0")


# ============================================================
# 6. Apply Boundaries
# ============================================================

class TestApplyBoundaries:
    """Tests for _apply_boundaries."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_no_boundaries(self):
        result = self.engine._apply_boundaries(Decimal("100"), None, None)
        assert result == Decimal("100")

    def test_below_min_price(self):
        result = self.engine._apply_boundaries(
            Decimal("40"), Decimal("50"), Decimal("200")
        )
        assert result == Decimal("50")

    def test_above_max_price(self):
        result = self.engine._apply_boundaries(
            Decimal("250"), Decimal("50"), Decimal("200")
        )
        assert result == Decimal("200")

    def test_within_boundaries(self):
        result = self.engine._apply_boundaries(
            Decimal("100"), Decimal("50"), Decimal("200")
        )
        assert result == Decimal("100")

    def test_only_min_boundary(self):
        result = self.engine._apply_boundaries(
            Decimal("40"), Decimal("50"), None
        )
        assert result == Decimal("50")

    def test_only_max_boundary(self):
        result = self.engine._apply_boundaries(
            Decimal("250"), None, Decimal("200")
        )
        assert result == Decimal("200")

    def test_exactly_at_min(self):
        result = self.engine._apply_boundaries(
            Decimal("50"), Decimal("50"), Decimal("200")
        )
        assert result == Decimal("50")

    def test_exactly_at_max(self):
        result = self.engine._apply_boundaries(
            Decimal("200"), Decimal("50"), Decimal("200")
        )
        assert result == Decimal("200")


# ============================================================
# 7. Confidence Calculation
# ============================================================

class TestConfidenceCalculation:
    """Tests for _calculate_confidence."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_zero_mentions_no_competitor(self):
        result = self.engine._calculate_confidence(0, False, 0)
        assert result == Decimal("0.10")

    def test_low_mentions(self):
        result = self.engine._calculate_confidence(5, False, 0)
        assert result == Decimal("0.30")

    def test_medium_mentions(self):
        result = self.engine._calculate_confidence(25, False, 0)
        assert result == Decimal("0.50")

    def test_high_mentions(self):
        result = self.engine._calculate_confidence(75, False, 0)
        assert result == Decimal("0.70")

    def test_very_high_mentions(self):
        result = self.engine._calculate_confidence(200, False, 0)
        assert result == Decimal("0.85")

    def test_max_mentions(self):
        result = self.engine._calculate_confidence(1000, False, 0)
        assert result == Decimal("0.95")

    def test_competitor_boost_single(self):
        # 0 mentions (0.1) + 1 competitor (0.05) = 0.15
        result = self.engine._calculate_confidence(0, True, 1)
        assert result == Decimal("0.15")

    def test_competitor_boost_multiple(self):
        # 25 mentions (0.5) + 3 competitors (0.15 capped) = 0.65
        result = self.engine._calculate_confidence(25, True, 3)
        assert result == Decimal("0.65")

    def test_competitor_boost_capped_at_015(self):
        # boost = min(0.15, 5 * 0.05) = min(0.15, 0.25) = 0.15
        result = self.engine._calculate_confidence(25, True, 5)
        assert result == Decimal("0.65")  # 0.5 + 0.15

    def test_total_confidence_capped_at_099(self):
        # 500+ mentions (0.95) + 3 competitors (0.15) = 1.10 → capped at 0.99
        result = self.engine._calculate_confidence(1000, True, 3)
        assert result == Decimal("0.99")

    def test_confidence_rounded_to_two_decimals(self):
        result = self.engine._calculate_confidence(5, True, 1)
        assert result == result.quantize(Decimal("0.01"))

    def test_boundary_mention_10(self):
        result = self.engine._calculate_confidence(10, False, 0)
        assert result == Decimal("0.50")

    def test_boundary_mention_50(self):
        result = self.engine._calculate_confidence(50, False, 0)
        assert result == Decimal("0.70")

    def test_boundary_mention_100(self):
        result = self.engine._calculate_confidence(100, False, 0)
        assert result == Decimal("0.85")

    def test_boundary_mention_500(self):
        result = self.engine._calculate_confidence(500, False, 0)
        assert result == Decimal("0.95")


# ============================================================
# 8. Trend Detection
# ============================================================

class TestGetTrend:
    """Tests for _get_trend."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_positive_rising(self):
        assert self.engine._get_trend(Decimal("0.5")) == "rising"

    def test_negative_falling(self):
        assert self.engine._get_trend(Decimal("-0.5")) == "falling"

    def test_neutral_zero(self):
        assert self.engine._get_trend(Decimal("0")) == "stable"

    def test_boundary_positive(self):
        assert self.engine._get_trend(Decimal("0.1")) == "stable"

    def test_boundary_just_above(self):
        assert self.engine._get_trend(Decimal("0.11")) == "rising"

    def test_boundary_negative(self):
        assert self.engine._get_trend(Decimal("-0.1")) == "stable"

    def test_boundary_just_below(self):
        assert self.engine._get_trend(Decimal("-0.11")) == "falling"


# ============================================================
# 9. Reasoning Generation
# ============================================================

class TestGenerateReasoning:
    """Tests for _generate_reasoning."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_no_mentions(self):
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("0"),
            mention_volume=0,
            change_percent=Decimal("0"),
            competitor_analysis=None,
        )
        assert "Limited sentiment data" in reasoning

    def test_positive_sentiment_with_mentions(self):
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
            change_percent=Decimal("3.0"),
            competitor_analysis=None,
        )
        assert "Positive" in reasoning
        assert "50 mentions" in reasoning

    def test_negative_sentiment(self):
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("-0.5"),
            mention_volume=30,
            change_percent=Decimal("-2.0"),
            competitor_analysis=None,
        )
        assert "Negative" in reasoning
        assert "decrease" in reasoning

    def test_neutral_sentiment(self):
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("0.05"),
            mention_volume=20,
            change_percent=Decimal("0"),
            competitor_analysis=None,
        )
        assert "Neutral" in reasoning
        assert "No price adjustment" in reasoning

    def test_with_competitor_highest_position(self):
        analysis = {
            "your_position": "highest",
            "competitor_count": 3,
            "price_gap_percent": Decimal("15.00"),
            "active_promotions": 0,
        }
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("0.3"),
            mention_volume=50,
            change_percent=Decimal("-2.0"),
            competitor_analysis=analysis,
        )
        assert "highest" in reasoning
        assert "3 competitors" in reasoning

    def test_with_competitor_lowest_position(self):
        analysis = {
            "your_position": "lowest",
            "competitor_count": 2,
            "price_gap_percent": Decimal("-10.00"),
            "active_promotions": 0,
        }
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("0.3"),
            mention_volume=50,
            change_percent=Decimal("3.0"),
            competitor_analysis=analysis,
        )
        assert "lowest" in reasoning

    def test_with_competitor_middle_position(self):
        analysis = {
            "your_position": "middle",
            "competitor_count": 4,
            "price_gap_percent": Decimal("2.00"),
            "active_promotions": 0,
        }
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("0.3"),
            mention_volume=50,
            change_percent=Decimal("1.5"),
            competitor_analysis=analysis,
        )
        assert "Competitively positioned" in reasoning

    def test_promotion_note(self):
        analysis = {
            "your_position": "middle",
            "competitor_count": 3,
            "price_gap_percent": Decimal("5.00"),
            "active_promotions": 2,
        }
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("0.3"),
            mention_volume=50,
            change_percent=Decimal("1.5"),
            competitor_analysis=analysis,
        )
        assert "2 competitor(s) running promotions" in reasoning

    def test_increase_direction(self):
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
            change_percent=Decimal("5.0"),
            competitor_analysis=None,
        )
        assert "increase" in reasoning
        assert "5.0%" in reasoning

    def test_decrease_direction(self):
        reasoning = self.engine._generate_reasoning(
            sentiment_score=Decimal("-0.5"),
            mention_volume=50,
            change_percent=Decimal("-3.0"),
            competitor_analysis=None,
        )
        assert "decrease" in reasoning
        assert "3.0%" in reasoning


# ============================================================
# 10. Competitive Position Analysis
# ============================================================

class TestCompetitivePosition:
    """Tests for get_competitive_position."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_no_competitors(self):
        result = self.engine.get_competitive_position(
            Decimal("100"), []
        )
        assert result["position"] == "no_data"

    def test_single_competitor_we_are_higher(self):
        competitors = [make_competitor(price=Decimal("80"))]
        result = self.engine.get_competitive_position(
            Decimal("100"), competitors
        )
        assert result["competitor_count"] == 1
        assert result["your_price"] == Decimal("100")
        assert result["your_rank"] == 2  # we're #2 (highest of 2)
        assert result["total_in_market"] == 2

    def test_single_competitor_we_are_lower(self):
        competitors = [make_competitor(price=Decimal("120"))]
        result = self.engine.get_competitive_position(
            Decimal("100"), competitors
        )
        assert result["your_rank"] == 1

    def test_vs_average_percent(self):
        competitors = [make_competitor(price=Decimal("80"))]
        result = self.engine.get_competitive_position(
            Decimal("100"), competitors
        )
        # (100 - 80) / 80 * 100 = 25.00%
        assert result["vs_average_percent"] == Decimal("25.00")

    def test_multiple_competitors_ranking(self):
        competitors = [
            make_competitor(name="A", price=Decimal("80")),
            make_competitor(name="B", price=Decimal("90")),
            make_competitor(name="C", price=Decimal("110")),
        ]
        result = self.engine.get_competitive_position(
            Decimal("100"), competitors
        )
        # sorted: 80, 90, 100, 110 → rank 3
        assert result["your_rank"] == 3
        assert result["total_in_market"] == 4

    def test_percentile_calculation(self):
        competitors = [
            make_competitor(price=Decimal("80")),
            make_competitor(price=Decimal("120")),
        ]
        result = self.engine.get_competitive_position(
            Decimal("100"), competitors
        )
        # sorted: 80, 100, 120 → rank=2, total=3
        # percentile = (3-2)/3*100 = 33.33...
        assert result["percentile"] > 0

    def test_min_max_competitor_prices(self):
        competitors = [
            make_competitor(price=Decimal("60")),
            make_competitor(price=Decimal("150")),
        ]
        result = self.engine.get_competitive_position(
            Decimal("100"), competitors
        )
        assert result["min_competitor_price"] == Decimal("60")
        assert result["max_competitor_price"] == Decimal("150")


# ============================================================
# 11. Price War Detection
# ============================================================

class TestPriceWarDetection:
    """Tests for detect_price_war."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_no_competitors(self):
        result = self.engine.detect_price_war([])
        assert result["detected"] is False
        assert "No competitor data" in result["reason"]

    def test_no_price_war(self):
        competitors = [
            make_competitor(is_promotion=False),
            make_competitor(name="B", is_promotion=False),
        ]
        result = self.engine.detect_price_war(competitors)
        assert result["detected"] is False
        assert "Normal market" in result["recommendation"]

    def test_price_war_detected_medium(self):
        competitors = [
            make_competitor(name="A", is_promotion=True),
            make_competitor(name="B", is_promotion=True),
            make_competitor(name="C", is_promotion=False),
        ]
        result = self.engine.detect_price_war(competitors)
        assert result["detected"] is True
        assert result["severity"] == "medium"

    def test_price_war_detected_high(self):
        competitors = [
            make_competitor(name="A", is_promotion=True),
            make_competitor(name="B", is_promotion=True),
            make_competitor(name="C", is_promotion=True),
            make_competitor(name="D", is_promotion=True),
        ]
        result = self.engine.detect_price_war(competitors)
        assert result["detected"] is True
        assert result["severity"] == "high"
        assert "Hold prices steady" in result["recommendation"]

    def test_exactly_50_percent_no_war(self):
        competitors = [
            make_competitor(name="A", is_promotion=True),
            make_competitor(name="B", is_promotion=False),
        ]
        result = self.engine.detect_price_war(competitors)
        # 0.5 is not > 0.5, so no war
        assert result["detected"] is False

    def test_just_over_50_percent_war(self):
        competitors = [
            make_competitor(name="A", is_promotion=True),
            make_competitor(name="B", is_promotion=True),
            make_competitor(name="C", is_promotion=False),
        ]
        result = self.engine.detect_price_war(competitors)
        # 2/3 > 0.5 → war
        assert result["detected"] is True

    def test_promotion_rate_returned(self):
        competitors = [
            make_competitor(name="A", is_promotion=True),
            make_competitor(name="B", is_promotion=False),
            make_competitor(name="C", is_promotion=False),
            make_competitor(name="D", is_promotion=False),
        ]
        result = self.engine.detect_price_war(competitors)
        assert result["promotion_rate"] == 0.25


# ============================================================
# 12. Full Integration: calculate_suggestion
# ============================================================

class TestCalculateSuggestion:
    """Integration tests for the full calculate_suggestion pipeline."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_sentiment_only_positive(self):
        product = make_product()
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
        )
        assert result["product_id"] == "prod-123"
        assert result["current_price"] == Decimal("100.00")
        assert result["suggested_price"] > Decimal("100.00")
        assert result["change_percent"] > 0
        assert "factors" in result
        assert result["competitor_analysis"] is None

    def test_sentiment_only_negative(self):
        product = make_product()
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("-0.5"),
            mention_volume=50,
        )
        assert result["suggested_price"] < Decimal("100.00")
        assert result["change_percent"] < 0

    def test_with_competitors(self):
        product = make_product()
        competitors = [
            make_competitor(name="A", price=Decimal("90")),
            make_competitor(name="B", price=Decimal("95")),
        ]
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.3"),
            mention_volume=50,
            competitor_prices=competitors,
        )
        assert result["competitor_analysis"] is not None
        assert result["competitor_analysis"]["competitor_count"] == 2
        assert result["factors"]["competitor_weight"] == Decimal("0.4")

    def test_no_competitors_weight_is_zero(self):
        product = make_product()
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.3"),
            mention_volume=50,
        )
        assert result["factors"]["competitor_weight"] == Decimal("0")

    def test_zero_sentiment_small_change_clamped_to_zero(self):
        """Near-zero sentiment should produce 0 change (below min threshold)."""
        product = make_product()
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.01"),
            mention_volume=10,
        )
        # base_price(80) * 0.01 * 0.1 = 0.08 → 0.08% change → below 1% min → clamped to 0
        assert result["change_percent"] == Decimal("0.00")
        assert result["suggested_price"] == result["current_price"]

    def test_product_uses_custom_multiplier(self):
        product = make_product(sentiment_multiplier=Decimal("0.3"))
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
        )
        assert result["factors"]["multiplier"] == Decimal("0.3")

    def test_product_uses_default_multiplier_when_none(self):
        product = make_product(sentiment_multiplier=None)
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
        )
        assert result["factors"]["multiplier"] == Decimal("0.1")

    def test_min_price_boundary_enforced(self):
        product = make_product(
            current_price=Decimal("55"),
            base_price=Decimal("50"),
            min_price=Decimal("50"),
        )
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("-1.0"),
            mention_volume=100,
        )
        assert result["suggested_price"] >= Decimal("50")

    def test_max_price_boundary_enforced(self):
        product = make_product(
            current_price=Decimal("95"),
            base_price=Decimal("80"),
            max_price=Decimal("100"),
        )
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("1.0"),
            mention_volume=100,
        )
        assert result["suggested_price"] <= Decimal("100")

    def test_suggested_price_rounded_to_two_decimals(self):
        product = make_product()
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.33"),
            mention_volume=50,
        )
        # Check it has exactly 2 decimal places
        assert result["suggested_price"] == result["suggested_price"].quantize(Decimal("0.01"))

    def test_change_percent_rounded_to_two_decimals(self):
        product = make_product()
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.33"),
            mention_volume=50,
        )
        assert result["change_percent"] == result["change_percent"].quantize(Decimal("0.01"))

    def test_zero_current_price(self):
        product = make_product(current_price=Decimal("0"), base_price=Decimal("0"))
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=10,
        )
        assert result["change_percent"] == Decimal("0")

    def test_zero_mention_volume(self):
        product = make_product()
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=0,
        )
        assert result["confidence"] == Decimal("0.10")
        assert "Limited sentiment data" in result["reasoning"]

    def test_factors_include_all_keys(self):
        product = make_product()
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
        )
        factors = result["factors"]
        expected_keys = {
            "sentiment_score", "mention_volume", "multiplier", "trend",
            "sentiment_weight", "competitor_weight",
            "sentiment_adjustment_raw", "competitor_adjustment_raw",
        }
        assert set(factors.keys()) == expected_keys

    def test_trend_in_factors(self):
        product = make_product()
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
        )
        assert result["factors"]["trend"] == "rising"

    def test_weighted_combination_with_competitors(self):
        """Verify the weighted combination formula."""
        engine = PricingEngine(
            sentiment_weight=Decimal("0.6"),
            competitor_weight=Decimal("0.4"),
        )
        product = make_product(
            current_price=Decimal("100"),
            base_price=Decimal("100"),
        )
        # sentiment_adjustment = 100 * 0.5 * 0.1 = 5
        # competitor target = avg * 0.98 → need to calculate
        competitors = [make_competitor(price=Decimal("100"))]
        result = engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
            competitor_prices=competitors,
        )
        # Combined = 5*0.6 + (100*0.98-100)*0.4 = 3.0 + (-2)*0.4 = 3.0 - 0.8 = 2.2
        # change_percent = 2.2/100 * 100 = 2.2%
        assert result["factors"]["sentiment_weight"] == Decimal("0.6")
        assert result["factors"]["competitor_weight"] == Decimal("0.4")


# ============================================================
# 13. Singleton Instance
# ============================================================

class TestSingletonInstance:
    """Tests for the module-level pricing_engine singleton."""

    def test_singleton_exists(self):
        assert pricing_engine is not None

    def test_singleton_is_pricing_engine(self):
        assert isinstance(pricing_engine, PricingEngine)

    def test_singleton_has_default_values(self):
        assert pricing_engine.default_multiplier == Decimal("0.1")
        assert pricing_engine.sentiment_weight == Decimal("0.6")
        assert pricing_engine.competitor_weight == Decimal("0.4")


# ============================================================
# 14. Edge Cases
# ============================================================

class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def setup_method(self):
        self.engine = PricingEngine()

    def test_very_large_sentiment(self):
        """Sentiment score beyond normal -1 to 1 range."""
        result = self.engine._calculate_sentiment_adjustment(
            base_price=Decimal("100"),
            current_price=Decimal("100"),
            sentiment_score=Decimal("2.0"),  # beyond normal range
            multiplier=Decimal("0.1"),
        )
        assert result == Decimal("20.0")

    def test_very_small_price(self):
        product = make_product(
            current_price=Decimal("0.01"),
            base_price=Decimal("0.01"),
        )
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
        )
        assert result["suggested_price"] >= Decimal("0")

    def test_very_large_price(self):
        product = make_product(
            current_price=Decimal("99999.99"),
            base_price=Decimal("80000.00"),
        )
        result = self.engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("0.5"),
            mention_volume=50,
        )
        assert result["suggested_price"] > Decimal("0")

    def test_many_competitors(self):
        competitors = [
            make_competitor(name=f"C{i}", price=Decimal(str(80 + i)))
            for i in range(20)
        ]
        _, analysis = self.engine._calculate_competitor_adjustment(
            current_price=Decimal("100"),
            competitor_prices=competitors,
        )
        assert analysis["competitor_count"] == 20

    def test_all_competitors_same_price(self):
        competitors = [
            make_competitor(name=f"C{i}", price=Decimal("100"))
            for i in range(3)
        ]
        result = self.engine.get_competitive_position(
            Decimal("100"), competitors
        )
        assert result["vs_average_percent"] == Decimal("0.00")

    def test_max_change_clamp_integration(self):
        """Large sentiment should be clamped to max 15%."""
        engine = PricingEngine(default_multiplier=Decimal("0.5"))
        product = make_product(
            current_price=Decimal("100"),
            base_price=Decimal("100"),
        )
        result = engine.calculate_suggestion(
            product=product,
            sentiment_score=Decimal("1.0"),
            mention_volume=100,
        )
        # 100 * 1.0 * 0.5 = 50 → 50% change → clamped to 15%
        assert result["change_percent"] <= Decimal("15.00")
        assert result["suggested_price"] <= Decimal("115.00")


        