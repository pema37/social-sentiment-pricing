"""
Tests for services/analysis/sentiment_aggregator.py — SentimentAggregator

Covers:
- __init__: stores db
- _empty_aggregation: structure, None product_id
- _avg_sentiment: empty, single, multiple, missing raw_data
- _calculate_aggregation: avg/weighted sentiment, label classification,
  engagement weighting, topic extraction, positive/negative/neutral counts
- get_product_sentiment: returns aggregation, empty returns default
- get_user_sentiment: returns aggregation, empty returns default
- get_sentiment_velocity: improving/stable/declining, volume change,
  no previous data, no current data
- get_sentiment_by_source: groups by source, per-source metrics
"""

import os
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session",
    "models.social_mention",
    "sqlmodel",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

for _m in "db.session":
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for _pkg, _subdir in [
    ("services", "services"),
    ("services.analysis", "services/analysis"),
    ("models", "models"),
]:
    if _pkg not in sys.modules:
        _mod = ModuleType(_pkg)
        _mod.__path__ = [os.path.join(_backend_dir, _subdir)]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod


class _ColumnMock:
    def __lt__(self, other):
        return MagicMock()

    def __le__(self, other):
        return MagicMock()

    def __gt__(self, other):
        return MagicMock()

    def __ge__(self, other):
        return MagicMock()

    def __eq__(self, other):
        return MagicMock()

    def __ne__(self, other):
        return MagicMock()

    def __hash__(self):
        return id(self)


class _FakeSocialMention:
    product_id = _ColumnMock()
    user_id = _ColumnMock()
    collected_at = _ColumnMock()
    processed = _ColumnMock()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


_sm_stub = ModuleType("models.social_mention")
_sm_stub.SocialMention = _FakeSocialMention
sys.modules["models.social_mention"] = _sm_stub

_sqlmodel_stub = ModuleType("sqlmodel")
_sqlmodel_stub.select = MagicMock()
sys.modules["sqlmodel"] = _sqlmodel_stub

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.analysis.sentiment_aggregator import SentimentAggregator

# ---------------------------------------------------------------------------
# 3. Restore sys.modules
# ---------------------------------------------------------------------------
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m


# ===========================================================================
# Helpers
# ===========================================================================


def _make_session():
    s = AsyncMock()
    s.execute = AsyncMock()
    return s


def _make_aggregator(session=None):
    return SentimentAggregator(session or _make_session())


def _make_mention(**kw):
    defaults = {
        "engagement_count": 0,
        "raw_data": {"sentiment": {"compound": 0.0, "label": "neutral", "topics": []}},
        "source": "twitter",
    }
    defaults.update(kw)
    return _FakeSocialMention(**defaults)


def _mock_query_returns(session, mentions):
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = mentions
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result_mock)


def _mock_query_sequence(session, *mention_lists):
    results = []
    for mentions in mention_lists:
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = mentions
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        results.append(result_mock)
    session.execute = AsyncMock(side_effect=results)


# ===========================================================================
# Tests
# ===========================================================================


class TestInit:
    def test_stores_db(self):
        session = _make_session()
        agg = SentimentAggregator(session)
        assert agg.db is session


class TestEmptyAggregation:
    def test_structure(self):
        agg = _make_aggregator()
        pid = uuid4()
        result = agg._empty_aggregation(pid, 24)

        assert result["product_id"] == str(pid)
        assert result["period_hours"] == 24
        assert result["mention_count"] == 0
        assert result["avg_sentiment"] == 0.0
        assert result["weighted_sentiment"] == 0.0
        assert result["positive_count"] == 0
        assert result["negative_count"] == 0
        assert result["neutral_count"] == 0
        assert result["positive_ratio"] == 0.0
        assert result["negative_ratio"] == 0.0
        assert result["sentiment_label"] == "neutral"
        assert result["top_topics"] == []
        assert "computed_at" in result

    def test_none_product_id(self):
        agg = _make_aggregator()
        result = agg._empty_aggregation(None, 12)
        assert result["product_id"] is None


