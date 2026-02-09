"""
Tests for services/ai_trend_analysis/formatters.py

Covers all static methods in DataFormatter:
- format_products
- format_sentiment_history
- format_sentiment_drops
- format_mentions_summary
- format_recent_mentions
- format_negative_mentions
- format_competitor_data
- format_competitor_prices
- format_competitor_activities
- format_current_alerts
- format_trends
- format_events
"""

import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock

# ── Import isolation ──────────────────────────────────────────────
for mod in ["db.session", "core.logging"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
sys.modules["core.logging"].get_logger = MagicMock(return_value=MagicMock())

from services.ai_trend_analysis.formatters import DataFormatter


# ==================================================================
# format_products
# ==================================================================

class TestFormatProducts:
    def test_empty_list(self):
        assert DataFormatter.format_products([]) == "No products"

    def test_none_like_empty(self):
        """Empty list returns fallback."""
        assert DataFormatter.format_products([]) == "No products"

    def test_single_product_no_category(self):
        p = MagicMock()
        p.name = "Widget"
        p.base_price = 29.99
        p.category = None
        result = DataFormatter.format_products([p])
        assert "Widget" in result
        assert "$29.99" in result
        assert "Category" not in result

    def test_single_product_with_category(self):
        p = MagicMock()
        p.name = "Widget"
        p.base_price = 29.99
        p.category = "Electronics"
        result = DataFormatter.format_products([p])
        assert "Widget" in result
        assert "$29.99" in result
        assert "(Category: Electronics)" in result

    def test_multiple_products(self):
        products = []
        for i in range(5):
            p = MagicMock()
            p.name = f"Product {i}"
            p.base_price = 10.0 + i
            p.category = "Cat"
            products.append(p)
        result = DataFormatter.format_products(products)
        lines = result.strip().split("\n")
        assert len(lines) == 5

    def test_limits_to_20_products(self):
        products = []
        for i in range(30):
            p = MagicMock()
            p.name = f"Product {i}"
            p.base_price = float(i)
            p.category = None
            products.append(p)
        result = DataFormatter.format_products(products)
        lines = result.strip().split("\n")
        assert len(lines) == 20

    def test_exactly_20_products(self):
        products = []
        for i in range(20):
            p = MagicMock()
            p.name = f"P{i}"
            p.base_price = 1.0
            p.category = None
            products.append(p)
        result = DataFormatter.format_products(products)
        lines = result.strip().split("\n")
        assert len(lines) == 20

    def test_product_line_format(self):
        p = MagicMock()
        p.name = "Test Item"
        p.base_price = 99.99
        p.category = "Toys"
        result = DataFormatter.format_products([p])
        assert result == "- Test Item: $99.99 (Category: Toys)"

    def test_empty_category_string(self):
        """Empty string category is falsy, should not appear."""
        p = MagicMock()
        p.name = "Widget"
        p.base_price = 10.0
        p.category = ""
        result = DataFormatter.format_products([p])
        assert "Category" not in result


# ==================================================================
# format_sentiment_history
# ==================================================================

class TestFormatSentimentHistory:
    def test_empty_list(self):
        assert DataFormatter.format_sentiment_history([]) == "No sentiment data available"

    def test_single_entry(self):
        data = [{"created_at": datetime(2026, 2, 1, tzinfo=timezone.utc), "score": 0.75}]
        result = DataFormatter.format_sentiment_history(data)
        assert "2026-02-01" in result
        assert "0.75" in result
        assert "n=1" in result

    def test_multiple_entries_same_day_averaged(self):
        data = [
            {"created_at": datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc), "score": 0.80},
            {"created_at": datetime(2026, 2, 1, 14, 0, tzinfo=timezone.utc), "score": 0.60},
        ]
        result = DataFormatter.format_sentiment_history(data)
        assert "2026-02-01" in result
        assert "0.70" in result
        assert "n=2" in result

    def test_multiple_days_sorted_reverse(self):
        data = [
            {"created_at": datetime(2026, 1, 1, tzinfo=timezone.utc), "score": 0.50},
            {"created_at": datetime(2026, 2, 1, tzinfo=timezone.utc), "score": 0.80},
        ]
        result = DataFormatter.format_sentiment_history(data)
        lines = result.strip().split("\n")
        # Most recent date first
        assert "2026-02-01" in lines[0]
        assert "2026-01-01" in lines[1]

    def test_limits_to_14_days(self):
        data = []
        for day in range(1, 25):
            data.append({
                "created_at": datetime(2026, 1, day, tzinfo=timezone.utc),
                "score": 0.5,
            })
        result = DataFormatter.format_sentiment_history(data)
        lines = result.strip().split("\n")
        assert len(lines) == 14

    def test_exactly_14_days(self):
        data = []
        for day in range(1, 15):
            data.append({
                "created_at": datetime(2026, 1, day, tzinfo=timezone.utc),
                "score": 0.5,
            })
        result = DataFormatter.format_sentiment_history(data)
        lines = result.strip().split("\n")
        assert len(lines) == 14

    def test_negative_scores(self):
        data = [{"created_at": datetime(2026, 2, 1, tzinfo=timezone.utc), "score": -0.65}]
        result = DataFormatter.format_sentiment_history(data)
        assert "-0.65" in result

    def test_average_formatting_two_decimals(self):
        data = [
            {"created_at": datetime(2026, 2, 1, tzinfo=timezone.utc), "score": 0.333},
            {"created_at": datetime(2026, 2, 1, tzinfo=timezone.utc), "score": 0.666},
        ]
        result = DataFormatter.format_sentiment_history(data)
        # Average is 0.4995, formatted to 2 decimals = 0.50
        assert "0.50" in result


