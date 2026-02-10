"""
Tests for services/analytics/analytics_service.py

Dashboard analytics service — uses plain Python classes for column mocks
to avoid Python 3.13 MagicMock comparison dunder restrictions.
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from decimal import Decimal

# ── Import isolation ──────────────────────────────────────────────
_MOCKED_MODULES = [
    "db.session", "core.logging",
    "models.product", "models.competitor", "models.sentiment",
    "models.price_recommendation", "models.price_history",
    "models.alert",
    "schemas.analytics",
]
_originals = {mod: sys.modules.get(mod) for mod in _MOCKED_MODULES}

for mod in _MOCKED_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

sys.modules["core.logging"].get_logger = MagicMock(return_value=MagicMock())

# Fake schema classes — pass-through constructors
class _FakeDashboardOverview:
    def __init__(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)

class _FakeProductSummary:
    def __init__(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)

class _FakeRecommendationStats:
    def __init__(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)

class _FakeAlertAnalytics:
    def __init__(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)

class _FakeSentimentAnalytics:
    def __init__(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)

class _FakeSentimentDataPoint:
    def __init__(self, **kw):
        for k, v in kw.items(): setattr(self, k, v)

_schema_mod = sys.modules["schemas.analytics"]
_schema_mod.DashboardOverview = _FakeDashboardOverview
_schema_mod.ProductSummary = _FakeProductSummary
_schema_mod.RecommendationStats = _FakeRecommendationStats
_schema_mod.AlertAnalytics = _FakeAlertAnalytics
_schema_mod.SentimentAnalytics = _FakeSentimentAnalytics
_schema_mod.SentimentDataPoint = _FakeSentimentDataPoint

class _FakeRecStatus:
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"

sys.modules["models.price_recommendation"].RecommendationStatus = _FakeRecStatus

class _FakeAlertStatus:
    SENT = "sent"
    READ = "read"

sys.modules["models.alert"].AlertStatus = _FakeAlertStatus

from services.analytics.analytics_service import AnalyticsService

# ── Restore modules ──────────────────────────────────────────────
for _mod in _MOCKED_MODULES:
    if _originals[_mod] is None:
        sys.modules.pop(_mod, None)
    else:
        sys.modules[_mod] = _originals[_mod]
del _mod

import pytest

SVC_MOD = "services.analytics.analytics_service"


# ── Plain-class column mock (NOT MagicMock subclass) ─────────────
# Python 3.13 MagicMock blocks comparison dunders, so we use a
# plain class that supports all comparison operators.

class _Col:
    """Fake SQLAlchemy column — supports comparisons, calls, .desc(), attribute access."""
    def __ge__(self, other): return _Col()
    def __le__(self, other): return _Col()
    def __gt__(self, other): return _Col()
    def __lt__(self, other): return _Col()
    def __eq__(self, other): return _Col()
    def __ne__(self, other): return _Col()
    def __hash__(self):      return id(self)
    def __call__(self, *a, **kw): return _Col()
    def desc(self):          return _Col()
    def label(self, name):   return _Col()
    def __getattr__(self, name): return _Col()
    def __bool__(self):      return True


class _Model:
    """Fake SQLAlchemy model — all attribute access returns _Col, also callable."""
    def __getattr__(self, name):
        return _Col()
    def __call__(self, *a, **kw):
        return _Col()


# ── Helpers ──────────────────────────────────────────────────────

def _scalar_one_result(value):
    r = MagicMock()
    r.scalar_one = MagicMock(return_value=value)
    return r

def _scalars_all_result(items):
    r = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=items)
    r.scalars = MagicMock(return_value=scalars)
    return r

def _scalars_first_result(item):
    r = MagicMock()
    scalars = MagicMock()
    scalars.first = MagicMock(return_value=item)
    r.scalars = MagicMock(return_value=scalars)
    return r

def _rows_result(rows):
    r = MagicMock()
    r.all = MagicMock(return_value=rows)
    return r

def _make_session():
    return AsyncMock()

def _make_product(**overrides):
    p = MagicMock()
    p.id = overrides.get("id", "prod-1")
    p.name = overrides.get("name", "Test Product")
    p.sku = overrides.get("sku", "SKU001")
    p.current_price = overrides.get("current_price", Decimal("29.99"))
    p.base_price = overrides.get("base_price", Decimal("24.99"))
    p.auto_pricing_enabled = overrides.get("auto_pricing_enabled", True)
    p.updated_at = overrides.get("updated_at", datetime.utcnow())
    return p

def _make_alert(**overrides):
    a = MagicMock()
    a.alert_type = MagicMock()
    a.alert_type.value = overrides.get("alert_type", "price_change")
    a.severity = MagicMock()
    a.severity.value = overrides.get("severity", "high")
    return a

def _chainable_select(*args, **kwargs):
    q = MagicMock()
    q.where = MagicMock(return_value=q)
    q.order_by = MagicMock(return_value=q)
    q.limit = MagicMock(return_value=q)
    q.join = MagicMock(return_value=q)
    q.group_by = MagicMock(return_value=q)
    q.label = MagicMock(return_value=q)
    return q


# ── Decorator — patches SQLAlchemy + models with plain classes ───
def _patch_sql(fn):
    @patch(f"{SVC_MOD}.Product", _Model())
    @patch(f"{SVC_MOD}.Competitor", _Model())
    @patch(f"{SVC_MOD}.Sentiment", _Model())
    @patch(f"{SVC_MOD}.PriceRecommendation", _Model())
    @patch(f"{SVC_MOD}.PriceHistory", _Model())
    @patch(f"{SVC_MOD}.Alert", _Model())
    @patch(f"{SVC_MOD}.AlertStatus", _FakeAlertStatus)
    @patch(f"{SVC_MOD}.RecommendationStatus", _FakeRecStatus)
    @patch(f"{SVC_MOD}.func", _Model())
    @patch(f"{SVC_MOD}.and_", lambda *args: _Col())
    @patch(f"{SVC_MOD}.select", _chainable_select)
    async def wrapper(*args, **kwargs):
        return await fn(*args, **kwargs)
    wrapper.__name__ = fn.__name__
    wrapper.__qualname__ = fn.__qualname__
    return wrapper


# ──────────────────────────────────────────────
# Constructor
# ──────────────────────────────────────────────
class TestAnalyticsServiceInit:

    def test_stores_session_and_user_id(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-123")
        assert svc.session is session
        assert svc.user_id == "user-123"


# ──────────────────────────────────────────────
# get_dashboard_overview
# ──────────────────────────────────────────────
class TestGetDashboardOverview:

    @pytest.mark.asyncio
    @_patch_sql
    async def test_returns_dashboard_overview(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            _scalar_one_result(10),    # total_products
            _scalar_one_result(3),     # auto_pricing
            _scalar_one_result(5),     # competitors
            _scalar_one_result(2),     # unread_alerts
            _scalar_one_result(7),     # alerts_today
            _scalar_one_result(4),     # pending_recs
            _scalar_one_result(6),     # applied_7d
            _scalar_one_result(0.65),  # sentiment_24h
            _scalar_one_result(0.55),  # sentiment_48h
            _scalar_one_result(120),   # mentions_24h
        ])

        result = await svc.get_dashboard_overview()
        assert result.total_products == 10
        assert result.products_with_auto_pricing == 3
        assert result.total_competitors == 5
        assert result.unread_alerts == 2
        assert result.alerts_today == 7
        assert result.pending_recommendations == 4
        assert result.applied_recommendations_7d == 6
        assert result.total_mentions_24h == 120

    @pytest.mark.asyncio
    @_patch_sql
    async def test_sentiment_trend_improving(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            *[_scalar_one_result(0) for _ in range(7)],
            _scalar_one_result(0.80),
            _scalar_one_result(0.50),
            _scalar_one_result(0),
        ])

        result = await svc.get_dashboard_overview()
        assert result.sentiment_trend == "improving"

    @pytest.mark.asyncio
    @_patch_sql
    async def test_sentiment_trend_declining(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            *[_scalar_one_result(0) for _ in range(7)],
            _scalar_one_result(0.30),
            _scalar_one_result(0.80),
            _scalar_one_result(0),
        ])

        result = await svc.get_dashboard_overview()
        assert result.sentiment_trend == "declining"

    @pytest.mark.asyncio
    @_patch_sql
    async def test_sentiment_trend_stable(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            *[_scalar_one_result(0) for _ in range(7)],
            _scalar_one_result(0.60),
            _scalar_one_result(0.58),
            _scalar_one_result(0),
        ])

        result = await svc.get_dashboard_overview()
        assert result.sentiment_trend == "stable"

    @pytest.mark.asyncio
    @_patch_sql
    async def test_sentiment_none_returns_stable(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            *[_scalar_one_result(0) for _ in range(7)],
            _scalar_one_result(None),
            _scalar_one_result(None),
            _scalar_one_result(0),
        ])

        result = await svc.get_dashboard_overview()
        assert result.sentiment_trend == "stable"
        assert result.average_sentiment is None


# ──────────────────────────────────────────────
# get_product_summaries
# ──────────────────────────────────────────────
class TestGetProductSummaries:

    @pytest.mark.asyncio
    @_patch_sql
    async def test_returns_product_list(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        product = _make_product()
        sentiment = MagicMock()
        sentiment.compound_score = 0.85

        session.execute = AsyncMock(side_effect=[
            _scalars_all_result([product]),
            _scalars_first_result(sentiment),
            _scalar_one_result(5),
            _scalar_one_result(1),
        ])

        result = await svc.get_product_summaries(limit=10)
        assert len(result) == 1
        assert result[0].name == "Test Product"
        assert result[0].has_pending_recommendation is True

    @pytest.mark.asyncio
    @_patch_sql
    async def test_price_change_percent(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        product = _make_product(
            current_price=Decimal("30.00"),
            base_price=Decimal("20.00"),
        )

        session.execute = AsyncMock(side_effect=[
            _scalars_all_result([product]),
            _scalars_first_result(None),
            _scalar_one_result(0),
            _scalar_one_result(0),
        ])

        result = await svc.get_product_summaries()
        assert result[0].price_change_percent == 50.0

    @pytest.mark.asyncio
    @_patch_sql
    async def test_zero_base_price(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        product = _make_product(base_price=Decimal("0"))

        session.execute = AsyncMock(side_effect=[
            _scalars_all_result([product]),
            _scalars_first_result(None),
            _scalar_one_result(0),
            _scalar_one_result(0),
        ])

        result = await svc.get_product_summaries()
        assert result[0].price_change_percent == 0.0

    @pytest.mark.asyncio
    @_patch_sql
    async def test_none_base_price(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        product = _make_product(base_price=None)

        session.execute = AsyncMock(side_effect=[
            _scalars_all_result([product]),
            _scalars_first_result(None),
            _scalar_one_result(0),
            _scalar_one_result(0),
        ])

        result = await svc.get_product_summaries()
        assert result[0].price_change_percent == 0.0

    @pytest.mark.asyncio
    @_patch_sql
    async def test_no_sentiment_returns_none(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        product = _make_product()

        session.execute = AsyncMock(side_effect=[
            _scalars_all_result([product]),
            _scalars_first_result(None),
            _scalar_one_result(0),
            _scalar_one_result(0),
        ])

        result = await svc.get_product_summaries()
        assert result[0].sentiment_score is None

    @pytest.mark.asyncio
    @_patch_sql
    async def test_empty_products(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[_scalars_all_result([])])

        result = await svc.get_product_summaries()
        assert result == []

    @pytest.mark.asyncio
    @_patch_sql
    async def test_multiple_products(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        p1 = _make_product(id="p1", name="Product A")
        p2 = _make_product(id="p2", name="Product B")

        session.execute = AsyncMock(side_effect=[
            _scalars_all_result([p1, p2]),
            _scalars_first_result(None), _scalar_one_result(3), _scalar_one_result(0),
            _scalars_first_result(None), _scalar_one_result(1), _scalar_one_result(2),
        ])

        result = await svc.get_product_summaries()
        assert len(result) == 2
        assert result[0].name == "Product A"
        assert result[1].name == "Product B"

    @pytest.mark.asyncio
    @_patch_sql
    async def test_has_pending_false(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        product = _make_product()

        session.execute = AsyncMock(side_effect=[
            _scalars_all_result([product]),
            _scalars_first_result(None),
            _scalar_one_result(0),
            _scalar_one_result(0),
        ])

        result = await svc.get_product_summaries()
        assert result[0].has_pending_recommendation is False


# ──────────────────────────────────────────────
# get_recommendation_stats
# ──────────────────────────────────────────────
class TestGetRecommendationStats:

    @pytest.mark.asyncio
    @_patch_sql
    async def test_basic_stats(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            _scalar_one_result(100),
            _scalar_one_result(60),
            _scalar_one_result(20),
            _scalar_one_result(10),
            _scalar_one_result(10),
            _scalar_one_result(0.85),
        ])

        result = await svc.get_recommendation_stats(days=30)
        assert result.total_generated == 100
        assert result.total_applied == 60
        assert result.total_rejected == 20
        assert result.total_expired == 10
        assert result.total_pending == 10

    @pytest.mark.asyncio
    @_patch_sql
    async def test_approval_rate(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            _scalar_one_result(100),
            _scalar_one_result(75),
            _scalar_one_result(25),
            _scalar_one_result(0),
            _scalar_one_result(0),
            _scalar_one_result(0.90),
        ])

        result = await svc.get_recommendation_stats()
        assert result.approval_rate == 75.0

    @pytest.mark.asyncio
    @_patch_sql
    async def test_zero_decided_rate(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            _scalar_one_result(5),
            _scalar_one_result(0),
            _scalar_one_result(0),
            _scalar_one_result(0),
            _scalar_one_result(5),
            _scalar_one_result(None),
        ])

        result = await svc.get_recommendation_stats()
        assert result.approval_rate == 0.0

    @pytest.mark.asyncio
    @_patch_sql
    async def test_avg_confidence_none(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            *[_scalar_one_result(0) for _ in range(5)],
            _scalar_one_result(None),
        ])

        result = await svc.get_recommendation_stats()
        assert result.avg_confidence is None

    @pytest.mark.asyncio
    @_patch_sql
    async def test_avg_price_change_always_none(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[
            *[_scalar_one_result(0) for _ in range(5)],
            _scalar_one_result(None),
        ])

        result = await svc.get_recommendation_stats()
        assert result.avg_price_change_percent is None


# ──────────────────────────────────────────────
# get_alert_analytics
# ──────────────────────────────────────────────
class TestGetAlertAnalytics:

    @pytest.mark.asyncio
    @_patch_sql
    async def test_empty_alerts(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[_scalars_all_result([])])

        result = await svc.get_alert_analytics()
        assert result.total_alerts_7d == 0
        assert result.by_type == {}
        assert result.by_severity == {}

    @pytest.mark.asyncio
    @_patch_sql
    async def test_counts_by_type_and_severity(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        alerts = [
            _make_alert(alert_type="price_change", severity="high"),
            _make_alert(alert_type="price_change", severity="medium"),
            _make_alert(alert_type="competitor", severity="high"),
        ]

        session.execute = AsyncMock(side_effect=[_scalars_all_result(alerts)])

        result = await svc.get_alert_analytics()
        assert result.total_alerts_7d == 3
        assert result.by_type == {"price_change": 2, "competitor": 1}
        assert result.by_severity == {"high": 2, "medium": 1}

    @pytest.mark.asyncio
    @_patch_sql
    async def test_resolution_time_none(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[_scalars_all_result([])])

        result = await svc.get_alert_analytics()
        assert result.avg_resolution_time_hours is None


# ──────────────────────────────────────────────
# get_sentiment_trend
# ──────────────────────────────────────────────
class TestGetSentimentTrend:

    @pytest.mark.asyncio
    @_patch_sql
    async def test_empty_timeline(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[_rows_result([])])

        result = await svc.get_sentiment_trend()
        assert result.timeline == []
        assert result.trend == "stable"
        assert result.current_score is None

    @pytest.mark.asyncio
    @_patch_sql
    async def test_with_data_points(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        now = datetime.utcnow()
        rows = []
        for i in range(6):
            row = MagicMock()
            row.bucket_time = now - timedelta(days=5 - i)
            row.avg_score = 0.5 + i * 0.05
            row.mention_count = 10 + i
            rows.append(row)

        session.execute = AsyncMock(side_effect=[_rows_result(rows)])

        result = await svc.get_sentiment_trend(days=7)
        assert len(result.timeline) == 6
        assert result.period_days == 7

    @pytest.mark.asyncio
    @_patch_sql
    async def test_trend_up(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        now = datetime.utcnow()
        scores = [0.3, 0.32, 0.31, 0.7, 0.72, 0.71]
        rows = []
        for i, score in enumerate(scores):
            row = MagicMock()
            row.bucket_time = now - timedelta(days=5 - i)
            row.avg_score = score
            row.mention_count = 10
            rows.append(row)

        session.execute = AsyncMock(side_effect=[_rows_result(rows)])

        result = await svc.get_sentiment_trend()
        assert result.trend == "up"
        assert result.change > 0.05

    @pytest.mark.asyncio
    @_patch_sql
    async def test_trend_down(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        now = datetime.utcnow()
        scores = [0.8, 0.78, 0.79, 0.3, 0.28, 0.29]
        rows = []
        for i, score in enumerate(scores):
            row = MagicMock()
            row.bucket_time = now - timedelta(days=5 - i)
            row.avg_score = score
            row.mention_count = 10
            rows.append(row)

        session.execute = AsyncMock(side_effect=[_rows_result(rows)])

        result = await svc.get_sentiment_trend()
        assert result.trend == "down"
        assert result.change < -0.05

    @pytest.mark.asyncio
    @_patch_sql
    async def test_trend_stable(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        now = datetime.utcnow()
        rows = []
        for i in range(4):
            row = MagicMock()
            row.bucket_time = now - timedelta(days=3 - i)
            row.avg_score = 0.60 + (i * 0.01)
            row.mention_count = 10
            rows.append(row)

        session.execute = AsyncMock(side_effect=[_rows_result(rows)])

        result = await svc.get_sentiment_trend()
        assert result.trend == "stable"

    @pytest.mark.asyncio
    @_patch_sql
    async def test_with_product_id(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(side_effect=[_rows_result([])])

        result = await svc.get_sentiment_trend(product_id="prod-42")
        assert result.product_id == "prod-42"

    @pytest.mark.asyncio
    @_patch_sql
    async def test_single_data_point(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        row = MagicMock()
        row.bucket_time = datetime.utcnow()
        row.avg_score = 0.65
        row.mention_count = 5

        session.execute = AsyncMock(side_effect=[_rows_result([row])])

        result = await svc.get_sentiment_trend()
        assert len(result.timeline) == 1
        assert result.current_score is not None

    @pytest.mark.asyncio
    @_patch_sql
    async def test_none_avg_score_defaults_zero(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        row = MagicMock()
        row.bucket_time = datetime.utcnow()
        row.avg_score = None
        row.mention_count = 0

        session.execute = AsyncMock(side_effect=[_rows_result([row])])

        result = await svc.get_sentiment_trend()
        assert result.timeline[0].score == 0.0


# ──────────────────────────────────────────────
# _get_average_sentiment
# ──────────────────────────────────────────────
class TestGetAverageSentiment:

    @pytest.mark.asyncio
    @_patch_sql
    async def test_returns_float(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(return_value=_scalar_one_result(0.723456))

        result = await svc._get_average_sentiment(hours=24)
        assert result == 0.723

    @pytest.mark.asyncio
    @_patch_sql
    async def test_returns_none_when_no_data(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(return_value=_scalar_one_result(None))

        result = await svc._get_average_sentiment(hours=24)
        assert result is None

    @pytest.mark.asyncio
    @_patch_sql
    async def test_with_offset(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(return_value=_scalar_one_result(0.55))

        result = await svc._get_average_sentiment(hours=24, offset_hours=24)
        assert result == 0.55

    @pytest.mark.asyncio
    @_patch_sql
    async def test_rounds_to_3_decimals(self):
        session = _make_session()
        svc = AnalyticsService(session=session, user_id="user-1")

        session.execute = AsyncMock(return_value=_scalar_one_result(0.123456789))

        result = await svc._get_average_sentiment()
        assert result == 0.123
        