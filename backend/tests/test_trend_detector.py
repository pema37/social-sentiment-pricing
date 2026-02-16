"""
Tests for services/analysis/trend_detector.py — TrendDetector

Covers:
- __init__: db, aggregator, thresholds
- detect_all: orchestrates all checks, returns alerts + metrics
- detect_volume_spike: spike detection, severity levels, no spike
- detect_sentiment_shift: drop (critical/high), spike (info/high), no shift
- detect_viral_mentions: viral with positive/negative/mixed sentiment, no viral
- get_pricing_signal: increase/decrease/hold signals, strength capping,
  adjustment capping, factor combinations
"""

import sys
import os
from types import ModuleType
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session",
    "models.social_mention",
    "services.analysis.sentiment_aggregator",
    "sqlmodel",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

for _m in ("db.session"):
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

# Stub models.social_mention
_sm_stub = ModuleType("models.social_mention")


class _ColumnMock:
    def __lt__(self, other): return MagicMock()
    def __le__(self, other): return MagicMock()
    def __gt__(self, other): return MagicMock()
    def __ge__(self, other): return MagicMock()
    def __eq__(self, other): return MagicMock()
    def __ne__(self, other): return MagicMock()
    def __hash__(self): return id(self)


class _FakeSocialMention:
    product_id = _ColumnMock()
    collected_at = _ColumnMock()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


_sm_stub.SocialMention = _FakeSocialMention
sys.modules["models.social_mention"] = _sm_stub

# Stub sentiment_aggregator
_agg_stub = ModuleType("services.analysis.sentiment_aggregator")


class _FakeSentimentAggregator:
    def __init__(self, db):
        self.db = db
        self.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.0,
            "volume_change": 0.0,
            "trend": "stable",
            "current_sentiment": 0.0,
            "previous_sentiment": 0.0,
        })
        self.get_product_sentiment = AsyncMock(return_value={
            "avg_sentiment": 0.0,
            "mention_count": 0,
        })


_agg_stub.SentimentAggregator = _FakeSentimentAggregator
sys.modules["services.analysis.sentiment_aggregator"] = _agg_stub

# Stub sqlmodel
_sqlmodel_stub = ModuleType("sqlmodel")
_sqlmodel_stub.select = MagicMock()
sys.modules["sqlmodel"] = _sqlmodel_stub

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.analysis.trend_detector import TrendDetector

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


def _make_detector(session=None):
    return TrendDetector(session or _make_session())


