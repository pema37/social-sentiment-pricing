# backend/tests/test_rule_evaluator.py
"""
Comprehensive tests for RuleEvaluator — evaluates pricing rules against market signals.

Tests cover:
- MarketSignals dataclass (defaults, custom values)
- RuleEvaluator initialization
- _rule_applies_to_product (4 scoping conditions)
- _eval_sentiment_threshold (above/below directions, missing data)
- _eval_competitor_relative (UUID match, name-based match, lowest price fallback)
- _match_competitor_by_name (DB lookup, normalization, not found)
- _eval_time_based (day of week, time range)
- _eval_volume_surge (surge ratio, zero baseline)
- _eval_viral_detection (reach, engagement, sentiment checks)
- _evaluate_rule (routing to correct evaluator)
- find_matching_rule (cooldown, priority ordering)
- get_active_rules (DB query + filtering)

Total: ~95 tests
"""

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
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

import pytest

# Import after isolation
from services.pricing.rule_evaluator import (
    MarketSignals,
    RuleEvaluator,
)

SERVICE_PATH = "services.pricing.rule_evaluator"


# ============================================================
# Helpers
# ============================================================

PRODUCT_ID = uuid4()
USER_ID = uuid4()
COMP_ID_A = uuid4()
COMP_ID_B = uuid4()
RULE_ID = uuid4()


def make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


def make_signals(**kwargs):
    """Create a MarketSignals with overrides."""
    return MarketSignals(**kwargs)


def make_rule(
    rule_type=None,
    is_active=True,
    priority=1,
    product_id=None,
    applies_to_all_products=False,
    applies_to_products=None,
    applies_to_categories=None,
    sentiment_threshold=None,
    sentiment_direction="above",
    competitor_id=None,
    competitor_margin_percent=None,
    price_position=None,
    cooldown_hours=1,
    last_triggered_at=None,
    time_days=None,
    time_start=None,
    time_end=None,
    volume_threshold=None,
    viral_threshold_reach=None,
    viral_threshold_engagement=None,
    viral_sentiment_min=None,
):
    rule = MagicMock()
    rule.id = RULE_ID
    rule.rule_type = rule_type
    rule.is_active = is_active
    rule.priority = priority
    rule.product_id = product_id
    rule.applies_to_all_products = applies_to_all_products
    rule.applies_to_products = applies_to_products
    rule.applies_to_categories = applies_to_categories
    rule.sentiment_threshold = sentiment_threshold
    rule.sentiment_direction = sentiment_direction
    rule.competitor_id = competitor_id
    rule.competitor_margin_percent = competitor_margin_percent
    rule.price_position = price_position
    rule.cooldown_hours = cooldown_hours
    rule.last_triggered_at = last_triggered_at
    rule.time_days = time_days
    rule.time_start = time_start
    rule.time_end = time_end
    rule.volume_threshold = volume_threshold
    rule.viral_threshold_reach = viral_threshold_reach
    rule.viral_threshold_engagement = viral_threshold_engagement
    rule.viral_sentiment_min = viral_sentiment_min
    return rule


def make_product(id=None, category=None):
    product = MagicMock()
    product.id = id or PRODUCT_ID
    product.category = category
    return product


# We need the actual RuleType enum — import it from the mock or define stand-ins
# Since models.pricing_rule is mocked, we need to get the real RuleType
# The source imports RuleType from models.pricing_rule
# We'll import it fresh to get the actual enum
try:
    from models.pricing_rule import RuleType as _RT

    # If models are real, use them
    SENTIMENT_THRESHOLD = _RT.SENTIMENT_THRESHOLD
    COMPETITOR_RELATIVE = _RT.COMPETITOR_RELATIVE
    TIME_BASED = _RT.TIME_BASED
    VOLUME_SURGE = _RT.VOLUME_SURGE
    VIRAL_DETECTION = _RT.VIRAL_DETECTION
except (ImportError, AttributeError):
    # Models are mocked — create stand-in enums
    class _FakeRuleType:
        def __init__(self, val):
            self.value = val

        def __eq__(self, other):
            if hasattr(other, "value"):
                return self.value == other.value
            return self.value == other

        def __hash__(self):
            return hash(self.value)

    SENTIMENT_THRESHOLD = _FakeRuleType("sentiment_threshold")
    COMPETITOR_RELATIVE = _FakeRuleType("competitor_relative")
    TIME_BASED = _FakeRuleType("time_based")
    VOLUME_SURGE = _FakeRuleType("volume_surge")
    VIRAL_DETECTION = _FakeRuleType("viral_detection")