class TestAvgSentiment:
    def test_empty_returns_none(self):
        agg = _make_aggregator()
        assert agg._avg_sentiment([]) is None

    def test_single_mention(self):
        agg = _make_aggregator()
        m = _make_mention(raw_data={"sentiment": {"compound": 0.8}})
        result = agg._avg_sentiment([m])
        assert result == 0.8

    def test_multiple_mentions(self):
        agg = _make_aggregator()
        mentions = [
            _make_mention(raw_data={"sentiment": {"compound": 0.6}}),
            _make_mention(raw_data={"sentiment": {"compound": 0.4}}),
            _make_mention(raw_data={"sentiment": {"compound": -0.2}}),
        ]
        result = agg._avg_sentiment(mentions)
        expected = (0.6 + 0.4 + -0.2) / 3
        assert abs(result - expected) < 0.001

    def test_missing_raw_data(self):
        agg = _make_aggregator()
        m = _make_mention(raw_data=None)
        result = agg._avg_sentiment([m])
        assert result == 0.0  # defaults to compound=0

    def test_missing_sentiment_key(self):
        agg = _make_aggregator()
        m = _make_mention(raw_data={"other": "stuff"})
        result = agg._avg_sentiment([m])
        assert result == 0.0


class TestCalculateAggregation:
    def test_basic_aggregation(self):
        agg = _make_aggregator()
        pid = uuid4()
        mentions = [
            _make_mention(raw_data={"sentiment": {"compound": 0.5, "label": "positive", "topics": ["quality"]}}),
            _make_mention(raw_data={"sentiment": {"compound": -0.4, "label": "negative", "topics": ["price"]}}),
            _make_mention(raw_data={"sentiment": {"compound": 0.0, "label": "neutral", "topics": []}}),
        ]

        result = agg._calculate_aggregation(mentions, pid, 24)

        assert result["product_id"] == str(pid)
        assert result["mention_count"] == 3
        assert result["positive_count"] == 1
        assert result["negative_count"] == 1
        assert result["neutral_count"] == 1
        assert abs(result["avg_sentiment"] - round((0.5 + -0.4 + 0.0) / 3, 3)) < 0.01

    def test_positive_label(self):
        agg = _make_aggregator()
        mentions = [
            _make_mention(raw_data={"sentiment": {"compound": 0.8, "label": "positive"}}),
            _make_mention(raw_data={"sentiment": {"compound": 0.6, "label": "positive"}}),
        ]
        result = agg._calculate_aggregation(mentions, uuid4(), 24)
        assert result["sentiment_label"] == "positive"

    def test_negative_label(self):
        agg = _make_aggregator()
        mentions = [
            _make_mention(raw_data={"sentiment": {"compound": -0.5, "label": "negative"}}),
            _make_mention(raw_data={"sentiment": {"compound": -0.7, "label": "negative"}}),
        ]
        result = agg._calculate_aggregation(mentions, uuid4(), 24)
        assert result["sentiment_label"] == "negative"

    def test_neutral_label(self):
        agg = _make_aggregator()
        mentions = [
            _make_mention(raw_data={"sentiment": {"compound": 0.1, "label": "neutral"}}),
            _make_mention(raw_data={"sentiment": {"compound": -0.1, "label": "neutral"}}),
        ]
        result = agg._calculate_aggregation(mentions, uuid4(), 24)
        assert result["sentiment_label"] == "neutral"

    def test_engagement_weighting(self):
        agg = _make_aggregator()
        mentions = [
            _make_mention(
                engagement_count=1000,
                raw_data={"sentiment": {"compound": 0.9, "label": "positive"}},
            ),
            _make_mention(
                engagement_count=0,
                raw_data={"sentiment": {"compound": -0.5, "label": "negative"}},
            ),
        ]
        result = agg._calculate_aggregation(mentions, uuid4(), 24)
        # Weighted should be pulled toward the high-engagement positive mention
        assert result["weighted_sentiment"] > result["avg_sentiment"]

    def test_topic_extraction(self):
        agg = _make_aggregator()
        mentions = [
            _make_mention(
                raw_data={"sentiment": {"compound": 0.5, "label": "positive", "topics": ["quality", "shipping"]}}
            ),
            _make_mention(
                raw_data={"sentiment": {"compound": 0.3, "label": "positive", "topics": ["quality", "design"]}}
            ),
            _make_mention(raw_data={"sentiment": {"compound": 0.1, "label": "neutral", "topics": ["shipping"]}}),
        ]
        result = agg._calculate_aggregation(mentions, uuid4(), 24)
        # "quality" appears 2x, "shipping" 2x, "design" 1x
        assert "quality" in result["top_topics"]
        assert "shipping" in result["top_topics"]

    def test_top_topics_capped_at_5(self):
        agg = _make_aggregator()
        topics = [f"topic_{i}" for i in range(10)]
        mentions = [_make_mention(raw_data={"sentiment": {"compound": 0.0, "label": "neutral", "topics": topics}})]
        result = agg._calculate_aggregation(mentions, uuid4(), 24)
        assert len(result["top_topics"]) <= 5

    def test_ratios(self):
        agg = _make_aggregator()
        mentions = [
            _make_mention(raw_data={"sentiment": {"compound": 0.5, "label": "positive"}}),
            _make_mention(raw_data={"sentiment": {"compound": 0.3, "label": "positive"}}),
            _make_mention(raw_data={"sentiment": {"compound": -0.5, "label": "negative"}}),
            _make_mention(raw_data={"sentiment": {"compound": 0.0, "label": "neutral"}}),
        ]
        result = agg._calculate_aggregation(mentions, uuid4(), 24)
        assert result["positive_ratio"] == 0.5
        assert result["negative_ratio"] == 0.25

    def test_none_product_id(self):
        agg = _make_aggregator()
        mentions = [_make_mention()]
        result = agg._calculate_aggregation(mentions, None, 24)
        assert result["product_id"] is None

    def test_none_engagement_count(self):
        agg = _make_aggregator()
        mentions = [
            _make_mention(engagement_count=None, raw_data={"sentiment": {"compound": 0.5, "label": "positive"}}),
        ]
        result = agg._calculate_aggregation(mentions, uuid4(), 24)
        assert result["mention_count"] == 1  # doesn't crash