def _mock_query_returns(session, mentions_list):
    """Configure session.execute to return mentions via scalars().all()."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = mentions_list
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result_mock)


def _mock_query_returns_sequence(session, *mention_lists):
    """Configure session.execute to return different results on successive calls."""
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

class TestTrendDetectorInit:
    def test_stores_db(self):
        session = _make_session()
        td = TrendDetector(session)
        assert td.db is session

    def test_creates_aggregator(self):
        td = _make_detector()
        assert td.aggregator is not None

    def test_default_thresholds(self):
        td = _make_detector()
        assert td.volume_spike_threshold == 2.0
        assert td.sentiment_shift_threshold == 0.3
        assert td.viral_engagement_threshold == 1000


class TestDetectAll:
    @pytest.mark.asyncio
    async def test_no_alerts(self):
        td = _make_detector()
        td.detect_volume_spike = AsyncMock(return_value=None)
        td.detect_sentiment_shift = AsyncMock(return_value=None)
        td.detect_viral_mentions = AsyncMock(return_value=None)

        pid = uuid4()
        result = await td.detect_all(pid)

        assert result["product_id"] == str(pid)
        assert result["has_alerts"] is False
        assert result["alerts"] == []
        assert "metrics" in result
        assert "checked_at" in result

    @pytest.mark.asyncio
    async def test_with_alerts(self):
        td = _make_detector()
        vol_alert = {"type": "volume_spike", "severity": "high", "message": "2x"}
        sent_alert = {"type": "sentiment_drop", "severity": "critical", "message": "drop"}
        td.detect_volume_spike = AsyncMock(return_value=vol_alert)
        td.detect_sentiment_shift = AsyncMock(return_value=sent_alert)
        td.detect_viral_mentions = AsyncMock(return_value=None)

        result = await td.detect_all(uuid4())

        assert result["has_alerts"] is True
        assert len(result["alerts"]) == 2
        assert result["alerts"][0]["type"] == "volume_spike"
        assert result["alerts"][1]["type"] == "sentiment_drop"

    @pytest.mark.asyncio
    async def test_metrics_from_velocity(self):
        td = _make_detector()
        td.detect_volume_spike = AsyncMock(return_value=None)
        td.detect_sentiment_shift = AsyncMock(return_value=None)
        td.detect_viral_mentions = AsyncMock(return_value=None)
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.15,
            "volume_change": 1.5,
            "trend": "improving",
            "current_sentiment": 0.6,
        })

        result = await td.detect_all(uuid4())
        assert result["metrics"]["sentiment_velocity"] == 0.15
        assert result["metrics"]["volume_change"] == 1.5
        assert result["metrics"]["trend"] == "improving"


class TestDetectVolumeSpike:
    @pytest.mark.asyncio
    async def test_no_spike(self):
        session = _make_session()
        td = TrendDetector(session)
        # Current: 2 mentions, Baseline: 14 mentions (avg ~2 per period) → no spike
        _mock_query_returns_sequence(session, [1, 2], list(range(14)))

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_volume_spike(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_medium_spike(self):
        session = _make_session()
        td = TrendDetector(session)
        # Current: 10 mentions, Baseline: 7 mentions (avg=1 per 6hr period) → 10x
        # baseline_periods = (48-6)/6 = 7, baseline_avg = 7/7 = 1
        current = list(range(10))
        baseline = list(range(7))
        _mock_query_returns_sequence(session, current, baseline)

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_volume_spike(uuid4())

        assert result is not None
        assert result["type"] == "volume_spike"
        assert result["severity"] == "critical"  # 10x > 5

    @pytest.mark.asyncio
    async def test_high_spike_severity(self):
        session = _make_session()
        td = TrendDetector(session)
        # Current: 4, Baseline: 7 → avg=1, multiplier=4 → "high" (3<4<5)
        _mock_query_returns_sequence(session, list(range(4)), list(range(7)))

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_volume_spike(uuid4())

        assert result is not None
        assert result["severity"] == "high"

    @pytest.mark.asyncio
    async def test_zero_baseline(self):
        session = _make_session()
        td = TrendDetector(session)
        _mock_query_returns_sequence(session, [1, 2, 3], [])

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_volume_spike(uuid4())
        # baseline_avg = 0, so condition (baseline_avg > 0) fails
        assert result is None


class TestDetectSentimentShift:
    @pytest.mark.asyncio
    async def test_no_shift(self):
        td = _make_detector()
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.0, "volume_change": 0.0,
            "trend": "stable", "current_sentiment": 0.5, "previous_sentiment": 0.4,
        })

        result = await td.detect_sentiment_shift(uuid4())
        assert result is None  # 0.1 < 0.3 threshold

    @pytest.mark.asyncio
    async def test_sentiment_drop_high(self):
        td = _make_detector()
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": -0.35, "volume_change": 0.0,
            "trend": "declining", "current_sentiment": 0.1, "previous_sentiment": 0.45,
        })

        result = await td.detect_sentiment_shift(uuid4())
        assert result is not None
        assert result["type"] == "sentiment_drop"
        assert result["severity"] == "high"
        assert result["data"]["shift"] == -0.35

    @pytest.mark.asyncio
    async def test_sentiment_drop_critical(self):
        td = _make_detector()
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": -0.6, "volume_change": 0.0,
            "trend": "declining", "current_sentiment": -0.2, "previous_sentiment": 0.4,
        })

        result = await td.detect_sentiment_shift(uuid4())
        assert result["type"] == "sentiment_drop"
        assert result["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_sentiment_spike_info(self):
        td = _make_detector()
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.35, "volume_change": 0.0,
            "trend": "improving", "current_sentiment": 0.7, "previous_sentiment": 0.35,
        })

        result = await td.detect_sentiment_shift(uuid4())
        assert result["type"] == "sentiment_spike"
        assert result["severity"] == "info"

    @pytest.mark.asyncio
    async def test_sentiment_spike_high(self):
        td = _make_detector()
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.55, "volume_change": 0.0,
            "trend": "improving", "current_sentiment": 0.8, "previous_sentiment": 0.25,
        })

        result = await td.detect_sentiment_shift(uuid4())
        assert result["type"] == "sentiment_spike"
        assert result["severity"] == "high"


class TestDetectViralMentions:
    @pytest.mark.asyncio
    async def test_no_viral(self):
        session = _make_session()
        td = TrendDetector(session)
        mentions = [
            _FakeSocialMention(engagement_count=50, raw_data={}),
            _FakeSocialMention(engagement_count=200, raw_data={}),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_viral_mentions(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_viral_positive(self):
        session = _make_session()
        td = TrendDetector(session)
        mentions = [
            _FakeSocialMention(
                engagement_count=5000,
                raw_data={"sentiment": {"label": "positive"}},
            ),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_viral_mentions(uuid4())

        assert result is not None
        assert result["type"] == "viral_mention"
        assert result["data"]["viral_count"] == 1
        assert result["data"]["positive_viral"] == 1
        assert result["data"]["overall_sentiment"] == "positive"
        assert result["severity"] == "high"

    @pytest.mark.asyncio
    async def test_viral_negative(self):
        session = _make_session()
        td = TrendDetector(session)
        mentions = [
            _FakeSocialMention(
                engagement_count=2000,
                raw_data={"sentiment": {"label": "negative"}},
            ),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_viral_mentions(uuid4())

        assert result["data"]["overall_sentiment"] == "negative"
        assert result["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_viral_mixed(self):
        session = _make_session()
        td = TrendDetector(session)
        mentions = [
            _FakeSocialMention(engagement_count=1500, raw_data={"sentiment": {"label": "positive"}}),
            _FakeSocialMention(engagement_count=1200, raw_data={"sentiment": {"label": "negative"}}),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_viral_mentions(uuid4())

        assert result["data"]["overall_sentiment"] == "mixed"

    @pytest.mark.asyncio
    async def test_viral_none_engagement(self):
        """Mentions with None engagement_count should not be viral."""
        session = _make_session()
        td = TrendDetector(session)
        mentions = [
            _FakeSocialMention(engagement_count=None, raw_data={}),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_viral_mentions(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_viral_no_raw_data(self):
        """Viral mention with no raw_data defaults to neutral."""
        session = _make_session()
        td = TrendDetector(session)
        mentions = [
            _FakeSocialMention(engagement_count=2000, raw_data=None),
        ]
        _mock_query_returns(session, mentions)

        with patch("services.analysis.trend_detector.select"):
            result = await td.detect_viral_mentions(uuid4())

        assert result is not None
        assert result["data"]["positive_viral"] == 0
        assert result["data"]["negative_viral"] == 0
        assert result["data"]["overall_sentiment"] == "mixed"


class TestGetPricingSignal:
    @pytest.mark.asyncio
    async def test_hold_signal_neutral(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={"alerts": []})
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.1})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.0, "volume_change": 0.0, "trend": "stable",
            "current_sentiment": 0.1, "previous_sentiment": 0.1,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["signal"] == "hold"
        assert result["strength"] == 0.0
        assert result["recommended_adjustment_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_increase_signal_positive_sentiment(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={"alerts": []})
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.7})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.0, "volume_change": 0.0, "trend": "stable",
            "current_sentiment": 0.7, "previous_sentiment": 0.7,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["signal"] == "increase"
        assert result["strength"] > 0

    @pytest.mark.asyncio
    async def test_decrease_signal_negative_sentiment(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={"alerts": []})
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": -0.5})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.0, "volume_change": 0.0, "trend": "stable",
            "current_sentiment": -0.5, "previous_sentiment": -0.5,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["signal"] == "decrease"

    @pytest.mark.asyncio
    async def test_improving_trend_boosts_signal(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={"alerts": []})
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.6})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.1, "volume_change": 0.0, "trend": "improving",
            "current_sentiment": 0.6, "previous_sentiment": 0.5,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["signal"] == "increase"
        assert result["strength"] >= 0.5  # sentiment + trend

    @pytest.mark.asyncio
    async def test_declining_trend_forces_decrease(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={"alerts": []})
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.6})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": -0.1, "volume_change": 0.0, "trend": "declining",
            "current_sentiment": 0.6, "previous_sentiment": 0.6,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["signal"] == "decrease"

    @pytest.mark.asyncio
    async def test_high_volume_boosts_strength(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={"alerts": []})
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.6})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.0, "volume_change": 1.5, "trend": "stable",
            "current_sentiment": 0.6, "previous_sentiment": 0.6,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["strength"] >= 0.5  # sentiment (0.3) + volume (0.2)

    @pytest.mark.asyncio
    async def test_viral_positive_boosts_adjustment(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={
            "alerts": [{"type": "viral_mention", "severity": "high",
                        "data": {"overall_sentiment": "positive"}}]
        })
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.6})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.0, "volume_change": 0.0, "trend": "stable",
            "current_sentiment": 0.6, "previous_sentiment": 0.6,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["recommended_adjustment_pct"] > 3.0  # base 3 + viral 2

    @pytest.mark.asyncio
    async def test_viral_negative_forces_decrease(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={
            "alerts": [{"type": "viral_mention", "severity": "critical",
                        "data": {"overall_sentiment": "negative"}}]
        })
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.0})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.0, "volume_change": 0.0, "trend": "stable",
            "current_sentiment": 0.0, "previous_sentiment": 0.0,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["signal"] == "decrease"
        assert result["recommended_adjustment_pct"] < 0

    @pytest.mark.asyncio
    async def test_strength_capped_at_1(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={"alerts": []})
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.8})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.2, "volume_change": 2.0, "trend": "improving",
            "current_sentiment": 0.8, "previous_sentiment": 0.6,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["strength"] <= 1.0

    @pytest.mark.asyncio
    async def test_adjustment_capped_at_10(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={
            "alerts": [
                {"type": "viral_mention", "data": {"overall_sentiment": "positive"}},
                {"type": "viral_mention", "data": {"overall_sentiment": "positive"}},
            ]
        })
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.9})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.3, "volume_change": 3.0, "trend": "improving",
            "current_sentiment": 0.9, "previous_sentiment": 0.6,
        })

        result = await td.get_pricing_signal(uuid4())
        assert result["recommended_adjustment_pct"] <= 10.0

    @pytest.mark.asyncio
    async def test_generated_at_present(self):
        td = _make_detector()
        td.detect_all = AsyncMock(return_value={"alerts": []})
        td.aggregator.get_product_sentiment = AsyncMock(return_value={"avg_sentiment": 0.0})
        td.aggregator.get_sentiment_velocity = AsyncMock(return_value={
            "velocity": 0.0, "volume_change": 0.0, "trend": "stable",
            "current_sentiment": 0.0, "previous_sentiment": 0.0,
        })

        result = await td.get_pricing_signal(uuid4())
        assert "generated_at" in result

        