# Patch into the module's namespace so comparisons work
RuleType = MagicMock()
RuleType.SENTIMENT_THRESHOLD = SENTIMENT_THRESHOLD
RuleType.COMPETITOR_RELATIVE = COMPETITOR_RELATIVE
RuleType.TIME_BASED = TIME_BASED
RuleType.VOLUME_SURGE = VOLUME_SURGE
RuleType.VIRAL_DETECTION = VIRAL_DETECTION


# ============================================================
# 1. MarketSignals Dataclass
# ============================================================


class TestMarketSignals:
    def test_default_values(self):
        s = MarketSignals()
        assert s.sentiment_score is None
        assert s.sentiment_change_24h is None
        assert s.mention_count_24h == 0
        assert s.mention_baseline == 0
        assert s.viral_detected is False
        assert s.viral_reach == 0
        assert s.viral_engagement == 0
        assert s.viral_sentiment is None
        assert s.competitor_prices == {}
        assert s.trend_direction is None
        assert s.trend_strength == Decimal("0")
        assert s.is_trending is False

    def test_custom_sentiment(self):
        s = MarketSignals(sentiment_score=Decimal("0.75"), sentiment_change_24h=Decimal("0.1"))
        assert s.sentiment_score == Decimal("0.75")
        assert s.sentiment_change_24h == Decimal("0.1")

    def test_custom_competitor_prices(self):
        prices = {COMP_ID_A: Decimal("99.99"), COMP_ID_B: Decimal("89.99")}
        s = MarketSignals(competitor_prices=prices)
        assert len(s.competitor_prices) == 2
        assert s.competitor_prices[COMP_ID_A] == Decimal("99.99")

    def test_viral_signals(self):
        s = MarketSignals(
            viral_detected=True,
            viral_reach=50000,
            viral_engagement=5000,
            viral_sentiment=Decimal("0.8"),
        )
        assert s.viral_detected is True
        assert s.viral_reach == 50000

    def test_trend_signals(self):
        s = MarketSignals(
            trend_direction="up",
            trend_strength=Decimal("0.7"),
            is_trending=True,
        )
        assert s.trend_direction == "up"
        assert s.is_trending is True

    def test_volume_signals(self):
        s = MarketSignals(mention_count_24h=500, mention_baseline=100)
        assert s.mention_count_24h == 500
        assert s.mention_baseline == 100


# ============================================================
# 2. RuleEvaluator Init
# ============================================================


class TestRuleEvaluatorInit:
    def test_stores_db(self):
        db = make_mock_db()
        evaluator = RuleEvaluator(db)
        assert evaluator.db is db


# ============================================================
# 3. _rule_applies_to_product
# ============================================================


class TestRuleAppliesToProduct:
    def setup_method(self):
        self.evaluator = RuleEvaluator(make_mock_db())

    def test_applies_to_all_products(self):
        rule = make_rule(applies_to_all_products=True)
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), None) is True

    def test_legacy_product_id_match(self):
        rule = make_rule(product_id=PRODUCT_ID)
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), None) is True

    def test_legacy_product_id_no_match(self):
        other_id = uuid4()
        rule = make_rule(product_id=other_id)
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), None) is False

    def test_applies_to_products_list_match(self):
        rule = make_rule(applies_to_products=[str(PRODUCT_ID), str(uuid4())])
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), None) is True

    def test_applies_to_products_list_no_match(self):
        rule = make_rule(applies_to_products=[str(uuid4())])
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), None) is False

    def test_applies_to_categories_match(self):
        rule = make_rule(applies_to_categories=["electronics", "gadgets"])
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), "electronics") is True

    def test_applies_to_categories_no_match(self):
        rule = make_rule(applies_to_categories=["clothing"])
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), "electronics") is False

    def test_applies_to_categories_no_product_category(self):
        """If product has no category, category-based rules don't match."""
        rule = make_rule(applies_to_categories=["electronics"])
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), None) is False

    def test_no_scoping_at_all_returns_false(self):
        """Rule with no scoping doesn't match anything."""
        rule = make_rule(
            applies_to_all_products=False,
            product_id=None,
            applies_to_products=None,
            applies_to_categories=None,
        )
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), "electronics") is False

    def test_priority_all_products_wins(self):
        """applies_to_all_products is checked first, short-circuits."""
        rule = make_rule(
            applies_to_all_products=True,
            product_id=uuid4(),  # different product
        )
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), None) is True

    def test_empty_products_list(self):
        rule = make_rule(applies_to_products=[])
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), None) is False

    def test_empty_categories_list(self):
        rule = make_rule(applies_to_categories=[])
        assert self.evaluator._rule_applies_to_product(rule, PRODUCT_ID, str(PRODUCT_ID), "electronics") is False