# ==================================================================
# format_sentiment_drops
# ==================================================================

class TestFormatSentimentDrops:
    def test_empty_list(self):
        assert DataFormatter.format_sentiment_drops([]) == "No significant sentiment drops detected"

    def test_single_drop(self):
        drops = ["Score dropped from 0.8 to 0.2 on 2026-02-01"]
        result = DataFormatter.format_sentiment_drops(drops)
        assert "- Score dropped from 0.8 to 0.2 on 2026-02-01" == result

    def test_multiple_drops(self):
        drops = ["Drop 1", "Drop 2", "Drop 3"]
        result = DataFormatter.format_sentiment_drops(drops)
        lines = result.strip().split("\n")
        assert len(lines) == 3
        assert all(line.startswith("- ") for line in lines)


# ==================================================================
# format_mentions_summary
# ==================================================================

class TestFormatMentionsSummary:
    def test_empty_list(self):
        assert DataFormatter.format_mentions_summary([]) == "No mentions data available"

    def test_single_platform(self):
        data = [
            {"platform": "reddit"},
            {"platform": "reddit"},
        ]
        result = DataFormatter.format_mentions_summary(data)
        assert "Total mentions: 2" in result
        assert "reddit: 2" in result

    def test_multiple_platforms_sorted_by_count(self):
        data = [
            {"platform": "twitter"},
            {"platform": "reddit"},
            {"platform": "reddit"},
            {"platform": "reddit"},
        ]
        result = DataFormatter.format_mentions_summary(data)
        lines = result.strip().split("\n")
        assert "Total mentions: 4" in lines[0]
        # Reddit (3) should come before twitter (1)
        assert "reddit: 3" in lines[1]
        assert "twitter: 1" in lines[2]

    def test_missing_platform_defaults_to_unknown(self):
        data = [{"no_platform_key": True}]
        result = DataFormatter.format_mentions_summary(data)
        assert "unknown: 1" in result

    def test_mixed_platforms_with_unknown(self):
        data = [
            {"platform": "reddit"},
            {},
            {"platform": "twitter"},
        ]
        result = DataFormatter.format_mentions_summary(data)
        assert "Total mentions: 3" in result


# ==================================================================
# format_recent_mentions
# ==================================================================

