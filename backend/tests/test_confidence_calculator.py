# backend/tests/test_confidence_calculator.py
"""
Comprehensive tests for ConfidenceCalculator — calculates confidence scores
for price recommendations based on 5 weighted factors.

Tests cover:
- Initialization (with/without db)
- calculate() overall pipeline + weighted formula
- _score_data_quality (mentions, sentiment, competitor tiers)
- _score_signal_agreement (all agree, mixed, empty)
- _score_rule_confidence (all 5 rule types + no rule)
- _score_historical_accuracy (with/without db, delegation)
- _score_market_stability (volatility thresholds, linear interpolation)
- _calculate_price_volatility (coefficient of variation, edge cases)
- _calculate_sentiment_volatility (normalization, edge cases)
- get_confidence_breakdown (structure + values)
- Edge cases (zero data, max data, clamping)

Total: ~90 tests
"""

import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

# === Import isolation ===
for mod in [
    "db.session",
    "models.product",
    "models.pricing_rule",
    "models.price_history",
    "models.sentiment",
    "models.competitor",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Fix: MagicMock.__ge__ returns NotImplemented by default,
# causing TypeError when compared with datetime.
# Configure model column mocks to support SQLAlchemy-style comparisons.
_ph = sys.modules["models.price_history"]
try:
    _ph.PriceHistory.created_at.__ge__ = MagicMock(return_value=MagicMock())
    _ph.PriceHistory.created_at.__le__ = MagicMock(return_value=MagicMock())
    _ph.PriceHistory.product_id.__eq__ = MagicMock(return_value=MagicMock())
except (AttributeError, TypeError):
    pass  # Real SQLAlchemy model — operators already work

_sent = sys.modules["models.sentiment"]
try:
    _sent.Sentiment.analyzed_at.__ge__ = MagicMock(return_value=MagicMock())
    _sent.Sentiment.analyzed_at.__le__ = MagicMock(return_value=MagicMock())
    _sent.Sentiment.product_id.__eq__ = MagicMock(return_value=MagicMock())
except (AttributeError, TypeError):
    pass  # Real SQLAlchemy model — operators already work


from services.pricing.confidence_calculator import ConfidenceCalculator
from services.pricing.rule_evaluator import MarketSignals

SERVICE_PATH = "services.pricing.confidence_calculator"

# ============================================================
# Helpers
# ============================================================

USER_ID = uuid4()
PRODUCT_ID = uuid4()
COMP_A = uuid4()
COMP_B = uuid4()
COMP_C = uuid4()


def make_signals(**kwargs):
    return MarketSignals(**kwargs)


def make_impacts_all_positive():
    return {
        "sentiment": {"contribution_percent": 3.0},
        "competitor": {"contribution_percent": 2.0},
        "total_contribution_percent": 5.0,
    }


def make_impacts_all_negative():
    return {
        "sentiment": {"contribution_percent": -3.0},
        "competitor": {"contribution_percent": -2.0},
        "total_contribution_percent": -5.0,
    }


def make_impacts_mixed():
    return {
        "sentiment": {"contribution_percent": 3.0},
        "competitor": {"contribution_percent": -2.0},
        "total_contribution_percent": 1.0,
    }


# ============================================================
# 1. Initialization
# ============================================================


class TestConfidenceCalculatorInit:
    def test_init_without_db(self):
        calc = ConfidenceCalculator()
        assert calc.db is None

    def test_init_with_db(self):
        db = MagicMock()
        calc = ConfidenceCalculator(db=db)
        assert calc.db is db

    def test_class_constants(self):
        assert ConfidenceCalculator.MIN_MENTIONS_FOR_HIGH_CONFIDENCE == 100
        assert ConfidenceCalculator.MIN_MENTIONS_FOR_MEDIUM_CONFIDENCE == 25
        assert ConfidenceCalculator.LOW_VOLATILITY_THRESHOLD == Decimal("0.05")
        assert ConfidenceCalculator.HIGH_VOLATILITY_THRESHOLD == Decimal("0.15")


# ============================================================
# 2. _score_data_quality
# ============================================================


class TestScoreDataQuality:
    def setup_method(self):
        self.calc = ConfidenceCalculator()

    def test_zero_data(self):
        signals = make_signals()
        score = self.calc._score_data_quality(signals)
        assert score == Decimal("0.0")

    def test_high_mentions(self):
        signals = make_signals(mention_count_24h=100)
        score = self.calc._score_data_quality(signals)
        assert score >= Decimal("0.4")

    def test_medium_mentions(self):
        signals = make_signals(mention_count_24h=50)
        score = self.calc._score_data_quality(signals)
        assert Decimal("0.25") <= score <= Decimal("1.0")

    def test_low_mentions(self):
        signals = make_signals(mention_count_24h=5)
        score = self.calc._score_data_quality(signals)
        assert score >= Decimal("0.1")

    def test_sentiment_score_present(self):
        signals = make_signals(sentiment_score=Decimal("0.5"))
        score = self.calc._score_data_quality(signals)
        assert score >= Decimal("0.2")

    def test_sentiment_with_change(self):
        signals = make_signals(
            sentiment_score=Decimal("0.5"),
            sentiment_change_24h=Decimal("0.1"),
        )
        score = self.calc._score_data_quality(signals)
        assert score >= Decimal("0.3")  # 0.2 + 0.1

    def test_one_competitor(self):
        signals = make_signals(competitor_prices={COMP_A: Decimal("99")})
        score = self.calc._score_data_quality(signals)
        assert score >= Decimal("0.2")

    def test_three_plus_competitors(self):
        signals = make_signals(
            competitor_prices={
                COMP_A: Decimal("99"),
                COMP_B: Decimal("95"),
                COMP_C: Decimal("105"),
            }
        )
        score = self.calc._score_data_quality(signals)
        assert score >= Decimal("0.3")

    def test_all_data_present(self):
        signals = make_signals(
            mention_count_24h=200,
            sentiment_score=Decimal("0.8"),
            sentiment_change_24h=Decimal("0.2"),
            competitor_prices={
                COMP_A: Decimal("99"),
                COMP_B: Decimal("95"),
                COMP_C: Decimal("105"),
            },
        )
        score = self.calc._score_data_quality(signals)
        # 0.4 + 0.2 + 0.1 + 0.3 = 1.0
        assert score == Decimal("1.0")

    def test_capped_at_one(self):
        """Even with max data, score shouldn't exceed 1.0."""
        signals = make_signals(
            mention_count_24h=1000,
            sentiment_score=Decimal("0.9"),
            sentiment_change_24h=Decimal("0.5"),
            competitor_prices={
                COMP_A: Decimal("99"),
                COMP_B: Decimal("95"),
                COMP_C: Decimal("105"),
            },
        )
        score = self.calc._score_data_quality(signals)
        assert score <= Decimal("1.0")

    def test_mention_boundary_25(self):
        score_24 = self.calc._score_data_quality(make_signals(mention_count_24h=24))
        score_25 = self.calc._score_data_quality(make_signals(mention_count_24h=25))
        assert score_25 > score_24

    def test_mention_boundary_100(self):
        score_99 = self.calc._score_data_quality(make_signals(mention_count_24h=99))
        score_100 = self.calc._score_data_quality(make_signals(mention_count_24h=100))
        assert score_100 > score_99


# ============================================================
# 3. _score_signal_agreement
# ============================================================


class TestScoreSignalAgreement:
    def setup_method(self):
        self.calc = ConfidenceCalculator()

    def test_all_positive(self):
        score = self.calc._score_signal_agreement(make_impacts_all_positive())
        assert score == Decimal("1.0")

    def test_all_negative(self):
        score = self.calc._score_signal_agreement(make_impacts_all_negative())
        assert score == Decimal("1.0")

    def test_mixed_signals(self):
        score = self.calc._score_signal_agreement(make_impacts_mixed())
        assert score < Decimal("1.0")

    def test_empty_impacts(self):
        score = self.calc._score_signal_agreement({})
        assert score == Decimal("0.5")

    def test_only_total_key(self):
        """total_contribution_percent is skipped."""
        score = self.calc._score_signal_agreement({"total_contribution_percent": 5.0})
        assert score == Decimal("0.5")

    def test_three_positive_one_negative(self):
        impacts = {
            "a": {"contribution_percent": 3.0},
            "b": {"contribution_percent": 2.0},
            "c": {"contribution_percent": 1.0},
            "d": {"contribution_percent": -1.0},
        }
        score = self.calc._score_signal_agreement(impacts)
        # 3/4 = 0.75 → score 0.8
        assert score == Decimal("0.8")

    def test_two_positive_two_negative(self):
        impacts = {
            "a": {"contribution_percent": 3.0},
            "b": {"contribution_percent": 2.0},
            "c": {"contribution_percent": -3.0},
            "d": {"contribution_percent": -2.0},
        }
        score = self.calc._score_signal_agreement(impacts)
        # 2/4 = 0.50 → score 0.6
        assert score == Decimal("0.6")

    def test_one_positive_three_negative(self):
        impacts = {
            "a": {"contribution_percent": 1.0},
            "b": {"contribution_percent": -3.0},
            "c": {"contribution_percent": -2.0},
            "d": {"contribution_percent": -1.0},
        }
        score = self.calc._score_signal_agreement(impacts)
        # 3/4 = 0.75 → score 0.8
        assert score == Decimal("0.8")

    def test_non_dict_impact_skipped(self):
        """Entries that aren't dicts with contribution_percent are skipped."""
        impacts = {
            "a": {"contribution_percent": 3.0},
            "b": "not a dict",
            "c": {"no_contribution": True},
        }
        score = self.calc._score_signal_agreement(impacts)
        # Only 1 contribution → all positive → 1.0
        assert score == Decimal("1.0")

    def test_zero_contributions_treated_as_neutral(self):
        impacts = {
            "a": {"contribution_percent": 0},
            "b": {"contribution_percent": 0},
        }
        score = self.calc._score_signal_agreement(impacts)
        # 0 positive, 0 negative → majority=0, total=2, ratio=0 → 0.3
        assert score == Decimal("0.3")


# ============================================================
# 4. _score_rule_confidence
# ============================================================


class TestScoreRuleConfidence:
    def setup_method(self):
        self.calc = ConfidenceCalculator()

    def test_no_rule_type(self):
        signals = make_signals()
        assert self.calc._score_rule_confidence(None, signals) == Decimal("0.5")

    def test_sentiment_high_mentions(self):
        signals = make_signals(mention_count_24h=200)
        score = self.calc._score_rule_confidence("sentiment_threshold", signals)
        assert score == Decimal("0.9")

    def test_sentiment_medium_mentions(self):
        signals = make_signals(mention_count_24h=50)
        score = self.calc._score_rule_confidence("sentiment_threshold", signals)
        assert score == Decimal("0.7")

    def test_sentiment_low_mentions(self):
        signals = make_signals(mention_count_24h=5)
        score = self.calc._score_rule_confidence("sentiment_threshold", signals)
        assert score == Decimal("0.5")

    def test_competitor_with_prices(self):
        signals = make_signals(competitor_prices={COMP_A: Decimal("99")})
        score = self.calc._score_rule_confidence("competitor_relative", signals)
        assert score == Decimal("0.95")

    def test_competitor_without_prices(self):
        signals = make_signals()
        score = self.calc._score_rule_confidence("competitor_relative", signals)
        assert score == Decimal("0.3")

    def test_time_based_always_high(self):
        signals = make_signals()
        score = self.calc._score_rule_confidence("time_based", signals)
        assert score == Decimal("1.0")

    def test_volume_surge_high_ratio(self):
        signals = make_signals(mention_count_24h=400, mention_baseline=100)
        score = self.calc._score_rule_confidence("volume_surge", signals)
        assert score == Decimal("0.9")

    def test_volume_surge_medium_ratio(self):
        signals = make_signals(mention_count_24h=250, mention_baseline=100)
        score = self.calc._score_rule_confidence("volume_surge", signals)
        assert score == Decimal("0.75")

    def test_volume_surge_low_ratio(self):
        signals = make_signals(mention_count_24h=150, mention_baseline=100)
        score = self.calc._score_rule_confidence("volume_surge", signals)
        assert score == Decimal("0.6")

    def test_volume_surge_zero_baseline(self):
        signals = make_signals(mention_count_24h=100, mention_baseline=0)
        score = self.calc._score_rule_confidence("volume_surge", signals)
        assert score == Decimal("0.5")

    def test_viral_high_reach(self):
        signals = make_signals(viral_reach=200000)
        score = self.calc._score_rule_confidence("viral_detection", signals)
        assert score == Decimal("0.9")

    def test_viral_medium_reach(self):
        signals = make_signals(viral_reach=75000)
        score = self.calc._score_rule_confidence("viral_detection", signals)
        assert score == Decimal("0.75")

    def test_viral_low_reach(self):
        signals = make_signals(viral_reach=10000)
        score = self.calc._score_rule_confidence("viral_detection", signals)
        assert score == Decimal("0.6")

    def test_unknown_rule_type(self):
        signals = make_signals()
        score = self.calc._score_rule_confidence("unknown_type", signals)
        assert score == Decimal("0.5")


# ============================================================
# 5. _score_historical_accuracy
# ============================================================


class TestScoreHistoricalAccuracy:
    def test_no_db_returns_default(self):
        calc = ConfidenceCalculator(db=None)
        score = calc._score_historical_accuracy("sentiment_threshold", USER_ID)
        assert score == Decimal("0.5")

    def test_no_rule_type_returns_default(self):
        calc = ConfidenceCalculator(db=MagicMock())
        score = calc._score_historical_accuracy(None, USER_ID)
        assert score == Decimal("0.5")

    def test_no_user_id_returns_default(self):
        calc = ConfidenceCalculator(db=MagicMock())
        score = calc._score_historical_accuracy("sentiment_threshold", None)
        assert score == Decimal("0.5")

    @patch("services.pricing.outcome_service.OutcomeService")
    def test_delegates_to_outcome_service(self, MockOS):
        mock_instance = MagicMock()
        mock_instance.get_historical_accuracy_for_rule_type.return_value = Decimal("0.85")
        MockOS.return_value = mock_instance

        db = MagicMock()
        calc = ConfidenceCalculator(db=db)
        score = calc._score_historical_accuracy("sentiment_threshold", USER_ID)
        assert score == Decimal("0.85")


# ============================================================
# 6. _score_market_stability
# ============================================================


class TestScoreMarketStability:
    def test_no_db_returns_default(self):
        calc = ConfidenceCalculator(db=None)
        score = calc._score_market_stability(PRODUCT_ID)
        assert score == Decimal("0.5")

    def test_no_product_id_returns_default(self):
        calc = ConfidenceCalculator(db=MagicMock())
        score = calc._score_market_stability(None)
        assert score == Decimal("0.5")

    def test_low_volatility_high_stability(self):
        calc = ConfidenceCalculator(db=MagicMock())
        calc._calculate_price_volatility = MagicMock(return_value=Decimal("0.02"))
        calc._calculate_sentiment_volatility = MagicMock(return_value=Decimal("0.01"))
        score = calc._score_market_stability(PRODUCT_ID)
        # combined = 0.02*0.6 + 0.01*0.4 = 0.016 < 0.05 → 1.0
        assert score == Decimal("1.0")

    def test_high_volatility_low_stability(self):
        calc = ConfidenceCalculator(db=MagicMock())
        calc._calculate_price_volatility = MagicMock(return_value=Decimal("0.20"))
        calc._calculate_sentiment_volatility = MagicMock(return_value=Decimal("0.15"))
        score = calc._score_market_stability(PRODUCT_ID)
        # combined = 0.20*0.6 + 0.15*0.4 = 0.12+0.06 = 0.18 > 0.15 → 0.3
        assert score == Decimal("0.3")

    def test_mid_volatility_interpolated(self):
        calc = ConfidenceCalculator(db=MagicMock())
        calc._calculate_price_volatility = MagicMock(return_value=Decimal("0.10"))
        calc._calculate_sentiment_volatility = MagicMock(return_value=Decimal("0.05"))
        score = calc._score_market_stability(PRODUCT_ID)
        # combined = 0.10*0.6 + 0.05*0.4 = 0.06+0.02 = 0.08
        # in range [0.05, 0.15], position = (0.08-0.05)/0.10 = 0.3
        # score = 1.0 - 0.3*0.7 = 1.0 - 0.21 = 0.79
        assert Decimal("0.3") < score < Decimal("1.0")

    def test_exactly_at_low_threshold(self):
        calc = ConfidenceCalculator(db=MagicMock())
        calc._calculate_price_volatility = MagicMock(return_value=Decimal("0.05"))
        calc._calculate_sentiment_volatility = MagicMock(return_value=Decimal("0.05"))
        score = calc._score_market_stability(PRODUCT_ID)
        # combined = 0.05*0.6 + 0.05*0.4 = 0.05 → exactly at low → 1.0
        assert score == Decimal("1.0")

    def test_exactly_at_high_threshold(self):
        calc = ConfidenceCalculator(db=MagicMock())
        calc._calculate_price_volatility = MagicMock(return_value=Decimal("0.15"))
        calc._calculate_sentiment_volatility = MagicMock(return_value=Decimal("0.15"))
        score = calc._score_market_stability(PRODUCT_ID)
        # combined = 0.15*0.6 + 0.15*0.4 = 0.15 → exactly at high → 0.3
        assert score == Decimal("0.3")


# ============================================================
# 7. _calculate_price_volatility
# ============================================================


class TestCalculatePriceVolatility:
    @patch(f"{SERVICE_PATH}.select")
    def test_insufficient_data_returns_stable(self, mock_select):
        mock_select.return_value.where.return_value.order_by.return_value = MagicMock()
        db = MagicMock()
        db.exec.return_value.all.return_value = [MagicMock(), MagicMock()]  # Only 2 < 3
        calc = ConfidenceCalculator(db=db)
        result = calc._calculate_price_volatility(PRODUCT_ID)
        assert result == Decimal("0.05")

    @patch(f"{SERVICE_PATH}.select")
    def test_zero_mean_returns_stable(self, mock_select):
        mock_select.return_value.where.return_value.order_by.return_value = MagicMock()
        db = MagicMock()
        history = [MagicMock(new_price=Decimal("0")) for _ in range(5)]
        db.exec.return_value.all.return_value = history
        calc = ConfidenceCalculator(db=db)
        result = calc._calculate_price_volatility(PRODUCT_ID)
        assert result == Decimal("0.05")

    @patch(f"{SERVICE_PATH}.select")
    def test_stable_prices_low_volatility(self, mock_select):
        mock_select.return_value.where.return_value.order_by.return_value = MagicMock()
        db = MagicMock()
        history = [MagicMock(new_price=Decimal("100.00")) for _ in range(10)]
        db.exec.return_value.all.return_value = history
        calc = ConfidenceCalculator(db=db)
        result = calc._calculate_price_volatility(PRODUCT_ID)
        assert result == Decimal("0.00")

    @patch(f"{SERVICE_PATH}.select")
    def test_volatile_prices_high_volatility(self, mock_select):
        mock_select.return_value.where.return_value.order_by.return_value = MagicMock()
        db = MagicMock()
        prices = [Decimal("50"), Decimal("150"), Decimal("50"), Decimal("150"), Decimal("50")]
        history = [MagicMock(new_price=p) for p in prices]
        db.exec.return_value.all.return_value = history
        calc = ConfidenceCalculator(db=db)
        result = calc._calculate_price_volatility(PRODUCT_ID)
        assert result > Decimal("0.10")

    @patch(f"{SERVICE_PATH}.select")
    def test_capped_at_050(self, mock_select):
        mock_select.return_value.where.return_value.order_by.return_value = MagicMock()
        db = MagicMock()
        prices = [Decimal("1"), Decimal("1000"), Decimal("1"), Decimal("1000"), Decimal("1")]
        history = [MagicMock(new_price=p) for p in prices]
        db.exec.return_value.all.return_value = history
        calc = ConfidenceCalculator(db=db)
        result = calc._calculate_price_volatility(PRODUCT_ID)
        assert result <= Decimal("0.50")


# ============================================================
# 8. _calculate_sentiment_volatility
# ============================================================


class TestCalculateSentimentVolatility:
    @patch(f"{SERVICE_PATH}.select")
    def test_insufficient_data_returns_stable(self, mock_select):
        mock_select.return_value.where.return_value.order_by.return_value.limit.return_value = MagicMock()
        db = MagicMock()
        db.exec.return_value.all.return_value = [MagicMock() for _ in range(3)]  # Only 3 < 5
        calc = ConfidenceCalculator(db=db)
        result = calc._calculate_sentiment_volatility(PRODUCT_ID)
        assert result == Decimal("0.05")

    @patch(f"{SERVICE_PATH}.select")
    def test_stable_sentiment_low_volatility(self, mock_select):
        mock_select.return_value.where.return_value.order_by.return_value.limit.return_value = MagicMock()
        db = MagicMock()
        sentiments = [MagicMock(compound_score=Decimal("0.5")) for _ in range(10)]
        db.exec.return_value.all.return_value = sentiments
        calc = ConfidenceCalculator(db=db)
        result = calc._calculate_sentiment_volatility(PRODUCT_ID)
        assert result == Decimal("0.00")

    @patch(f"{SERVICE_PATH}.select")
    def test_volatile_sentiment_high_volatility(self, mock_select):
        mock_select.return_value.where.return_value.order_by.return_value.limit.return_value = MagicMock()
        db = MagicMock()
        scores = [Decimal("-1"), Decimal("1"), Decimal("-1"), Decimal("1"), Decimal("-1")]
        sentiments = [MagicMock(compound_score=s) for s in scores]
        db.exec.return_value.all.return_value = sentiments
        calc = ConfidenceCalculator(db=db)
        result = calc._calculate_sentiment_volatility(PRODUCT_ID)
        assert result > Decimal("0.10")

    @patch(f"{SERVICE_PATH}.select")
    def test_capped_at_050(self, mock_select):
        mock_select.return_value.where.return_value.order_by.return_value.limit.return_value = MagicMock()
        db = MagicMock()
        scores = [Decimal("-1"), Decimal("1"), Decimal("-1"), Decimal("1"), Decimal("-1"), Decimal("1")]
        sentiments = [MagicMock(compound_score=s) for s in scores]
        db.exec.return_value.all.return_value = sentiments
        calc = ConfidenceCalculator(db=db)
        result = calc._calculate_sentiment_volatility(PRODUCT_ID)
        assert result <= Decimal("0.50")


# ============================================================
# 9. calculate() — Overall Pipeline
# ============================================================


class TestCalculateOverall:
    def test_returns_decimal(self):
        calc = ConfidenceCalculator()
        signals = make_signals()
        result = calc.calculate(signals, {})
        assert isinstance(result, Decimal)

    def test_rounded_to_two_decimals(self):
        calc = ConfidenceCalculator()
        signals = make_signals()
        result = calc.calculate(signals, {})
        assert result == result.quantize(Decimal("0.01"))

    def test_clamped_between_0_and_1(self):
        calc = ConfidenceCalculator()
        signals = make_signals()
        result = calc.calculate(signals, {})
        assert Decimal("0.0") <= result <= Decimal("1.0")

    def test_high_data_high_confidence(self):
        calc = ConfidenceCalculator()
        signals = make_signals(
            mention_count_24h=200,
            sentiment_score=Decimal("0.8"),
            sentiment_change_24h=Decimal("0.2"),
            competitor_prices={COMP_A: Decimal("99"), COMP_B: Decimal("95"), COMP_C: Decimal("105")},
        )
        impacts = make_impacts_all_positive()
        result = calc.calculate(signals, impacts, "sentiment_threshold")
        assert result > Decimal("0.5")

    def test_no_data_low_confidence(self):
        calc = ConfidenceCalculator()
        signals = make_signals()
        result = calc.calculate(signals, {})
        assert result <= Decimal("0.5")

    def test_weighted_formula(self):
        """Verify the 5-factor weighted average."""
        calc = ConfidenceCalculator()
        calc._score_data_quality = MagicMock(return_value=Decimal("1.0"))
        calc._score_signal_agreement = MagicMock(return_value=Decimal("1.0"))
        calc._score_rule_confidence = MagicMock(return_value=Decimal("1.0"))
        calc._score_historical_accuracy = MagicMock(return_value=Decimal("1.0"))
        calc._score_market_stability = MagicMock(return_value=Decimal("1.0"))

        result = calc.calculate(make_signals(), {})
        # All 1.0 × weights sum = 1.0
        assert result == Decimal("1.00")

    def test_weights_sum_to_one(self):
        """0.25 + 0.25 + 0.15 + 0.15 + 0.20 = 1.00."""
        total = Decimal("0.25") + Decimal("0.25") + Decimal("0.15") + Decimal("0.15") + Decimal("0.20")
        assert total == Decimal("1.00")

    def test_all_zeros_gives_zero(self):
        calc = ConfidenceCalculator()
        calc._score_data_quality = MagicMock(return_value=Decimal("0.0"))
        calc._score_signal_agreement = MagicMock(return_value=Decimal("0.0"))
        calc._score_rule_confidence = MagicMock(return_value=Decimal("0.0"))
        calc._score_historical_accuracy = MagicMock(return_value=Decimal("0.0"))
        calc._score_market_stability = MagicMock(return_value=Decimal("0.0"))

        result = calc.calculate(make_signals(), {})
        assert result == Decimal("0.00")


# ============================================================
# 10. get_confidence_breakdown
# ============================================================


class TestGetConfidenceBreakdown:
    def test_returns_dict(self):
        calc = ConfidenceCalculator()
        signals = make_signals()
        result = calc.get_confidence_breakdown(signals, {})
        assert isinstance(result, dict)

    def test_has_overall_key(self):
        calc = ConfidenceCalculator()
        result = calc.get_confidence_breakdown(make_signals(), {})
        assert "overall" in result

    def test_has_components_key(self):
        calc = ConfidenceCalculator()
        result = calc.get_confidence_breakdown(make_signals(), {})
        assert "components" in result

    def test_components_has_all_five_factors(self):
        calc = ConfidenceCalculator()
        result = calc.get_confidence_breakdown(make_signals(), {})
        components = result["components"]
        expected = {
            "data_quality",
            "signal_agreement",
            "rule_confidence",
            "historical_accuracy",
            "market_stability",
        }
        assert set(components.keys()) == expected

    def test_each_component_has_score_and_weight(self):
        calc = ConfidenceCalculator()
        result = calc.get_confidence_breakdown(make_signals(), {})
        for key, comp in result["components"].items():
            assert "score" in comp
            assert "weight" in comp

    def test_data_quality_has_factors(self):
        calc = ConfidenceCalculator()
        signals = make_signals(
            mention_count_24h=50,
            sentiment_score=Decimal("0.5"),
            competitor_prices={COMP_A: Decimal("99")},
        )
        result = calc.get_confidence_breakdown(signals, {})
        factors = result["components"]["data_quality"]["factors"]
        assert factors["mention_count_24h"] == 50
        assert factors["has_sentiment"] is True
        assert factors["competitor_count"] == 1

    def test_rule_confidence_includes_rule_type(self):
        calc = ConfidenceCalculator()
        result = calc.get_confidence_breakdown(make_signals(), {}, triggered_rule_type="sentiment_threshold")
        assert result["components"]["rule_confidence"]["rule_type"] == "sentiment_threshold"

    def test_volatility_none_without_db(self):
        calc = ConfidenceCalculator(db=None)
        result = calc.get_confidence_breakdown(make_signals(), {}, product_id=PRODUCT_ID)
        assert result["components"]["market_stability"]["price_volatility"] is None
        assert result["components"]["market_stability"]["sentiment_volatility"] is None

    def test_volatility_present_with_db(self):
        db = MagicMock()
        calc = ConfidenceCalculator(db=db)
        calc._calculate_price_volatility = MagicMock(return_value=Decimal("0.08"))
        calc._calculate_sentiment_volatility = MagicMock(return_value=Decimal("0.04"))

        result = calc.get_confidence_breakdown(make_signals(), {}, product_id=PRODUCT_ID)
        assert result["components"]["market_stability"]["price_volatility"] == 0.08
        assert result["components"]["market_stability"]["sentiment_volatility"] == 0.04

    def test_overall_matches_calculate(self):
        calc = ConfidenceCalculator()
        signals = make_signals(mention_count_24h=50, sentiment_score=Decimal("0.5"))
        impacts = make_impacts_all_positive()
        breakdown = calc.get_confidence_breakdown(signals, impacts)
        direct = calc.calculate(signals, impacts)
        assert abs(breakdown["overall"] - float(direct)) < 0.01