# ============================================================
# 4. _eval_sentiment_threshold
# ============================================================


class TestEvalSentimentThreshold:
    def setup_method(self):
        self.evaluator = RuleEvaluator(make_mock_db())

    def test_above_triggered(self):
        rule = make_rule(
            sentiment_threshold=Decimal("0.5"),
            sentiment_direction="above",
        )
        signals = make_signals(sentiment_score=Decimal("0.7"))
        result = self.evaluator._eval_sentiment_threshold(rule, signals)
        assert result is not None
        assert result["rule_type"] == "sentiment_threshold"
        assert result["direction"] == "above"

    def test_above_not_triggered(self):
        rule = make_rule(
            sentiment_threshold=Decimal("0.5"),
            sentiment_direction="above",
        )
        signals = make_signals(sentiment_score=Decimal("0.3"))
        assert self.evaluator._eval_sentiment_threshold(rule, signals) is None

    def test_above_at_boundary(self):
        rule = make_rule(
            sentiment_threshold=Decimal("0.5"),
            sentiment_direction="above",
        )
        signals = make_signals(sentiment_score=Decimal("0.5"))
        result = self.evaluator._eval_sentiment_threshold(rule, signals)
        assert result is not None  # >= threshold

    def test_below_triggered(self):
        rule = make_rule(
            sentiment_threshold=Decimal("-0.3"),
            sentiment_direction="below",
        )
        signals = make_signals(sentiment_score=Decimal("-0.5"))
        result = self.evaluator._eval_sentiment_threshold(rule, signals)
        assert result is not None
        assert result["direction"] == "below"

    def test_below_not_triggered(self):
        rule = make_rule(
            sentiment_threshold=Decimal("-0.3"),
            sentiment_direction="below",
        )
        signals = make_signals(sentiment_score=Decimal("0.1"))
        assert self.evaluator._eval_sentiment_threshold(rule, signals) is None

    def test_below_at_boundary(self):
        rule = make_rule(
            sentiment_threshold=Decimal("-0.3"),
            sentiment_direction="below",
        )
        signals = make_signals(sentiment_score=Decimal("-0.3"))
        result = self.evaluator._eval_sentiment_threshold(rule, signals)
        assert result is not None  # <= threshold

    def test_no_sentiment_score_returns_none(self):
        rule = make_rule(sentiment_threshold=Decimal("0.5"))
        signals = make_signals(sentiment_score=None)
        assert self.evaluator._eval_sentiment_threshold(rule, signals) is None

    def test_no_threshold_returns_none(self):
        rule = make_rule(sentiment_threshold=None)
        signals = make_signals(sentiment_score=Decimal("0.8"))
        assert self.evaluator._eval_sentiment_threshold(rule, signals) is None

    def test_default_direction_is_above(self):
        rule = make_rule(
            sentiment_threshold=Decimal("0.5"),
            sentiment_direction=None,
        )
        signals = make_signals(sentiment_score=Decimal("0.7"))
        result = self.evaluator._eval_sentiment_threshold(rule, signals)
        assert result is not None
        assert result["direction"] == "above"

    def test_result_contains_correct_values(self):
        rule = make_rule(
            sentiment_threshold=Decimal("0.3"),
            sentiment_direction="above",
        )
        signals = make_signals(sentiment_score=Decimal("0.75"))
        result = self.evaluator._eval_sentiment_threshold(rule, signals)
        assert result["sentiment_score"] == 0.75
        assert result["threshold"] == 0.3


# ============================================================
# 5. _eval_competitor_relative
# ============================================================