class TestFormatRecentMentions:
    def test_empty_list(self):
        assert DataFormatter.format_recent_mentions([]) == "No recent mentions"

    def test_single_mention(self):
        m = MagicMock()
        m.content = "This product is great"
        m.sentiment_score = 0.85
        result = DataFormatter.format_recent_mentions([m])
        assert "[0.85]" in result
        assert "This product is great" in result

    def test_truncates_content_at_100_chars(self):
        m = MagicMock()
        m.content = "A" * 200
        m.sentiment_score = 0.5
        result = DataFormatter.format_recent_mentions([m])
        # Content should be truncated to 100 chars + "..."
        assert "A" * 100 + "..." in result

    def test_limits_to_10_mentions(self):
        mentions = []
        for i in range(15):
            m = MagicMock()
            m.content = f"Mention {i}"
            m.sentiment_score = 0.5
            mentions.append(m)
        result = DataFormatter.format_recent_mentions(mentions)
        lines = result.strip().split("\n")
        assert len(lines) == 10

    def test_none_content(self):
        m = MagicMock()
        m.content = None
        m.sentiment_score = 0.5
        result = DataFormatter.format_recent_mentions([m])
        assert "[0.50]" in result
        assert "..." in result

    def test_none_sentiment_score(self):
        m = MagicMock()
        m.content = "Some content"
        m.sentiment_score = None
        result = DataFormatter.format_recent_mentions([m])
        assert "[0.00]" in result

    def test_negative_sentiment_score(self):
        m = MagicMock()
        m.content = "Terrible product"
        m.sentiment_score = -0.75
        result = DataFormatter.format_recent_mentions([m])
        assert "[-0.75]" in result

    def test_content_exactly_100_chars(self):
        m = MagicMock()
        m.content = "B" * 100
        m.sentiment_score = 0.0
        result = DataFormatter.format_recent_mentions([m])
        assert "B" * 100 + "..." in result


# ==================================================================
# format_negative_mentions
# ==================================================================

class TestFormatNegativeMentions:
    def test_empty_list(self):
        assert DataFormatter.format_negative_mentions([]) == "No significant negative mentions"

    def test_single_mention(self):
        m = MagicMock()
        m.content = "Bad quality"
        m.sentiment_score = -0.90
        result = DataFormatter.format_negative_mentions([m])
        assert "[-0.90]" in result
        assert "Bad quality" in result

    def test_limits_to_20_mentions(self):
        mentions = []
        for i in range(30):
            m = MagicMock()
            m.content = f"Bad {i}"
            m.sentiment_score = -0.5
            mentions.append(m)
        result = DataFormatter.format_negative_mentions(mentions)
        lines = result.strip().split("\n")
        assert len(lines) == 20

    def test_truncates_content_at_100_chars(self):
        m = MagicMock()
        m.content = "X" * 200
        m.sentiment_score = -0.3
        result = DataFormatter.format_negative_mentions([m])
        # First 100 chars, no trailing "..." (unlike format_recent_mentions)
        assert "X" * 100 in result

    def test_none_content(self):
        m = MagicMock()
        m.content = None
        m.sentiment_score = -0.5
        result = DataFormatter.format_negative_mentions([m])
        assert "[-0.50]" in result

    def test_none_sentiment_score(self):
        m = MagicMock()
        m.content = "Content"
        m.sentiment_score = None
        result = DataFormatter.format_negative_mentions([m])
        assert "[0.00]" in result


# ==================================================================
# format_competitor_data
# ==================================================================

class TestFormatCompetitorData:
    def test_empty_list(self):
        assert DataFormatter.format_competitor_data([]) == "No competitor data available"

    def test_single_competitor(self):
        data = [{"competitor_name": "Amazon", "competitor_price": 49.99}]
        result = DataFormatter.format_competitor_data(data)
        assert "Amazon" in result
        assert "$49.99" in result

    def test_missing_name_defaults_to_unknown(self):
        data = [{"competitor_price": 19.99}]
        result = DataFormatter.format_competitor_data(data)
        assert "Unknown" in result

    def test_missing_price_defaults_to_zero(self):
        data = [{"competitor_name": "Store"}]
        result = DataFormatter.format_competitor_data(data)
        assert "$0.00" in result

    def test_limits_to_20_competitors(self):
        data = [{"competitor_name": f"C{i}", "competitor_price": float(i)} for i in range(30)]
        result = DataFormatter.format_competitor_data(data)
        lines = result.strip().split("\n")
        assert len(lines) == 20

    def test_price_formatting(self):
        data = [{"competitor_name": "Store", "competitor_price": 100.5}]
        result = DataFormatter.format_competitor_data(data)
        assert "$100.50" in result


