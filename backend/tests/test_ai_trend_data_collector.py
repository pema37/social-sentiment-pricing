"""
Tests for services/ai_trend_analysis/data_collector.py

Covers all methods in DataCollector:
- get_products (with/without product_ids filter)
- get_sentiment_history (date filtering, product filtering, dict mapping)
- get_product_sentiment (averages, trend detection, empty results)
- get_mentions_summary (date filtering, product filtering, dict mapping)
- get_product_mentions (single product)
- get_negative_mentions (threshold filtering)
- get_competitor_data (with/without product_ids filter, dict mapping)
- get_product_competitors (single product)
- get_current_alerts (success + exception handling)
- get_sentiment_drops (placeholder)
- get_recent_competitor_activities (placeholder)
"""

import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Import isolation ──────────────────────────────────────────────
for mod in ["db.session"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from services.ai_trend_analysis.data_collector import DataCollector


# ── Helpers ───────────────────────────────────────────────────────

def _make_mock_db():
    """Create a mock AsyncSession with chainable execute/scalars/all."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    db.execute.return_value = mock_result
    return db, mock_result, mock_scalars


def _make_sentiment(score=0.5, magnitude=0.3, product_id="prod-1", analyzed_at=None):
    s = MagicMock()
    s.product_id = product_id
    s.score = score
    s.magnitude = magnitude
    s.analyzed_at = analyzed_at or datetime(2026, 2, 1, tzinfo=timezone.utc)
    return s


def _make_mention(
    product_id="prod-1",
    platform="reddit",
    content="Test mention",
    sentiment_score=0.5,
    collected_at=None,
):
    m = MagicMock()
    m.product_id = product_id
    m.platform = platform
    m.content = content
    m.sentiment_score = sentiment_score
    m.collected_at = collected_at or datetime(2026, 2, 1, tzinfo=timezone.utc)
    return m


def _make_competitor(product_id="prod-1", name="Amazon", price=49.99, updated_at=None):
    c = MagicMock()
    c.product_id = product_id
    c.competitor_name = name
    c.price = price
    c.updated_at = updated_at or datetime(2026, 2, 1, tzinfo=timezone.utc)
    return c


def _make_product(name="Widget", base_price=29.99, user_id="user-1", category="Electronics"):
    p = MagicMock()
    p.id = "prod-1"
    p.name = name
    p.base_price = base_price
    p.user_id = user_id
    p.category = category
    return p


# ==================================================================
# get_products
# ==================================================================

class TestGetProducts:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        result = await collector.get_products(user_id="user-1")
        assert result == []
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_products(self):
        db, _, scalars = _make_mock_db()
        products = [_make_product(), _make_product(name="Gadget")]
        scalars.all.return_value = products
        collector = DataCollector(db)
        result = await collector.get_products(user_id="user-1")
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_with_product_ids_filter(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = [_make_product()]
        collector = DataCollector(db)
        result = await collector.get_products(user_id="user-1", product_ids=["prod-1"])
        assert len(result) == 1
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_without_product_ids_filter(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        await collector.get_products(user_id="user-1", product_ids=None)
        db.execute.assert_awaited_once()


# ==================================================================
# get_sentiment_history
# ==================================================================

class TestGetSentimentHistory:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        result = await collector.get_sentiment_history(user_id="user-1", days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_mapped_dicts(self):
        db, _, scalars = _make_mock_db()
        s = _make_sentiment(score=0.75, product_id="prod-1")
        scalars.all.return_value = [s]
        collector = DataCollector(db)
        result = await collector.get_sentiment_history(user_id="user-1", days=30)
        assert len(result) == 1
        assert result[0]["product_id"] == "prod-1"
        assert result[0]["score"] == 0.75
        assert "created_at" in result[0]
        assert "magnitude" in result[0]

    @pytest.mark.asyncio
    async def test_none_score_defaults_to_zero(self):
        db, _, scalars = _make_mock_db()
        s = _make_sentiment(score=None)
        scalars.all.return_value = [s]
        collector = DataCollector(db)
        result = await collector.get_sentiment_history(user_id="user-1", days=30)
        assert result[0]["score"] == 0

    @pytest.mark.asyncio
    async def test_no_magnitude_attribute_defaults_to_zero(self):
        db, _, scalars = _make_mock_db()
        s = _make_sentiment()
        del s.magnitude  # Remove attribute
        scalars.all.return_value = [s]
        collector = DataCollector(db)
        result = await collector.get_sentiment_history(user_id="user-1", days=30)
        assert result[0]["magnitude"] == 0

    @pytest.mark.asyncio
    async def test_magnitude_none_defaults_to_zero(self):
        db, _, scalars = _make_mock_db()
        s = _make_sentiment(magnitude=None)
        scalars.all.return_value = [s]
        collector = DataCollector(db)
        result = await collector.get_sentiment_history(user_id="user-1", days=30)
        assert result[0]["magnitude"] == 0

    @pytest.mark.asyncio
    async def test_with_product_ids_filter(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        await collector.get_sentiment_history(
            user_id="user-1", days=30, product_ids=["prod-1"]
        )
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_product_id_converted_to_string(self):
        db, _, scalars = _make_mock_db()
        import uuid
        pid = uuid.uuid4()
        s = _make_sentiment(product_id=pid)
        scalars.all.return_value = [s]
        collector = DataCollector(db)
        result = await collector.get_sentiment_history(user_id="user-1", days=7)
        assert result[0]["product_id"] == str(pid)


# ==================================================================
# get_product_sentiment
# ==================================================================

class TestGetProductSentiment:
    @pytest.mark.asyncio
    async def test_empty_sentiments_returns_defaults(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        assert result["current"] == 0
        assert result["avg_7d"] == 0
        assert result["avg_30d"] == 0
        assert result["trend"] == "stable"
        assert result["avg_volume"] == 0
        assert result["volume_change"] == 0

    @pytest.mark.asyncio
    async def test_single_sentiment_returns_values(self):
        db, _, scalars = _make_mock_db()
        s = _make_sentiment(score=0.8)
        scalars.all.return_value = [s]
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        assert result["current"] == 0.8
        assert result["avg_7d"] == 0.8
        assert result["avg_30d"] == 0.8

    @pytest.mark.asyncio
    async def test_none_score_treated_as_zero(self):
        db, _, scalars = _make_mock_db()
        s = _make_sentiment(score=None)
        scalars.all.return_value = [s]
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        assert result["current"] == 0

    @pytest.mark.asyncio
    async def test_trend_rising(self):
        """Recent scores higher than older → rising."""
        db, _, scalars = _make_mock_db()
        # 7 recent high + 7 older low = rising
        sentiments = [_make_sentiment(score=0.9) for _ in range(7)]
        sentiments += [_make_sentiment(score=0.3) for _ in range(7)]
        scalars.all.return_value = sentiments
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        assert result["trend"] == "rising"

    @pytest.mark.asyncio
    async def test_trend_falling(self):
        """Recent scores lower than older → falling."""
        db, _, scalars = _make_mock_db()
        sentiments = [_make_sentiment(score=0.2) for _ in range(7)]
        sentiments += [_make_sentiment(score=0.8) for _ in range(7)]
        scalars.all.return_value = sentiments
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        assert result["trend"] == "falling"

    @pytest.mark.asyncio
    async def test_trend_stable(self):
        """Similar scores → stable."""
        db, _, scalars = _make_mock_db()
        sentiments = [_make_sentiment(score=0.5) for _ in range(14)]
        scalars.all.return_value = sentiments
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        assert result["trend"] == "stable"

    @pytest.mark.asyncio
    async def test_trend_stable_fewer_than_7(self):
        """Fewer than 7 sentiments → default stable."""
        db, _, scalars = _make_mock_db()
        sentiments = [_make_sentiment(score=0.9) for _ in range(5)]
        scalars.all.return_value = sentiments
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        assert result["trend"] == "stable"

    @pytest.mark.asyncio
    async def test_trend_exactly_7_sentiments(self):
        """Exactly 7 → no older data, recent == older, stable."""
        db, _, scalars = _make_mock_db()
        sentiments = [_make_sentiment(score=0.6) for _ in range(7)]
        scalars.all.return_value = sentiments
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        assert result["trend"] == "stable"

    @pytest.mark.asyncio
    async def test_avg_volume_calculated(self):
        db, _, scalars = _make_mock_db()
        sentiments = [_make_sentiment() for _ in range(10)]
        scalars.all.return_value = sentiments
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        assert result["avg_volume"] == 10 / 30

    @pytest.mark.asyncio
    async def test_avg_volume_zero_days(self):
        """days=0 should not cause ZeroDivisionError."""
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=0)
        assert result["avg_volume"] == 0

    @pytest.mark.asyncio
    async def test_avg_7d_with_fewer_than_7(self):
        """avg_7d with 3 scores should average those 3."""
        db, _, scalars = _make_mock_db()
        sentiments = [
            _make_sentiment(score=0.6),
            _make_sentiment(score=0.8),
            _make_sentiment(score=1.0),
        ]
        scalars.all.return_value = sentiments
        collector = DataCollector(db)
        result = await collector.get_product_sentiment(product_id="prod-1", days=30)
        # sum([0.6, 0.8, 1.0]) / min(7, 3) = 2.4 / 3 = 0.8
        assert abs(result["avg_7d"] - 0.8) < 0.01


# ==================================================================
# get_mentions_summary
# ==================================================================

class TestGetMentionsSummary:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        result = await collector.get_mentions_summary(user_id="user-1", days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_mapped_dicts(self):
        db, _, scalars = _make_mock_db()
        m = _make_mention(platform="twitter", sentiment_score=0.65)
        scalars.all.return_value = [m]
        collector = DataCollector(db)
        result = await collector.get_mentions_summary(user_id="user-1", days=30)
        assert len(result) == 1
        assert result[0]["platform"] == "twitter"
        assert result[0]["sentiment_score"] == 0.65
        assert "content" in result[0]
        assert "created_at" in result[0]

    @pytest.mark.asyncio
    async def test_content_truncated_at_200(self):
        db, _, scalars = _make_mock_db()
        m = _make_mention(content="A" * 500)
        scalars.all.return_value = [m]
        collector = DataCollector(db)
        result = await collector.get_mentions_summary(user_id="user-1", days=30)
        assert len(result[0]["content"]) == 200

    @pytest.mark.asyncio
    async def test_none_content_defaults_to_empty(self):
        db, _, scalars = _make_mock_db()
        m = _make_mention(content=None)
        scalars.all.return_value = [m]
        collector = DataCollector(db)
        result = await collector.get_mentions_summary(user_id="user-1", days=30)
        assert result[0]["content"] == ""

    @pytest.mark.asyncio
    async def test_none_sentiment_score_defaults_to_zero(self):
        db, _, scalars = _make_mock_db()
        m = _make_mention(sentiment_score=None)
        scalars.all.return_value = [m]
        collector = DataCollector(db)
        result = await collector.get_mentions_summary(user_id="user-1", days=30)
        assert result[0]["sentiment_score"] == 0

    @pytest.mark.asyncio
    async def test_with_product_ids_filter(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        await collector.get_mentions_summary(
            user_id="user-1", days=30, product_ids=["prod-1"]
        )
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_product_id_converted_to_string(self):
        db, _, scalars = _make_mock_db()
        import uuid
        pid = uuid.uuid4()
        m = _make_mention(product_id=pid)
        scalars.all.return_value = [m]
        collector = DataCollector(db)
        result = await collector.get_mentions_summary(user_id="user-1", days=7)
        assert result[0]["product_id"] == str(pid)


# ==================================================================
# get_product_mentions
# ==================================================================

class TestGetProductMentions:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        result = await collector.get_product_mentions(product_id="prod-1", days=30)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_mention_objects(self):
        db, _, scalars = _make_mock_db()
        m = _make_mention()
        scalars.all.return_value = [m]
        collector = DataCollector(db)
        result = await collector.get_product_mentions(product_id="prod-1", days=30)
        assert len(result) == 1
        assert result[0] is m

    @pytest.mark.asyncio
    async def test_calls_execute(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        await collector.get_product_mentions(product_id="prod-1", days=7)
        db.execute.assert_awaited_once()


# ==================================================================
# get_negative_mentions
# ==================================================================

class TestGetNegativeMentions:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        result = await collector.get_negative_mentions(user_id="user-1", days=7)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_mention_objects(self):
        db, _, scalars = _make_mock_db()
        m = _make_mention(sentiment_score=-0.8)
        scalars.all.return_value = [m]
        collector = DataCollector(db)
        result = await collector.get_negative_mentions(user_id="user-1", days=7)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_calls_execute(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        await collector.get_negative_mentions(user_id="user-1", days=30)
        db.execute.assert_awaited_once()


# ==================================================================
# get_competitor_data
# ==================================================================

class TestGetCompetitorData:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        result = await collector.get_competitor_data(user_id="user-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_mapped_dicts(self):
        db, _, scalars = _make_mock_db()
        c = _make_competitor(name="BestBuy", price=59.99)
        scalars.all.return_value = [c]
        collector = DataCollector(db)
        result = await collector.get_competitor_data(user_id="user-1")
        assert len(result) == 1
        assert result[0]["competitor_name"] == "BestBuy"
        assert result[0]["competitor_price"] == 59.99
        assert "last_updated" in result[0]

    @pytest.mark.asyncio
    async def test_none_price_defaults_to_zero(self):
        db, _, scalars = _make_mock_db()
        c = _make_competitor(price=None)
        scalars.all.return_value = [c]
        collector = DataCollector(db)
        result = await collector.get_competitor_data(user_id="user-1")
        assert result[0]["competitor_price"] == 0

    @pytest.mark.asyncio
    async def test_no_competitor_name_attr_defaults_to_unknown(self):
        db, _, scalars = _make_mock_db()
        c = _make_competitor()
        del c.competitor_name
        scalars.all.return_value = [c]
        collector = DataCollector(db)
        result = await collector.get_competitor_data(user_id="user-1")
        assert result[0]["competitor_name"] == "Unknown"

    @pytest.mark.asyncio
    async def test_with_product_ids_filter(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        await collector.get_competitor_data(
            user_id="user-1", product_ids=["prod-1"]
        )
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_product_id_converted_to_string(self):
        db, _, scalars = _make_mock_db()
        import uuid
        pid = uuid.uuid4()
        c = _make_competitor(product_id=pid)
        scalars.all.return_value = [c]
        collector = DataCollector(db)
        result = await collector.get_competitor_data(user_id="user-1")
        assert result[0]["product_id"] == str(pid)


# ==================================================================
# get_product_competitors
# ==================================================================

class TestGetProductCompetitors:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        result = await collector.get_product_competitors(product_id="prod-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_competitor_objects(self):
        db, _, scalars = _make_mock_db()
        c = _make_competitor()
        scalars.all.return_value = [c]
        collector = DataCollector(db)
        result = await collector.get_product_competitors(product_id="prod-1")
        assert len(result) == 1
        assert result[0] is c

    @pytest.mark.asyncio
    async def test_calls_execute(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        await collector.get_product_competitors(product_id="prod-1")
        db.execute.assert_awaited_once()


# ==================================================================
# get_current_alerts
# ==================================================================

class TestGetCurrentAlerts:
    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        db, _, scalars = _make_mock_db()
        scalars.all.return_value = []
        collector = DataCollector(db)
        with patch("services.ai_trend_analysis.data_collector.select"):
            result = await collector.get_current_alerts(user_id="user-1")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_alert_objects(self):
        db, _, scalars = _make_mock_db()
        alert = MagicMock()
        alert.alert_type = "price_drop"
        alert.message = "Competitor dropped price"
        scalars.all.return_value = [alert]
        collector = DataCollector(db)
        result = await collector.get_current_alerts(user_id="user-1")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_empty_list(self):
        db = AsyncMock()
        db.execute.side_effect = Exception("Import error")
        collector = DataCollector(db)
        result = await collector.get_current_alerts(user_id="user-1")
        assert result == []


# ==================================================================
# Placeholder methods
# ==================================================================

class TestPlaceholderMethods:
    @pytest.mark.asyncio
    async def test_get_sentiment_drops_returns_empty(self):
        db, _, _ = _make_mock_db()
        collector = DataCollector(db)
        result = await collector.get_sentiment_drops(user_id="user-1", days=7)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_recent_competitor_activities_returns_empty(self):
        db, _, _ = _make_mock_db()
        collector = DataCollector(db)
        result = await collector.get_recent_competitor_activities(user_id="user-1")
        assert result == []


        