class TestEvalCompetitorRelative:
    def setup_method(self):
        self.evaluator = RuleEvaluator(make_mock_db())

    @pytest.mark.asyncio
    async def test_uuid_match(self):
        rule = make_rule(
            competitor_id=COMP_ID_A,
            competitor_margin_percent=Decimal("5"),
            price_position="below",
        )
        signals = make_signals(competitor_prices={COMP_ID_A: Decimal("99.99")})
        result = await self.evaluator._eval_competitor_relative(rule, signals)
        assert result is not None
        assert result["competitor_price"] == 99.99
        assert result["rule_type"] == "competitor_relative"

    @pytest.mark.asyncio
    async def test_uuid_no_match_tries_name(self):
        """When UUID doesn't match, falls back to name-based matching."""
        rule = make_rule(competitor_id=COMP_ID_A)
        signals = make_signals(competitor_prices={COMP_ID_B: Decimal("89.99")})
        # Mock name-based match to return a result
        self.evaluator._match_competitor_by_name = AsyncMock(
            return_value={
                "competitor_id": COMP_ID_B,
                "price": Decimal("89.99"),
                "name": "Amazon",
            }
        )
        result = await self.evaluator._eval_competitor_relative(rule, signals)
        assert result is not None
        assert result["matched_by"] == "name"
        assert result["competitor_price"] == 89.99

    @pytest.mark.asyncio
    async def test_uuid_no_match_name_no_match(self):
        """When neither UUID nor name matches, returns None."""
        rule = make_rule(competitor_id=COMP_ID_A)
        signals = make_signals(competitor_prices={COMP_ID_B: Decimal("89.99")})
        self.evaluator._match_competitor_by_name = AsyncMock(return_value=None)
        result = await self.evaluator._eval_competitor_relative(rule, signals)
        assert result is None

    @pytest.mark.asyncio
    async def test_no_competitor_id_uses_lowest_price(self):
        """When no specific competitor, picks the lowest price."""
        rule = make_rule(
            competitor_id=None,
            competitor_margin_percent=Decimal("3"),
            price_position="below",
        )
        signals = make_signals(
            competitor_prices={
                COMP_ID_A: Decimal("120.00"),
                COMP_ID_B: Decimal("95.00"),
            }
        )
        result = await self.evaluator._eval_competitor_relative(rule, signals)
        assert result is not None
        assert result["competitor_price"] == 95.00
        assert result["competitor_id"] == str(COMP_ID_B)

    @pytest.mark.asyncio
    async def test_no_competitor_id_no_prices(self):
        rule = make_rule(competitor_id=None)
        signals = make_signals(competitor_prices={})
        result = await self.evaluator._eval_competitor_relative(rule, signals)
        assert result is None

    @pytest.mark.asyncio
    async def test_margin_percent_in_result(self):
        rule = make_rule(
            competitor_id=COMP_ID_A,
            competitor_margin_percent=Decimal("7.5"),
        )
        signals = make_signals(competitor_prices={COMP_ID_A: Decimal("100")})
        result = await self.evaluator._eval_competitor_relative(rule, signals)
        assert result["margin_percent"] == 7.5

    @pytest.mark.asyncio
    async def test_null_margin_defaults_to_zero(self):
        rule = make_rule(
            competitor_id=COMP_ID_A,
            competitor_margin_percent=None,
        )
        signals = make_signals(competitor_prices={COMP_ID_A: Decimal("100")})
        result = await self.evaluator._eval_competitor_relative(rule, signals)
        assert result["margin_percent"] == 0


# ============================================================
# 6. _match_competitor_by_name
# ============================================================