# ==================================================================
# format_competitor_prices
# ==================================================================

class TestFormatCompetitorPrices:
    def test_empty_list(self):
        assert DataFormatter.format_competitor_prices([]) == "No competitor prices available"

    def test_object_with_attributes(self):
        c = MagicMock()
        c.competitor_name = "BestBuy"
        c.price = 59.99
        result = DataFormatter.format_competitor_prices([c])
        assert "BestBuy" in result
        assert "$59.99" in result

    def test_object_without_competitor_name(self):
        c = MagicMock(spec=[])  # No attributes
        c.price = 29.99
        result = DataFormatter.format_competitor_prices([c])
        assert "Competitor" in result

    def test_none_price_defaults_to_zero(self):
        c = MagicMock()
        c.competitor_name = "Store"
        c.price = None
        result = DataFormatter.format_competitor_prices([c])
        assert "$0.00" in result

    def test_multiple_competitors(self):
        comps = []
        for i in range(5):
            c = MagicMock()
            c.competitor_name = f"Store{i}"
            c.price = 10.0 * (i + 1)
            comps.append(c)
        result = DataFormatter.format_competitor_prices(comps)
        lines = result.strip().split("\n")
        assert len(lines) == 5


# ==================================================================
# format_competitor_activities
# ==================================================================

class TestFormatCompetitorActivities:
    def test_empty_list(self):
        assert DataFormatter.format_competitor_activities([]) == "No recent competitor activities"

    def test_single_activity(self):
        activities = ["Price drop by Amazon -15%"]
        result = DataFormatter.format_competitor_activities(activities)
        assert "- Price drop by Amazon -15%" == result

    def test_multiple_activities(self):
        activities = ["Activity 1", "Activity 2"]
        result = DataFormatter.format_competitor_activities(activities)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert all(line.startswith("- ") for line in lines)


# ==================================================================
# format_current_alerts
# ==================================================================

class TestFormatCurrentAlerts:
    def test_empty_list(self):
        assert DataFormatter.format_current_alerts([]) == "No active alerts"

    def test_single_alert_with_attributes(self):
        a = MagicMock()
        a.alert_type = "price_drop"
        a.message = "Competitor dropped price by 20%"
        result = DataFormatter.format_current_alerts([a])
        assert "price_drop" in result
        assert "Competitor dropped price by 20%" in result

    def test_alert_without_attributes(self):
        a = MagicMock(spec=[])  # No attributes
        result = DataFormatter.format_current_alerts([a])
        assert "unknown" in result

    def test_limits_to_10_alerts(self):
        alerts = []
        for i in range(15):
            a = MagicMock()
            a.alert_type = f"type_{i}"
            a.message = f"Alert {i}"
            alerts.append(a)
        result = DataFormatter.format_current_alerts(alerts)
        lines = result.strip().split("\n")
        assert len(lines) == 10

    def test_exactly_10_alerts(self):
        alerts = []
        for i in range(10):
            a = MagicMock()
            a.alert_type = "warning"
            a.message = f"Msg {i}"
            alerts.append(a)
        result = DataFormatter.format_current_alerts(alerts)
        lines = result.strip().split("\n")
        assert len(lines) == 10


# ==================================================================
# format_trends
# ==================================================================

class TestFormatTrends:
    def test_empty_list(self):
        assert DataFormatter.format_trends([]) == "No significant trends detected"

    def test_single_trend(self):
        result = DataFormatter.format_trends(["Rising demand for wireless earbuds"])
        assert "- Rising demand for wireless earbuds" == result

    def test_multiple_trends(self):
        trends = ["Trend A", "Trend B", "Trend C"]
        result = DataFormatter.format_trends(trends)
        lines = result.strip().split("\n")
        assert len(lines) == 3


# ==================================================================
# format_events
# ==================================================================

class TestFormatEvents:
    def test_empty_list(self):
        assert DataFormatter.format_events([]) == "No notable events"

    def test_single_event(self):
        result = DataFormatter.format_events(["Amazon Prime Day announced"])
        assert "- Amazon Prime Day announced" == result

    def test_multiple_events(self):
        events = ["Event 1", "Event 2"]
        result = DataFormatter.format_events(events)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert all(line.startswith("- ") for line in lines)


        