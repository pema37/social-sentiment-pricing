"""
Test Suite: backend/schemas/analytics.py
Covers: DashboardOverview, ProductSummary, RecommendationStats,
        SentimentDataPoint, SentimentAnalytics, RevenueImpact, AlertAnalytics.

Place at: backend/tests/test_analytics_schemas.py
Run: pytest backend/tests/test_analytics_schemas.py -v
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from schemas.analytics import (
    AlertAnalytics,
    DashboardOverview,
    ProductSummary,
    RecommendationStats,
    RevenueImpact,
    SentimentAnalytics,
    SentimentDataPoint,
)

NOW = datetime.now(UTC)


# =====================================================================
# DashboardOverview
# =====================================================================


class TestDashboardOverview:
    def test_valid_minimal(self):
        d = DashboardOverview(
            total_products=50,
            products_with_auto_pricing=10,
            total_competitors=25,
            unread_alerts=3,
            alerts_today=1,
            pending_recommendations=5,
            applied_recommendations_7d=12,
        )
        assert d.average_sentiment is None
        assert d.sentiment_trend == "stable"
        assert d.total_mentions_24h == 0

    def test_valid_full(self):
        d = DashboardOverview(
            total_products=100,
            products_with_auto_pricing=30,
            total_competitors=60,
            unread_alerts=5,
            alerts_today=2,
            pending_recommendations=8,
            applied_recommendations_7d=20,
            average_sentiment=0.65,
            sentiment_trend="improving",
            total_mentions_24h=450,
        )
        assert d.average_sentiment == 0.65
        assert d.sentiment_trend == "improving"

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            DashboardOverview(
                total_products=50,
                # missing other required fields
            )


# =====================================================================
# ProductSummary
# =====================================================================


class TestProductSummary:
    def test_valid_minimal(self):
        p = ProductSummary(
            id="prod_123",
            name="Widget X",
            current_price=Decimal("29.99"),
            base_price=Decimal("24.99"),
            price_change_percent=20.0,
        )
        assert p.sku is None
        assert p.sentiment_score is None
        assert p.mention_count_24h == 0
        assert p.has_pending_recommendation is False
        assert p.auto_pricing_enabled is False

    def test_valid_full(self):
        p = ProductSummary(
            id="prod_456",
            name="Gadget Y",
            sku="GAD-Y-001",
            current_price=Decimal("49.99"),
            base_price=Decimal("39.99"),
            price_change_percent=25.0,
            sentiment_score=0.78,
            mention_count_24h=35,
            has_pending_recommendation=True,
            auto_pricing_enabled=True,
        )
        assert p.sku == "GAD-Y-001"
        assert p.auto_pricing_enabled is True

    def test_missing_id_raises(self):
        with pytest.raises(ValidationError):
            ProductSummary(
                name="Widget",
                current_price=Decimal("29.99"),
                base_price=Decimal("24.99"),
                price_change_percent=10.0,
            )

    def test_missing_price_raises(self):
        with pytest.raises(ValidationError):
            ProductSummary(
                id="p1",
                name="Widget",
                base_price=Decimal("24.99"),
                price_change_percent=10.0,
            )


# =====================================================================
# RecommendationStats
# =====================================================================


class TestRecommendationStats:
    def test_valid_minimal(self):
        r = RecommendationStats(
            total_generated=100,
            total_applied=60,
            total_rejected=20,
            total_expired=10,
            total_pending=10,
            approval_rate=0.75,
        )
        assert r.avg_confidence is None
        assert r.avg_price_change_percent is None

    def test_valid_full(self):
        r = RecommendationStats(
            total_generated=200,
            total_applied=120,
            total_rejected=40,
            total_expired=25,
            total_pending=15,
            approval_rate=0.75,
            avg_confidence=0.82,
            avg_price_change_percent=8.5,
        )
        assert r.avg_confidence == 0.82

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            RecommendationStats(
                total_generated=100,
                total_applied=60,
                # missing others
            )


# =====================================================================
# SentimentDataPoint
# =====================================================================


class TestSentimentDataPoint:
    def test_valid(self):
        s = SentimentDataPoint(
            timestamp=NOW,
            score=0.72,
            mention_count=45,
        )
        assert s.score == 0.72

    def test_missing_timestamp_raises(self):
        with pytest.raises(ValidationError):
            SentimentDataPoint(score=0.5, mention_count=10)


# =====================================================================
# SentimentAnalytics
# =====================================================================


class TestSentimentAnalytics:
    def test_valid_defaults(self):
        s = SentimentAnalytics(period_days=30)
        assert s.product_id is None
        assert s.current_score is None
        assert s.trend == "stable"
        assert s.timeline == []

    def test_valid_full(self):
        dp = SentimentDataPoint(timestamp=NOW, score=0.65, mention_count=30)
        s = SentimentAnalytics(
            product_id="prod_123",
            period_days=7,
            current_score=0.72,
            previous_score=0.60,
            change=0.12,
            trend="improving",
            timeline=[dp],
        )
        assert len(s.timeline) == 1
        assert s.change == 0.12

    def test_missing_period_raises(self):
        with pytest.raises(ValidationError):
            SentimentAnalytics()


# =====================================================================
# RevenueImpact
# =====================================================================


class TestRevenueImpact:
    def test_valid_minimal(self):
        r = RevenueImpact(
            period_days=30,
            total_price_changes=25,
            avg_change_percent=5.2,
            products_increased=15,
            products_decreased=10,
        )
        assert r.estimated_revenue_impact is None

    def test_valid_full(self):
        r = RevenueImpact(
            period_days=7,
            total_price_changes=10,
            avg_change_percent=3.5,
            products_increased=7,
            products_decreased=3,
            estimated_revenue_impact=Decimal("2500.00"),
        )
        assert r.estimated_revenue_impact == Decimal("2500.00")

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            RevenueImpact(period_days=30)


# =====================================================================
# AlertAnalytics
# =====================================================================


class TestAlertAnalytics:
    def test_valid_minimal(self):
        a = AlertAnalytics(
            total_alerts_7d=18,
            by_type={"sentiment_change": 5, "price_recommendation": 12, "competitor": 1},
            by_severity={"low": 10, "medium": 5, "high": 2, "critical": 1},
        )
        assert a.avg_resolution_time_hours is None

    def test_valid_full(self):
        a = AlertAnalytics(
            total_alerts_7d=25,
            by_type={"sentiment_change": 10, "price_recommendation": 15},
            by_severity={"low": 12, "medium": 8, "high": 4, "critical": 1},
            avg_resolution_time_hours=4.5,
        )
        assert a.avg_resolution_time_hours == 4.5

    def test_missing_required_raises(self):
        with pytest.raises(ValidationError):
            AlertAnalytics(total_alerts_7d=10)