class TestMatchCompetitorByName:
    def setup_method(self):
        self.db = make_mock_db()
        self.evaluator = RuleEvaluator(self.db)

    @pytest.mark.asyncio
    async def test_empty_available_prices(self):
        result = await self.evaluator._match_competitor_by_name(COMP_ID_A, {})
        assert result is None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_target_competitor_not_found(self, mock_select):
        """Rule's competitor_id not in DB → returns None."""
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        # First query: target name → None
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        self.db.execute.return_value = mock_result

        result = await self.evaluator._match_competitor_by_name(COMP_ID_A, {COMP_ID_B: Decimal("99.99")})
        assert result is None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_name_match_found(self, mock_select):
        """Finds matching competitor by name."""
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        # First query: target name
        mock_result_1 = MagicMock()
        mock_result_1.scalar.return_value = "Amazon"

        # Second query: available competitors
        mock_result_2 = MagicMock()
        mock_result_2.all.return_value = [(COMP_ID_B, "Amazon")]

        self.db.execute.side_effect = [mock_result_1, mock_result_2]

        result = await self.evaluator._match_competitor_by_name(COMP_ID_A, {COMP_ID_B: Decimal("99.99")})
        assert result is not None
        assert result["competitor_id"] == COMP_ID_B
        assert result["price"] == Decimal("99.99")
        assert result["name"] == "Amazon"

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_name_match_case_insensitive(self, mock_select):
        """Name matching is case-insensitive."""
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result_1 = MagicMock()
        mock_result_1.scalar.return_value = "AMAZON"

        mock_result_2 = MagicMock()
        mock_result_2.all.return_value = [(COMP_ID_B, "amazon")]

        self.db.execute.side_effect = [mock_result_1, mock_result_2]

        result = await self.evaluator._match_competitor_by_name(COMP_ID_A, {COMP_ID_B: Decimal("99.99")})
        assert result is not None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_name_match_strips_whitespace(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result_1 = MagicMock()
        mock_result_1.scalar.return_value = "  Amazon  "

        mock_result_2 = MagicMock()
        mock_result_2.all.return_value = [(COMP_ID_B, "Amazon")]

        self.db.execute.side_effect = [mock_result_1, mock_result_2]

        result = await self.evaluator._match_competitor_by_name(COMP_ID_A, {COMP_ID_B: Decimal("99.99")})
        assert result is not None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_no_name_match(self, mock_select):
        """No competitor with matching name → returns None."""
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result_1 = MagicMock()
        mock_result_1.scalar.return_value = "Amazon"

        mock_result_2 = MagicMock()
        mock_result_2.all.return_value = [(COMP_ID_B, "Walmart")]

        self.db.execute.side_effect = [mock_result_1, mock_result_2]

        result = await self.evaluator._match_competitor_by_name(COMP_ID_A, {COMP_ID_B: Decimal("99.99")})
        assert result is None


# ============================================================
# 7. _eval_time_based
# ============================================================


class TestEvalTimeBased:
    def setup_method(self):
        self.evaluator = RuleEvaluator(make_mock_db())

    def test_no_time_constraints_always_matches(self):
        rule = make_rule(time_days=None, time_start=None, time_end=None)
        result = self.evaluator._eval_time_based(rule)
        assert result is not None
        assert result["rule_type"] == "time_based"

    @patch(f"{SERVICE_PATH}.datetime")
    def test_correct_day_matches(self, mock_dt):
        mock_now = MagicMock()
        mock_now.strftime.side_effect = lambda fmt: "Monday" if fmt == "%A" else "12:00"
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        rule = make_rule(time_days="Monday, Wednesday, Friday", time_start=None, time_end=None)
        result = self.evaluator._eval_time_based(rule)
        assert result is not None

    @patch(f"{SERVICE_PATH}.datetime")
    def test_wrong_day_no_match(self, mock_dt):
        mock_now = MagicMock()
        mock_now.strftime.side_effect = lambda fmt: "Tuesday" if fmt == "%A" else "12:00"
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        rule = make_rule(time_days="Monday, Wednesday", time_start=None, time_end=None)
        result = self.evaluator._eval_time_based(rule)
        assert result is None

    @patch(f"{SERVICE_PATH}.datetime")
    def test_within_time_range(self, mock_dt):
        mock_now = MagicMock()
        mock_now.strftime.side_effect = lambda fmt: "Monday" if fmt == "%A" else "14:00"
        mock_now.isoformat.return_value = "2026-02-08T14:00:00+00:00"
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        rule = make_rule(time_days=None, time_start="09:00", time_end="17:00")
        result = self.evaluator._eval_time_based(rule)
        assert result is not None

    @patch(f"{SERVICE_PATH}.datetime")
    def test_outside_time_range(self, mock_dt):
        mock_now = MagicMock()
        mock_now.strftime.side_effect = lambda fmt: "Monday" if fmt == "%A" else "22:00"
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        rule = make_rule(time_days=None, time_start="09:00", time_end="17:00")
        result = self.evaluator._eval_time_based(rule)
        assert result is None

    @patch(f"{SERVICE_PATH}.datetime")
    def test_result_contains_time_info(self, mock_dt):
        mock_now = MagicMock()
        mock_now.strftime.side_effect = lambda fmt: "Monday" if fmt == "%A" else "14:00"
        mock_now.isoformat.return_value = "2026-02-08T14:00:00+00:00"
        mock_dt.now.return_value = mock_now
        mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

        rule = make_rule(time_days="Monday", time_start="09:00", time_end="17:00")
        result = self.evaluator._eval_time_based(rule)
        assert result["time_days"] == "Monday"
        assert result["time_start"] == "09:00"
        assert result["time_end"] == "17:00"


# ============================================================
# 8. _eval_volume_surge
# ============================================================


class TestEvalVolumeSurge:
    def setup_method(self):
        self.evaluator = RuleEvaluator(make_mock_db())

    def test_zero_baseline_returns_none(self):
        rule = make_rule(volume_threshold=200)
        signals = make_signals(mention_count_24h=500, mention_baseline=0)
        assert self.evaluator._eval_volume_surge(rule, signals) is None

    def test_surge_triggered(self):
        rule = make_rule(volume_threshold=200)  # 200% = 2x
        signals = make_signals(mention_count_24h=300, mention_baseline=100)
        result = self.evaluator._eval_volume_surge(rule, signals)
        assert result is not None
        assert result["rule_type"] == "volume_surge"
        assert result["surge_ratio"] == 3.0

    def test_surge_not_triggered(self):
        rule = make_rule(volume_threshold=200)
        signals = make_signals(mention_count_24h=150, mention_baseline=100)
        result = self.evaluator._eval_volume_surge(rule, signals)
        assert result is None  # 1.5x < 2.0x threshold

    def test_exactly_at_threshold(self):
        rule = make_rule(volume_threshold=200)
        signals = make_signals(mention_count_24h=200, mention_baseline=100)
        result = self.evaluator._eval_volume_surge(rule, signals)
        assert result is not None  # 2.0x >= 2.0x

    def test_default_threshold_200(self):
        rule = make_rule(volume_threshold=None)  # defaults to 200
        signals = make_signals(mention_count_24h=300, mention_baseline=100)
        result = self.evaluator._eval_volume_surge(rule, signals)
        assert result is not None  # 3.0x >= 2.0x

    def test_result_contains_correct_values(self):
        rule = make_rule(volume_threshold=150)
        signals = make_signals(mention_count_24h=400, mention_baseline=100)
        result = self.evaluator._eval_volume_surge(rule, signals)
        assert result["mention_count_24h"] == 400
        assert result["baseline"] == 100
        assert result["surge_ratio"] == 4.0
        assert result["threshold_ratio"] == 1.5


# ============================================================
# 9. _eval_viral_detection
# ============================================================


class TestEvalViralDetection:
    def setup_method(self):
        self.evaluator = RuleEvaluator(make_mock_db())

    def test_not_viral_returns_none(self):
        rule = make_rule()
        signals = make_signals(viral_detected=False)
        assert self.evaluator._eval_viral_detection(rule, signals) is None

    def test_viral_all_thresholds_met(self):
        rule = make_rule(
            viral_threshold_reach=1000,
            viral_threshold_engagement=100,
            viral_sentiment_min=Decimal("0.5"),
        )
        signals = make_signals(
            viral_detected=True,
            viral_reach=5000,
            viral_engagement=500,
            viral_sentiment=Decimal("0.8"),
        )
        result = self.evaluator._eval_viral_detection(rule, signals)
        assert result is not None
        assert result["rule_type"] == "viral_detection"
        assert result["viral_reach"] == 5000

    def test_reach_below_threshold(self):
        rule = make_rule(viral_threshold_reach=10000)
        signals = make_signals(
            viral_detected=True,
            viral_reach=500,
            viral_engagement=1000,
        )
        assert self.evaluator._eval_viral_detection(rule, signals) is None

    def test_engagement_below_threshold(self):
        rule = make_rule(
            viral_threshold_reach=100,
            viral_threshold_engagement=5000,
        )
        signals = make_signals(
            viral_detected=True,
            viral_reach=10000,
            viral_engagement=100,
        )
        assert self.evaluator._eval_viral_detection(rule, signals) is None

    def test_sentiment_below_min(self):
        rule = make_rule(
            viral_threshold_reach=0,
            viral_threshold_engagement=0,
            viral_sentiment_min=Decimal("0.7"),
        )
        signals = make_signals(
            viral_detected=True,
            viral_reach=10000,
            viral_engagement=5000,
            viral_sentiment=Decimal("0.3"),
        )
        assert self.evaluator._eval_viral_detection(rule, signals) is None

    def test_no_thresholds_viral_only(self):
        """All thresholds None/0 — just viral_detected is enough."""
        rule = make_rule(
            viral_threshold_reach=None,
            viral_threshold_engagement=None,
            viral_sentiment_min=None,
        )
        signals = make_signals(
            viral_detected=True,
            viral_reach=100,
            viral_engagement=10,
        )
        result = self.evaluator._eval_viral_detection(rule, signals)
        assert result is not None

    def test_sentiment_min_with_no_viral_sentiment(self):
        """When viral_sentiment is None, sentiment check passes."""
        rule = make_rule(
            viral_threshold_reach=0,
            viral_threshold_engagement=0,
            viral_sentiment_min=Decimal("0.5"),
        )
        signals = make_signals(
            viral_detected=True,
            viral_reach=1000,
            viral_engagement=100,
            viral_sentiment=None,
        )
        result = self.evaluator._eval_viral_detection(rule, signals)
        # sentiment_ok defaults to True when viral_sentiment is None
        assert result is not None

    def test_result_contains_viral_sentiment(self):
        rule = make_rule(viral_threshold_reach=0, viral_threshold_engagement=0)
        signals = make_signals(
            viral_detected=True,
            viral_reach=1000,
            viral_engagement=100,
            viral_sentiment=Decimal("0.9"),
        )
        result = self.evaluator._eval_viral_detection(rule, signals)
        assert result["viral_sentiment"] == 0.9

    def test_result_viral_sentiment_none(self):
        rule = make_rule(viral_threshold_reach=0, viral_threshold_engagement=0)
        signals = make_signals(
            viral_detected=True,
            viral_reach=1000,
            viral_engagement=100,
            viral_sentiment=None,
        )
        result = self.evaluator._eval_viral_detection(rule, signals)
        assert result["viral_sentiment"] is None


# ============================================================
# 10. _evaluate_rule (routing)
# ============================================================


class TestEvaluateRule:
    """Tests that _evaluate_rule routes to the correct evaluator."""

    def setup_method(self):
        self.evaluator = RuleEvaluator(make_mock_db())

    @pytest.mark.asyncio
    async def test_routes_to_sentiment(self):
        rule = make_rule(
            rule_type=SENTIMENT_THRESHOLD,
            sentiment_threshold=Decimal("0.5"),
            sentiment_direction="above",
        )
        signals = make_signals(sentiment_score=Decimal("0.8"))
        product = make_product()
        result = await self.evaluator._evaluate_rule(rule, product, signals)
        assert result is not None
        assert result["rule_type"] == "sentiment_threshold"

    @pytest.mark.asyncio
    async def test_routes_to_competitor(self):
        rule = make_rule(
            rule_type=COMPETITOR_RELATIVE,
            competitor_id=COMP_ID_A,
        )
        signals = make_signals(competitor_prices={COMP_ID_A: Decimal("99")})
        product = make_product()
        result = await self.evaluator._evaluate_rule(rule, product, signals)
        assert result is not None
        assert result["rule_type"] == "competitor_relative"

    @pytest.mark.asyncio
    async def test_routes_to_volume_surge(self):
        rule = make_rule(
            rule_type=VOLUME_SURGE,
            volume_threshold=100,
        )
        signals = make_signals(mention_count_24h=500, mention_baseline=100)
        product = make_product()
        result = await self.evaluator._evaluate_rule(rule, product, signals)
        assert result is not None
        assert result["rule_type"] == "volume_surge"

    @pytest.mark.asyncio
    async def test_routes_to_viral(self):
        rule = make_rule(
            rule_type=VIRAL_DETECTION,
            viral_threshold_reach=0,
            viral_threshold_engagement=0,
        )
        signals = make_signals(
            viral_detected=True,
            viral_reach=1000,
            viral_engagement=100,
        )
        product = make_product()
        result = await self.evaluator._evaluate_rule(rule, product, signals)
        assert result is not None
        assert result["rule_type"] == "viral_detection"

    @pytest.mark.asyncio
    async def test_unknown_rule_type_returns_none(self):
        rule = make_rule(rule_type=MagicMock())
        signals = make_signals()
        product = make_product()
        result = await self.evaluator._evaluate_rule(rule, product, signals)
        assert result is None


# ============================================================
# 11. find_matching_rule
# ============================================================


class TestFindMatchingRule:
    """Tests for the main find_matching_rule pipeline."""

    def setup_method(self):
        self.db = make_mock_db()
        self.evaluator = RuleEvaluator(self.db)

    @pytest.mark.asyncio
    async def test_returns_first_matching_rule(self):
        rule = make_rule(
            rule_type=SENTIMENT_THRESHOLD,
            sentiment_threshold=Decimal("0.5"),
            sentiment_direction="above",
            last_triggered_at=None,
        )
        self.evaluator.get_active_rules = AsyncMock(return_value=[rule])

        product = make_product()
        signals = make_signals(sentiment_score=Decimal("0.8"))

        result_rule, details = await self.evaluator.find_matching_rule(product, USER_ID, signals)
        assert result_rule is rule
        assert details is not None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_rules(self):
        self.evaluator.get_active_rules = AsyncMock(return_value=[])
        product = make_product()
        signals = make_signals()

        result_rule, details = await self.evaluator.find_matching_rule(product, USER_ID, signals)
        assert result_rule is None
        assert details is None

    @pytest.mark.asyncio
    async def test_skips_rule_in_cooldown(self):
        """Rule triggered recently should be skipped."""
        rule = make_rule(
            rule_type=SENTIMENT_THRESHOLD,
            sentiment_threshold=Decimal("0.5"),
            sentiment_direction="above",
            cooldown_hours=24,
            last_triggered_at=datetime.now(UTC) - timedelta(hours=1),  # 1h ago, cooldown 24h
        )
        self.evaluator.get_active_rules = AsyncMock(return_value=[rule])
        product = make_product()
        signals = make_signals(sentiment_score=Decimal("0.8"))

        result_rule, details = await self.evaluator.find_matching_rule(product, USER_ID, signals)
        assert result_rule is None

    @pytest.mark.asyncio
    async def test_rule_past_cooldown_evaluated(self):
        """Rule past cooldown should be evaluated."""
        rule = make_rule(
            rule_type=SENTIMENT_THRESHOLD,
            sentiment_threshold=Decimal("0.5"),
            sentiment_direction="above",
            cooldown_hours=1,
            last_triggered_at=datetime.now(UTC) - timedelta(hours=2),  # 2h ago, cooldown 1h
        )
        self.evaluator.get_active_rules = AsyncMock(return_value=[rule])
        product = make_product()
        signals = make_signals(sentiment_score=Decimal("0.8"))

        result_rule, details = await self.evaluator.find_matching_rule(product, USER_ID, signals)
        assert result_rule is rule

    @pytest.mark.asyncio
    async def test_never_triggered_rule_no_cooldown(self):
        """Rule with last_triggered_at=None has no cooldown."""
        rule = make_rule(
            rule_type=SENTIMENT_THRESHOLD,
            sentiment_threshold=Decimal("0.5"),
            sentiment_direction="above",
            last_triggered_at=None,
        )
        self.evaluator.get_active_rules = AsyncMock(return_value=[rule])
        product = make_product()
        signals = make_signals(sentiment_score=Decimal("0.8"))

        result_rule, details = await self.evaluator.find_matching_rule(product, USER_ID, signals)
        assert result_rule is rule

    @pytest.mark.asyncio
    async def test_skips_non_matching_rule_tries_next(self):
        """If first rule doesn't match signals, tries next in priority order."""
        rule1 = make_rule(
            rule_type=SENTIMENT_THRESHOLD,
            sentiment_threshold=Decimal("0.9"),  # Won't match
            sentiment_direction="above",
            last_triggered_at=None,
        )
        rule2 = make_rule(
            rule_type=SENTIMENT_THRESHOLD,
            sentiment_threshold=Decimal("0.3"),  # Will match
            sentiment_direction="above",
            last_triggered_at=None,
        )
        self.evaluator.get_active_rules = AsyncMock(return_value=[rule1, rule2])
        product = make_product()
        signals = make_signals(sentiment_score=Decimal("0.5"))

        result_rule, details = await self.evaluator.find_matching_rule(product, USER_ID, signals)
        assert result_rule is rule2

    @pytest.mark.asyncio
    async def test_passes_product_category_to_get_active_rules(self):
        self.evaluator.get_active_rules = AsyncMock(return_value=[])
        product = make_product(category="electronics")
        signals = make_signals()

        await self.evaluator.find_matching_rule(product, USER_ID, signals)
        self.evaluator.get_active_rules.assert_awaited_once_with(product.id, USER_ID, "electronics")


# ============================================================
# 12. get_active_rules (DB query)
# ============================================================


class TestGetActiveRules:
    def setup_method(self):
        self.db = make_mock_db()
        self.evaluator = RuleEvaluator(self.db)

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_applicable_rules(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_select.return_value = mock_chain

        rule_all = make_rule(applies_to_all_products=True)
        rule_other = make_rule(product_id=uuid4())  # Different product

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [rule_all, rule_other]
        self.db.execute.return_value = mock_result

        rules = await self.evaluator.get_active_rules(PRODUCT_ID, USER_ID)
        assert len(rules) == 1
        assert rules[0] is rule_all

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_empty_when_no_rules(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        self.db.execute.return_value = mock_result

        rules = await self.evaluator.get_active_rules(PRODUCT_ID, USER_ID)
        assert rules == []

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_queries_database(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_select.return_value = mock_chain

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        self.db.execute.return_value = mock_result

        await self.evaluator.get_active_rules(PRODUCT_ID, USER_ID)
        self.db.execute.assert_awaited_once()
