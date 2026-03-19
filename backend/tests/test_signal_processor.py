# backend/tests/test_signal_processor.py
"""
Comprehensive tests for SignalProcessor — gathers and processes market signals.

Tests cover:
- Initialization
- gather_signals (full orchestration)
- _get_sentiment_signals (current avg, 24h change)
- _get_volume_signals (count, baseline)
- _get_viral_signals (detection, reach, engagement, sentiment)
- _get_competitor_prices (active competitors)
- _get_trend_signals (orchestration)
- _get_daily_mention_counts (per-day counts)
- _get_daily_sentiment (per-day averages)
- _calculate_growth_rate (recent vs earlier)
- _calculate_momentum (sentiment direction)
- _calculate_velocity (acceleration)
- _determine_trend (direction + strength)
- calculate_price_impact (all impact types)

Total: ~85 tests
"""

import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# === Import isolation ===
for mod in [
    "db.session",
    "models.product",
    "models.sentiment",
    "models.social_mention",
    "models.competitor_product",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Fix MagicMock comparison operators for model columns used with datetime/bool.
# MagicMock.__ge__ returns NotImplemented by default → TypeError when compared with real types.
# Must directly configure the exact model class attributes that signal_processor.py imports.

from models.sentiment import Sentiment

for _col in ["analyzed_at", "compound_score", "product_id"]:
    _c = getattr(Sentiment, _col)
    try:
        _c.__ge__ = MagicMock(return_value=MagicMock())
        _c.__le__ = MagicMock(return_value=MagicMock())
        _c.__lt__ = MagicMock(return_value=MagicMock())
        _c.__gt__ = MagicMock(return_value=MagicMock())
        _c.__eq__ = MagicMock(return_value=MagicMock())
    except (AttributeError, TypeError):
        pass  # Real SQLAlchemy model — operators already work

from models.social_mention import SocialMention

for _col in ["published_at", "product_id", "id", "engagement_count"]:
    _c = getattr(SocialMention, _col)
    try:
        _c.__ge__ = MagicMock(return_value=MagicMock())
        _c.__le__ = MagicMock(return_value=MagicMock())
        _c.__lt__ = MagicMock(return_value=MagicMock())
        _c.__gt__ = MagicMock(return_value=MagicMock())
        _c.__eq__ = MagicMock(return_value=MagicMock())
        _c.desc = MagicMock(return_value=MagicMock())
    except (AttributeError, TypeError):
        pass  # Real SQLAlchemy model — operators already work

from models.competitor_product import CompetitorProduct

for _col in ["product_id", "is_active", "competitor_id", "current_price"]:
    _c = getattr(CompetitorProduct, _col)
    try:
        _c.__ge__ = MagicMock(return_value=MagicMock())
        _c.__eq__ = MagicMock(return_value=MagicMock())
    except (AttributeError, TypeError):
        pass  # Real SQLAlchemy model — operators already work

import pytest

from services.pricing.rule_evaluator import MarketSignals
from services.pricing.signal_processor import SignalProcessor

SERVICE_PATH = "services.pricing.signal_processor"

# ============================================================
# Helpers
# ============================================================

PRODUCT_ID = uuid4()
COMP_ID_A = uuid4()
COMP_ID_B = uuid4()


def make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    return db


def make_product(id=None, current_price=Decimal("100.00")):
    p = MagicMock()
    p.id = id or PRODUCT_ID
    p.current_price = current_price
    return p


def make_signals(**kwargs):
    return MarketSignals(**kwargs)


# ============================================================
# 1. Initialization
# ============================================================


class TestSignalProcessorInit:
    def test_stores_db(self):
        db = make_mock_db()
        sp = SignalProcessor(db)
        assert sp.db is db

    def test_class_constants(self):
        assert SignalProcessor.TRENDING_GROWTH_THRESHOLD == Decimal("0.5")
        assert SignalProcessor.STRONG_TREND_THRESHOLD == Decimal("1.0")


# ============================================================
# 2. gather_signals (orchestration)
# ============================================================


class TestGatherSignals:
    @pytest.mark.asyncio
    async def test_returns_market_signals(self):
        db = make_mock_db()
        sp = SignalProcessor(db)

        sp._get_sentiment_signals = AsyncMock(return_value=(Decimal("0.7"), Decimal("0.1")))
        sp._get_volume_signals = AsyncMock(return_value=(50, 30))
        sp._get_viral_signals = AsyncMock(return_value=(False, 0, 0, None))
        sp._get_competitor_prices = AsyncMock(return_value={})
        sp._get_trend_signals = AsyncMock(
            return_value={
                "direction": "stable",
                "strength": Decimal("0"),
                "velocity": Decimal("0"),
                "mention_growth_rate": Decimal("0"),
                "sentiment_momentum": Decimal("0"),
                "is_trending": False,
            }
        )

        result = await sp.gather_signals(make_product())
        assert isinstance(result, MarketSignals)

    @pytest.mark.asyncio
    async def test_populates_sentiment_fields(self):
        db = make_mock_db()
        sp = SignalProcessor(db)

        sp._get_sentiment_signals = AsyncMock(return_value=(Decimal("0.75"), Decimal("0.05")))
        sp._get_volume_signals = AsyncMock(return_value=(0, 0))
        sp._get_viral_signals = AsyncMock(return_value=(False, 0, 0, None))
        sp._get_competitor_prices = AsyncMock(return_value={})
        sp._get_trend_signals = AsyncMock(
            return_value={
                "direction": "stable",
                "strength": Decimal("0"),
                "velocity": Decimal("0"),
                "mention_growth_rate": Decimal("0"),
                "sentiment_momentum": Decimal("0"),
                "is_trending": False,
            }
        )

        result = await sp.gather_signals(make_product())
        assert result.sentiment_score == Decimal("0.75")
        assert result.sentiment_change_24h == Decimal("0.05")

    @pytest.mark.asyncio
    async def test_populates_volume_fields(self):
        db = make_mock_db()
        sp = SignalProcessor(db)

        sp._get_sentiment_signals = AsyncMock(return_value=(None, None))
        sp._get_volume_signals = AsyncMock(return_value=(150, 50))
        sp._get_viral_signals = AsyncMock(return_value=(False, 0, 0, None))
        sp._get_competitor_prices = AsyncMock(return_value={})
        sp._get_trend_signals = AsyncMock(
            return_value={
                "direction": "stable",
                "strength": Decimal("0"),
                "velocity": Decimal("0"),
                "mention_growth_rate": Decimal("0"),
                "sentiment_momentum": Decimal("0"),
                "is_trending": False,
            }
        )

        result = await sp.gather_signals(make_product())
        assert result.mention_count_24h == 150
        assert result.mention_baseline == 50

    @pytest.mark.asyncio
    async def test_populates_viral_fields(self):
        db = make_mock_db()
        sp = SignalProcessor(db)

        sp._get_sentiment_signals = AsyncMock(return_value=(None, None))
        sp._get_volume_signals = AsyncMock(return_value=(0, 0))
        sp._get_viral_signals = AsyncMock(return_value=(True, 50000, 5000, Decimal("0.8")))
        sp._get_competitor_prices = AsyncMock(return_value={})
        sp._get_trend_signals = AsyncMock(
            return_value={
                "direction": "stable",
                "strength": Decimal("0"),
                "velocity": Decimal("0"),
                "mention_growth_rate": Decimal("0"),
                "sentiment_momentum": Decimal("0"),
                "is_trending": False,
            }
        )

        result = await sp.gather_signals(make_product())
        assert result.viral_detected is True
        assert result.viral_reach == 50000
        assert result.viral_engagement == 5000
        assert result.viral_sentiment == Decimal("0.8")

    @pytest.mark.asyncio
    async def test_populates_competitor_prices(self):
        db = make_mock_db()
        sp = SignalProcessor(db)

        prices = {COMP_ID_A: Decimal("95"), COMP_ID_B: Decimal("110")}
        sp._get_sentiment_signals = AsyncMock(return_value=(None, None))
        sp._get_volume_signals = AsyncMock(return_value=(0, 0))
        sp._get_viral_signals = AsyncMock(return_value=(False, 0, 0, None))
        sp._get_competitor_prices = AsyncMock(return_value=prices)
        sp._get_trend_signals = AsyncMock(
            return_value={
                "direction": "stable",
                "strength": Decimal("0"),
                "velocity": Decimal("0"),
                "mention_growth_rate": Decimal("0"),
                "sentiment_momentum": Decimal("0"),
                "is_trending": False,
            }
        )

        result = await sp.gather_signals(make_product())
        assert result.competitor_prices == prices

    @pytest.mark.asyncio
    async def test_populates_trend_fields(self):
        db = make_mock_db()
        sp = SignalProcessor(db)

        sp._get_sentiment_signals = AsyncMock(return_value=(None, None))
        sp._get_volume_signals = AsyncMock(return_value=(0, 0))
        sp._get_viral_signals = AsyncMock(return_value=(False, 0, 0, None))
        sp._get_competitor_prices = AsyncMock(return_value={})
        sp._get_trend_signals = AsyncMock(
            return_value={
                "direction": "up",
                "strength": Decimal("0.7"),
                "velocity": Decimal("0.3"),
                "mention_growth_rate": Decimal("0.6"),
                "sentiment_momentum": Decimal("0.2"),
                "is_trending": True,
            }
        )

        result = await sp.gather_signals(make_product())
        assert result.trend_direction == "up"
        assert result.trend_strength == Decimal("0.7")
        assert result.is_trending is True


# ============================================================
# 3. _get_sentiment_signals
# ============================================================


class TestGetSentimentSignals:
    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    @patch(f"{SERVICE_PATH}.func")
    async def test_returns_none_when_no_data(self, mock_func, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        db.execute.return_value = mock_result

        sp = SignalProcessor(db)
        score, change = await sp._get_sentiment_signals(PRODUCT_ID)
        assert score is None
        assert change is None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    @patch(f"{SERVICE_PATH}.func")
    async def test_returns_score_with_no_previous(self, mock_func, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()

        # First call: current avg
        result1 = MagicMock()
        result1.scalar.return_value = 0.75
        # Second call: previous avg = None
        result2 = MagicMock()
        result2.scalar.return_value = None

        db.execute.side_effect = [result1, result2]

        sp = SignalProcessor(db)
        score, change = await sp._get_sentiment_signals(PRODUCT_ID)
        assert score == Decimal("0.750")
        assert change is None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    @patch(f"{SERVICE_PATH}.func")
    async def test_returns_score_and_change(self, mock_func, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()

        result1 = MagicMock()
        result1.scalar.return_value = 0.75
        result2 = MagicMock()
        result2.scalar.return_value = 0.60

        db.execute.side_effect = [result1, result2]

        sp = SignalProcessor(db)
        score, change = await sp._get_sentiment_signals(PRODUCT_ID)
        assert score == Decimal("0.750")
        assert change == Decimal("0.150")


# ============================================================
# 4. _get_volume_signals
# ============================================================


class TestGetVolumeSignals:
    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    @patch(f"{SERVICE_PATH}.func")
    async def test_returns_count_and_baseline(self, mock_func, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()

        result1 = MagicMock()
        result1.scalar.return_value = 50  # 24h count
        result2 = MagicMock()
        result2.scalar.return_value = 180  # 6-day total → baseline = 180//6 = 30

        db.execute.side_effect = [result1, result2]

        sp = SignalProcessor(db)
        count, baseline = await sp._get_volume_signals(PRODUCT_ID)
        assert count == 50
        assert baseline == 30

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    @patch(f"{SERVICE_PATH}.func")
    async def test_returns_zeros_when_no_data(self, mock_func, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()

        result1 = MagicMock()
        result1.scalar.return_value = None
        result2 = MagicMock()
        result2.scalar.return_value = None

        db.execute.side_effect = [result1, result2]

        sp = SignalProcessor(db)
        count, baseline = await sp._get_volume_signals(PRODUCT_ID)
        assert count == 0
        assert baseline == 0

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    @patch(f"{SERVICE_PATH}.func")
    async def test_baseline_is_zero_when_no_previous(self, mock_func, mock_select):
        mock_select.return_value.where.return_value = MagicMock()
        db = make_mock_db()

        result1 = MagicMock()
        result1.scalar.return_value = 100
        result2 = MagicMock()
        result2.scalar.return_value = 0  # No previous mentions

        db.execute.side_effect = [result1, result2]

        sp = SignalProcessor(db)
        count, baseline = await sp._get_volume_signals(PRODUCT_ID)
        assert count == 100
        assert baseline == 0


# ============================================================
# 5. _get_viral_signals
# ============================================================


class TestGetViralSignals:
    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_no_posts_returns_false(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        sp = SignalProcessor(db)
        viral, reach, engagement, sentiment = await sp._get_viral_signals(PRODUCT_ID)
        assert viral is False
        assert reach == 0
        assert engagement == 0
        assert sentiment is None

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_high_engagement_is_viral(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()

        # Top posts with high engagement
        post1 = MagicMock(author_followers=5000, engagement_count=800)
        post2 = MagicMock(author_followers=8000, engagement_count=600)
        top_posts_result = MagicMock()
        top_posts_result.scalars.return_value.all.return_value = [post1, post2]

        # Sentiment query for viral posts
        sent_mock = MagicMock(compound_score=Decimal("0.8"))
        sent_result = MagicMock()
        sent_result.scalars.return_value.first.return_value = sent_mock

        db.execute.side_effect = [top_posts_result, sent_result, sent_result]

        sp = SignalProcessor(db)
        viral, reach, engagement, _sentiment = await sp._get_viral_signals(PRODUCT_ID)
        assert viral is True  # reach=13000 > 10000
        assert reach == 13000
        assert engagement == 1400

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_low_engagement_not_viral(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_chain.order_by.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()

        post = MagicMock(author_followers=100, engagement_count=50)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [post]
        db.execute.return_value = result_mock

        sp = SignalProcessor(db)
        viral, _reach, _engagement, sentiment = await sp._get_viral_signals(PRODUCT_ID)
        assert viral is False
        assert sentiment is None


# ============================================================
# 6. _get_competitor_prices
# ============================================================


class TestGetCompetitorPrices:
    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_active_prices(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        cp1 = MagicMock(competitor_id=COMP_ID_A, current_price=Decimal("95"))
        cp2 = MagicMock(competitor_id=COMP_ID_B, current_price=Decimal("110"))
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [cp1, cp2]
        db.execute.return_value = result_mock

        sp = SignalProcessor(db)
        prices = await sp._get_competitor_prices(PRODUCT_ID)
        assert prices[COMP_ID_A] == Decimal("95")
        assert prices[COMP_ID_B] == Decimal("110")

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_skips_null_prices(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        cp1 = MagicMock(competitor_id=COMP_ID_A, current_price=Decimal("95"))
        cp2 = MagicMock(competitor_id=COMP_ID_B, current_price=None)
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [cp1, cp2]
        db.execute.return_value = result_mock

        sp = SignalProcessor(db)
        prices = await sp._get_competitor_prices(PRODUCT_ID)
        assert COMP_ID_A in prices
        assert COMP_ID_B not in prices

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_empty_when_no_competitors(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute.return_value = result_mock

        sp = SignalProcessor(db)
        prices = await sp._get_competitor_prices(PRODUCT_ID)
        assert prices == {}


# ============================================================
# 7. _calculate_growth_rate (pure function)
# ============================================================


class TestCalculateGrowthRate:
    def setup_method(self):
        self.sp = SignalProcessor(make_mock_db())

    def test_insufficient_data(self):
        assert self.sp._calculate_growth_rate([1, 2, 3]) == Decimal("0")

    def test_no_growth(self):
        # last 3 = [10,10,10]=30, prev 3 = [10,10,10]=30, growth = 0
        result = self.sp._calculate_growth_rate([10, 10, 10, 10, 10, 10])
        assert result == Decimal("0.00")

    def test_positive_growth(self):
        # prev 3 = [10,10,10]=30, last 3 = [20,20,20]=60, growth = 100%
        result = self.sp._calculate_growth_rate([10, 10, 10, 20, 20, 20])
        assert result == Decimal("1.00")

    def test_negative_growth(self):
        # prev 3 = [20,20,20]=60, last 3 = [10,10,10]=30, growth = -50%
        result = self.sp._calculate_growth_rate([20, 20, 20, 10, 10, 10])
        assert result == Decimal("-0.50")

    def test_growth_from_zero(self):
        # prev 3 = [0,0,0]=0, last 3 = [10,10,10]=30
        result = self.sp._calculate_growth_rate([0, 0, 0, 10, 10, 10])
        assert result == Decimal("1.0")

    def test_no_growth_from_zero(self):
        result = self.sp._calculate_growth_rate([0, 0, 0, 0, 0, 0])
        assert result == Decimal("0")

    def test_four_days_uses_first_three_as_earlier(self):
        # Only 4 days: earlier=sum([:3])=[5,5,5]=15, recent=sum([-3:])=[5,5,10]=20
        result = self.sp._calculate_growth_rate([5, 5, 5, 10])
        # recent=[5,5,10]=20, earlier=[5,5,5]=15, growth=(20-15)/15=0.33
        assert result == Decimal("0.33")


# ============================================================
# 8. _calculate_momentum (pure function)
# ============================================================


class TestCalculateMomentum:
    def setup_method(self):
        self.sp = SignalProcessor(make_mock_db())

    def test_insufficient_data(self):
        result = self.sp._calculate_momentum([Decimal("0.5"), Decimal("0.6")])
        assert result == Decimal("0")

    def test_positive_momentum(self):
        # Increasing: 0.5, 0.6, 0.7 → changes=[0.1, 0.1] → avg=0.1 → /0.5=0.2
        result = self.sp._calculate_momentum([Decimal("0.5"), Decimal("0.6"), Decimal("0.7")])
        assert result == Decimal("0.20")

    def test_negative_momentum(self):
        result = self.sp._calculate_momentum([Decimal("0.7"), Decimal("0.6"), Decimal("0.5")])
        assert result == Decimal("-0.20")

    def test_stable_momentum(self):
        result = self.sp._calculate_momentum([Decimal("0.5"), Decimal("0.5"), Decimal("0.5")])
        assert result == Decimal("0.00")

    def test_clamped_at_positive_1(self):
        # Very large jumps
        result = self.sp._calculate_momentum([Decimal("0"), Decimal("0.8"), Decimal("1.0")])
        assert result <= Decimal("1")

    def test_clamped_at_negative_1(self):
        result = self.sp._calculate_momentum([Decimal("1.0"), Decimal("0.2"), Decimal("-0.8")])
        assert result >= Decimal("-1")

    def test_filters_none_values(self):
        result = self.sp._calculate_momentum([None, Decimal("0.5"), Decimal("0.6"), Decimal("0.7")])
        assert result == Decimal("0.20")

    def test_all_none_returns_zero(self):
        result = self.sp._calculate_momentum([None, None, None])
        assert result == Decimal("0")


# ============================================================
# 9. _calculate_velocity (pure function)
# ============================================================


class TestCalculateVelocity:
    def setup_method(self):
        self.sp = SignalProcessor(make_mock_db())

    def test_insufficient_data(self):
        assert self.sp._calculate_velocity([1, 2, 3]) == Decimal("0")

    def test_constant_growth(self):
        # [10, 20, 40, 80] → growth_rates=[1.0, 1.0, 1.0] → accelerations=[0,0] → 0
        result = self.sp._calculate_velocity([10, 20, 40, 80])
        assert result == Decimal("0.00")

    def test_accelerating_growth(self):
        # Increasing growth rates → positive acceleration
        result = self.sp._calculate_velocity([10, 11, 15, 25])
        assert result > Decimal("0")

    def test_capped_at_1(self):
        result = self.sp._calculate_velocity([1, 10, 1000, 100000])
        assert result <= Decimal("1")

    def test_zeros_in_data(self):
        """Zeros in denominators should be skipped."""
        result = self.sp._calculate_velocity([0, 0, 10, 20])
        # Only one valid growth rate (10→20), so < 2 rates → returns 0
        assert result == Decimal("0")


# ============================================================
# 10. _determine_trend (pure function)
# ============================================================


class TestDetermineTrend:
    def setup_method(self):
        self.sp = SignalProcessor(make_mock_db())

    def test_upward_trend(self):
        direction, strength = self.sp._determine_trend(Decimal("0.5"), Decimal("0.3"))
        assert direction == "up"
        assert strength > Decimal("0")

    def test_downward_trend(self):
        direction, _strength = self.sp._determine_trend(Decimal("-0.5"), Decimal("-0.3"))
        assert direction == "down"

    def test_stable_trend(self):
        direction, _strength = self.sp._determine_trend(Decimal("0.05"), Decimal("0.0"))
        assert direction == "stable"

    def test_strength_capped_at_1(self):
        _direction, strength = self.sp._determine_trend(Decimal("5.0"), Decimal("5.0"))
        assert strength <= Decimal("1")

    def test_growth_weighted_70_percent(self):
        """Growth rate weighted 0.7, sentiment 0.3."""
        # combined = 0.2*0.7 + (-0.1)*0.3 = 0.14 - 0.03 = 0.11 → up
        direction, _ = self.sp._determine_trend(Decimal("0.2"), Decimal("-0.1"))
        assert direction == "up"

    def test_threshold_boundary_positive(self):
        # combined = 0.1*0.7 + 0.1*0.3 = 0.07+0.03 = 0.10 → exactly at boundary → up
        direction, _ = self.sp._determine_trend(Decimal("0.1"), Decimal("0.1"))
        assert direction == "up"

    def test_threshold_boundary_negative(self):
        # combined = -0.1*0.7 + -0.1*0.3 = -0.10 → exactly at boundary → down
        direction, _ = self.sp._determine_trend(Decimal("-0.1"), Decimal("-0.1"))
        assert direction == "down"

    def test_strength_is_quantized(self):
        _, strength = self.sp._determine_trend(Decimal("0.5"), Decimal("0.2"))
        assert strength == strength.quantize(Decimal("0.01"))


# ============================================================
# 11. calculate_price_impact (pure function)
# ============================================================


class TestCalculatePriceImpact:
    def setup_method(self):
        self.sp = SignalProcessor(make_mock_db())

    def test_no_signals_empty_impacts(self):
        signals = make_signals()
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert impacts == {}

    def test_sentiment_impact(self):
        signals = make_signals(sentiment_score=Decimal("0.8"))
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert "sentiment" in impacts
        # (0.8 - 0.5) * 10 = 3.0
        assert impacts["sentiment"] == 3.0

    def test_negative_sentiment_impact(self):
        signals = make_signals(sentiment_score=Decimal("0.2"))
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        # (0.2 - 0.5) * 10 = -3.0
        assert impacts["sentiment"] == -3.0

    def test_neutral_sentiment_zero_impact(self):
        signals = make_signals(sentiment_score=Decimal("0.5"))
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert impacts["sentiment"] == 0.0

    def test_volume_impact(self):
        signals = make_signals(mention_count_24h=200, mention_baseline=100)
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert "volume" in impacts
        # ratio=2.0, impact=(2.0-1)*5 = 5.0
        assert impacts["volume"] == 5.0

    def test_volume_no_baseline(self):
        signals = make_signals(mention_count_24h=100, mention_baseline=0)
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert "volume" not in impacts

    def test_viral_impact(self):
        signals = make_signals(viral_detected=True)
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert impacts["viral"] == 5.0

    def test_no_viral_no_impact(self):
        signals = make_signals(viral_detected=False)
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert "viral" not in impacts

    def test_trend_impact_when_trending(self):
        signals = make_signals(is_trending=True, trend_strength=Decimal("0.8"))
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert "trend" in impacts
        # 0.8 * 3 = 2.4
        assert impacts["trend"] == 2.4

    def test_no_trend_impact_when_not_trending(self):
        signals = make_signals(is_trending=False)
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert "trend" not in impacts

    def test_all_impacts_combined(self):
        signals = make_signals(
            sentiment_score=Decimal("0.7"),
            mention_count_24h=300,
            mention_baseline=100,
            viral_detected=True,
            is_trending=True,
            trend_strength=Decimal("0.5"),
        )
        product = make_product()
        impacts = self.sp.calculate_price_impact(signals, product)
        assert len(impacts) == 4  # sentiment, volume, viral, trend


# ============================================================
# 12. _get_trend_signals (orchestration)
# ============================================================


class TestGetTrendSignals:
    @pytest.mark.asyncio
    async def test_returns_trend_dict(self):
        db = make_mock_db()
        sp = SignalProcessor(db)

        sp._get_daily_mention_counts = AsyncMock(return_value=[10, 10, 10, 10, 10, 10, 10])
        sp._get_daily_sentiment = AsyncMock(return_value=[Decimal("0.5")] * 7)

        result = await sp._get_trend_signals(PRODUCT_ID)
        assert "direction" in result
        assert "strength" in result
        assert "velocity" in result
        assert "mention_growth_rate" in result
        assert "sentiment_momentum" in result
        assert "is_trending" in result

    @pytest.mark.asyncio
    async def test_trending_when_high_growth(self):
        db = make_mock_db()
        sp = SignalProcessor(db)

        # Growth from ~10/day to ~30/day
        sp._get_daily_mention_counts = AsyncMock(return_value=[10, 10, 10, 30, 30, 30, 30])
        sp._get_daily_sentiment = AsyncMock(return_value=[Decimal("0.5")] * 7)

        result = await sp._get_trend_signals(PRODUCT_ID)
        assert result["mention_growth_rate"] >= Decimal("0.5")
        assert result["is_trending"] is True

    @pytest.mark.asyncio
    async def test_not_trending_when_flat(self):
        db = make_mock_db()
        sp = SignalProcessor(db)

        sp._get_daily_mention_counts = AsyncMock(return_value=[10, 10, 10, 10, 10, 10, 10])
        sp._get_daily_sentiment = AsyncMock(return_value=[Decimal("0.5")] * 7)

        result = await sp._get_trend_signals(PRODUCT_ID)
        assert result["is_trending"] is False
