# backend/tests/test_ai_trend_calculators.py
"""
Tests for ai_trend_analysis/calculators.py — pure calculation
utilities for sentiment, volume, competitor, product performance,
and trend detection.

Total: ~35 tests
"""

import sys
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock

# === Import isolation ===
for mod in ["db.session"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from services.ai_trend_analysis.calculators import TrendCalculators


# ============================================================
# Helpers
# ============================================================

def make_sentiment(score, created_at=None, product_id=None):
    d = {"score": score, "created_at": created_at or datetime.now(UTC)}
    if product_id is not None:
        d["product_id"] = product_id
    return d


def make_product(name, product_id="p1"):
    p = MagicMock()
    p.id = product_id
    p.name = name
    return p


# ============================================================
# 1. calculate_avg_sentiment
# ============================================================

class TestCalculateAvgSentiment:

    def test_simple_average(self):
        data = [make_sentiment(0.5), make_sentiment(0.7), make_sentiment(0.3)]
        assert TrendCalculators.calculate_avg_sentiment(data) == 0.5

    def test_single_item(self):
        assert TrendCalculators.calculate_avg_sentiment([make_sentiment(0.8)]) == 0.8

    def test_empty_list(self):
        assert TrendCalculators.calculate_avg_sentiment([]) == 0.0


# ============================================================
# 2. calculate_sentiment_trend
# ============================================================

class TestCalculateSentimentTrend:

    def test_rising_trend(self):
        # First half (recent) has higher scores, second half (older) lower
        data = [make_sentiment(0.8)] * 5 + [make_sentiment(0.3)] * 5
        result = TrendCalculators.calculate_sentiment_trend(data)
        assert result == "rising"

    def test_falling_trend(self):
        data = [make_sentiment(0.2)] * 5 + [make_sentiment(0.8)] * 5
        result = TrendCalculators.calculate_sentiment_trend(data)
        assert result == "falling"

    def test_stable_trend(self):
        data = [make_sentiment(0.5)] * 10
        result = TrendCalculators.calculate_sentiment_trend(data)
        assert result == "stable"

    def test_too_few_data_points(self):
        data = [make_sentiment(0.5)] * 5
        assert TrendCalculators.calculate_sentiment_trend(data) == "stable"


# ============================================================
# 3. calculate_sentiment_volatility
# ============================================================

class TestCalculateSentimentVolatility:

    def test_zero_volatility(self):
        data = [make_sentiment(0.5)] * 5
        assert TrendCalculators.calculate_sentiment_volatility(data) == 0.0

    def test_nonzero_volatility(self):
        data = [make_sentiment(0.0), make_sentiment(1.0)]
        result = TrendCalculators.calculate_sentiment_volatility(data)
        assert result > 0

    def test_single_item(self):
        assert TrendCalculators.calculate_sentiment_volatility([make_sentiment(0.5)]) == 0.0

    def test_empty_list(self):
        assert TrendCalculators.calculate_sentiment_volatility([]) == 0.0


# ============================================================
# 4. calculate_volume_change
# ============================================================

class TestCalculateVolumeChange:

    def test_volume_increase(self):
        now = datetime.now(UTC)
        mid = now - timedelta(days=15)
        data = (
            [{"created_at": now - timedelta(days=i)} for i in range(10)] +  # 10 recent
            [{"created_at": mid - timedelta(days=i)} for i in range(5)]     # 5 older
        )
        result = TrendCalculators.calculate_volume_change(data, 30)
        assert result > 0

    def test_no_older_data(self):
        now = datetime.now(UTC)
        data = [{"created_at": now - timedelta(days=i)} for i in range(5)]
        result = TrendCalculators.calculate_volume_change(data, 30)
        assert result == 0.0

    def test_too_few_days(self):
        assert TrendCalculators.calculate_volume_change([{"created_at": datetime.now(UTC)}], 7) == 0.0

    def test_empty_data(self):
        assert TrendCalculators.calculate_volume_change([], 30) == 0.0


# ============================================================
# 5. summarize_competitor_changes
# ============================================================

class TestSummarizeCompetitorChanges:

    def test_with_data(self):
        data = [{"name": "A"}, {"name": "B"}]
        result = TrendCalculators.summarize_competitor_changes(data)
        assert "2 competitors" in result

    def test_empty_data(self):
        result = TrendCalculators.summarize_competitor_changes([])
        assert "No competitor data" in result


# ============================================================
# 6. get_top_performing_product
# ============================================================

class TestGetTopPerformingProduct:

    def test_finds_best_product(self):
        p1 = make_product("Widget A", "p1")
        p2 = make_product("Widget B", "p2")
        data = [
            make_sentiment(0.9, product_id="p1"),
            make_sentiment(0.3, product_id="p2"),
        ]
        assert TrendCalculators.get_top_performing_product([p1, p2], data) == "Widget A"

    def test_no_products(self):
        assert TrendCalculators.get_top_performing_product([], []) == "N/A"

    def test_no_sentiment_data(self):
        p1 = make_product("Widget A")
        assert TrendCalculators.get_top_performing_product([p1], []) == "Widget A"

    def test_no_matching_product_id(self):
        p1 = make_product("Widget A", "p1")
        data = [make_sentiment(0.9, product_id="unknown")]
        result = TrendCalculators.get_top_performing_product([p1], data)
        assert result == "Widget A"  # Falls back to first product


# ============================================================
# 7. get_worst_performing_product
# ============================================================

class TestGetWorstPerformingProduct:

    def test_finds_worst_product(self):
        p1 = make_product("Widget A", "p1")
        p2 = make_product("Widget B", "p2")
        data = [
            make_sentiment(0.9, product_id="p1"),
            make_sentiment(0.1, product_id="p2"),
        ]
        assert TrendCalculators.get_worst_performing_product([p1, p2], data) == "Widget B"

    def test_no_products(self):
        assert TrendCalculators.get_worst_performing_product([], []) == "N/A"

    def test_no_sentiment_data(self):
        p1 = make_product("Widget A")
        p2 = make_product("Widget B")
        assert TrendCalculators.get_worst_performing_product([p1, p2], []) == "Widget B"


# ============================================================
# 8. detect_basic_trends
# ============================================================

class TestDetectBasicTrends:

    def test_sentiment_rise_detected(self):
        # Recent 7 high, older 7 low → rise > 0.2
        data = [make_sentiment(0.8)] * 7 + [make_sentiment(0.3)] * 7
        trends = TrendCalculators.detect_basic_trends(data)
        types = [t["type"] for t in trends]
        assert "sentiment_rise" in types

    def test_sentiment_drop_detected(self):
        data = [make_sentiment(0.2)] * 7 + [make_sentiment(0.8)] * 7
        trends = TrendCalculators.detect_basic_trends(data)
        types = [t["type"] for t in trends]
        assert "sentiment_drop" in types

    def test_no_trends_when_stable(self):
        data = [make_sentiment(0.5)] * 14
        trends = TrendCalculators.detect_basic_trends(data)
        assert len(trends) == 0

    def test_empty_data(self):
        assert TrendCalculators.detect_basic_trends([]) == []


# ============================================================
# 9. detect_notable_events
# ============================================================

class TestDetectNotableEvents:

    def test_sentiment_shift_detected(self):
        data = [
            make_sentiment(0.9),
            make_sentiment(0.2),  # Sudden drop > 0.5
            make_sentiment(0.3),
        ]
        events = TrendCalculators.detect_notable_events(data, [])
        assert len(events) == 1
        assert events[0]["type"] == "sentiment_shift"

    def test_no_shift_when_gradual(self):
        data = [
            make_sentiment(0.5),
            make_sentiment(0.6),
            make_sentiment(0.7),
        ]
        events = TrendCalculators.detect_notable_events(data, [])
        assert len(events) == 0

    def test_too_few_data_points(self):
        data = [make_sentiment(0.5), make_sentiment(0.1)]
        events = TrendCalculators.detect_notable_events(data, [])
        assert len(events) == 0


        