class TestGetProductSentiment:
    @pytest.mark.asyncio
    async def test_with_mentions(self):
        session = _make_session()
        agg = SentimentAggregator(session)
        mentions = [
            _make_mention(raw_data={"sentiment": {"compound": 0.7, "label": "positive", "topics": []}}),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_product_sentiment(uuid4(), hours=24)

        assert result["mention_count"] == 1
        assert result["avg_sentiment"] == 0.7

    @pytest.mark.asyncio
    async def test_empty_returns_default(self):
        session = _make_session()
        agg = SentimentAggregator(session)
        _mock_query_returns(session, [])

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_product_sentiment(uuid4())

        assert result["mention_count"] == 0
        assert result["avg_sentiment"] == 0.0
        assert result["sentiment_label"] == "neutral"


class TestGetUserSentiment:
    @pytest.mark.asyncio
    async def test_with_mentions(self):
        session = _make_session()
        agg = SentimentAggregator(session)
        mentions = [
            _make_mention(raw_data={"sentiment": {"compound": -0.5, "label": "negative", "topics": []}}),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_user_sentiment(uuid4())

        assert result["mention_count"] == 1
        assert result["product_id"] is None  # user-level aggregation

    @pytest.mark.asyncio
    async def test_empty(self):
        session = _make_session()
        agg = SentimentAggregator(session)
        _mock_query_returns(session, [])

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_user_sentiment(uuid4())

        assert result["mention_count"] == 0


class TestGetSentimentVelocity:
    @pytest.mark.asyncio
    async def test_improving_trend(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        current = [_make_mention(raw_data={"sentiment": {"compound": 0.8}})]
        previous = [_make_mention(raw_data={"sentiment": {"compound": 0.2}})]
        _mock_query_sequence(session, current, previous)

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_velocity(uuid4())

        assert result["trend"] == "improving"
        assert result["velocity"] > 0
        assert result["current_sentiment"] == 0.8
        assert result["previous_sentiment"] == 0.2

    @pytest.mark.asyncio
    async def test_declining_trend(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        current = [_make_mention(raw_data={"sentiment": {"compound": 0.1}})]
        previous = [_make_mention(raw_data={"sentiment": {"compound": 0.8}})]
        _mock_query_sequence(session, current, previous)

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_velocity(uuid4())

        assert result["trend"] == "declining"
        assert result["velocity"] < 0

    @pytest.mark.asyncio
    async def test_stable_trend(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        current = [_make_mention(raw_data={"sentiment": {"compound": 0.5}})]
        previous = [_make_mention(raw_data={"sentiment": {"compound": 0.5}})]
        _mock_query_sequence(session, current, previous)

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_velocity(uuid4())

        assert result["trend"] == "stable"
        assert result["velocity"] == 0.0

    @pytest.mark.asyncio
    async def test_no_previous_data(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        current = [_make_mention(raw_data={"sentiment": {"compound": 0.5}})]
        _mock_query_sequence(session, current, [])

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_velocity(uuid4())

        assert result["previous_sentiment"] == 0.0
        assert result["velocity"] == 0.0  # None previous → velocity=0

    @pytest.mark.asyncio
    async def test_no_current_data(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        previous = [_make_mention(raw_data={"sentiment": {"compound": 0.5}})]
        _mock_query_sequence(session, [], previous)

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_velocity(uuid4())

        assert result["current_sentiment"] == 0.0

    @pytest.mark.asyncio
    async def test_volume_change_increase(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        current = [_make_mention(), _make_mention(), _make_mention()]
        previous = [_make_mention()]
        _mock_query_sequence(session, current, previous)

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_velocity(uuid4())

        assert result["volume_change"] == 2.0  # (3-1)/1

    @pytest.mark.asyncio
    async def test_volume_change_no_previous(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        current = [_make_mention()]
        _mock_query_sequence(session, current, [])

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_velocity(uuid4())

        assert result["volume_change"] == 1.0  # curr>0, prev=0

    @pytest.mark.asyncio
    async def test_volume_change_both_empty(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        _mock_query_sequence(session, [], [])

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_velocity(uuid4())

        assert result["volume_change"] == 0.0


class TestGetSentimentBySource:
    @pytest.mark.asyncio
    async def test_groups_by_source(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        mentions = [
            _make_mention(
                source="twitter", raw_data={"sentiment": {"compound": 0.8, "label": "positive", "topics": []}}
            ),
            _make_mention(
                source="twitter", raw_data={"sentiment": {"compound": 0.6, "label": "positive", "topics": []}}
            ),
            _make_mention(
                source="reddit", raw_data={"sentiment": {"compound": -0.3, "label": "negative", "topics": []}}
            ),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_by_source(uuid4())

        assert "twitter" in result
        assert "reddit" in result
        assert result["twitter"]["mention_count"] == 2
        assert result["reddit"]["mention_count"] == 1

    @pytest.mark.asyncio
    async def test_empty_returns_empty_dict(self):
        session = _make_session()
        agg = SentimentAggregator(session)
        _mock_query_returns(session, [])

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_by_source(uuid4())

        assert result == {}

    @pytest.mark.asyncio
    async def test_per_source_sentiment_label(self):
        session = _make_session()
        agg = SentimentAggregator(session)

        mentions = [
            _make_mention(
                source="twitter", raw_data={"sentiment": {"compound": 0.8, "label": "positive", "topics": []}}
            ),
            _make_mention(
                source="reddit", raw_data={"sentiment": {"compound": -0.8, "label": "negative", "topics": []}}
            ),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.sentiment_aggregator.select"):
            result = await agg.get_sentiment_by_source(uuid4())

        assert result["twitter"]["sentiment_label"] == "positive"
        assert result["reddit"]["sentiment_label"] == "negative"
