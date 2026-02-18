"""
Tests for OutcomeBenchmarkService (services/pricing/outcome_benchmarks.py).

Covers:
1. Category benchmarks (materialized view + k-anonymity)
2. Category benchmarks fallback (programmatic when view unavailable)
3. Available categories (view + fallback)
4. Data gap failure rates (cross-merchant view + user-scoped programmatic)
5. Scout priority queue (interval mapping from failure gaps)
6. Strategist context (prompt generation from benchmarks)
7. View refresh (concurrent + fallback)
8. Static helpers (optimal range, source breakdown)

The source uses:
  result.mappings().first()  → for single-row view queries
  result.mappings().all()    → for multi-row view queries
  result.scalars().all()     → for ORM queries in fallback paths

Place at: backend/tests/unit/test_benchmark_views.py
Run: pytest backend/tests/unit/test_benchmark_views.py -v
"""

import sys
import types
from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# ══════════════════════════════════════════════════════════════════
# sys.modules ISOLATION
# ══════════════════════════════════════════════════════════════════

_saved = {}
for _key in ["db.session", "core.db.session"]:
    if _key in sys.modules:
        _saved[_key] = sys.modules[_key]

_mock_db = types.ModuleType("db.session")
_mock_db.get_session = MagicMock()
sys.modules.setdefault("db.session", _mock_db)

_mock_core_db = types.ModuleType("core.db.session")
_mock_core_db.get_session = MagicMock()
sys.modules.setdefault("core.db.session", _mock_core_db)

from backend.services.pricing.outcome_benchmarks import OutcomeBenchmarkService

# Pull enums from already-loaded module
_outcome_mod = sys.modules["models.recommendation_outcome"]
OutcomeLabel = _outcome_mod.OutcomeLabel


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _view_row_benchmarks(
    category="Electronics",
    merchant_count=8,
    total_outcomes=50,
    positive_count=30,
    success_rate=60.0,
    avg_confidence=0.72,
    avg_lift_7d=3.5,
    avg_lift_14d=4.2,
    avg_lift_30d=5.1,
    change_p25=-3.0,
    change_median=-5.0,
    change_p75=-8.0,
    positive_sample_size=30,
    refreshed_at="2026-02-17T04:30:00",
):
    """Dict-like row from mv_category_benchmarks."""
    return {
        "product_category": category,
        "merchant_count": merchant_count,
        "total_outcomes": total_outcomes,
        "positive_count": positive_count,
        "success_rate": success_rate,
        "avg_confidence": avg_confidence,
        "avg_lift_7d": avg_lift_7d,
        "avg_lift_14d": avg_lift_14d,
        "avg_lift_30d": avg_lift_30d,
        "change_p25": change_p25,
        "change_median": change_median,
        "change_p75": change_p75,
        "positive_sample_size": positive_sample_size,
        "refreshed_at": refreshed_at,
    }


def _view_row_data_gap(
    category="Electronics",
    low_data_failure_rate=45.0,
    high_data_failure_rate=15.0,
    failure_gap=30.0,
    low_data_outcomes=20,
    high_data_outcomes=30,
    total_outcomes=50,
    scout_priority="high",
):
    """Dict-like row from mv_category_data_gaps (using SQL aliases)."""
    return {
        "product_category": category,
        "low_data_failure_rate": low_data_failure_rate,
        "high_data_failure_rate": high_data_failure_rate,
        "failure_gap": failure_gap,
        "low_data_outcomes": low_data_outcomes,
        "high_data_outcomes": high_data_outcomes,
        "total_outcomes": total_outcomes,
        "scout_priority": scout_priority,
    }

def _make_db_for_view(mappings_first=None, mappings_all=None, scalars_all=None):
    """
    Build a mock AsyncSession that handles the source's query patterns.

    For view queries: result.mappings().first() or result.mappings().all()
    For ORM queries (source breakdown fallback): result.scalars().all()

    Uses side_effect to handle multiple sequential db.execute() calls.
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    # Build a mock result that supports both .mappings() and .scalars()
    def _make_result(m_first=None, m_all=None, s_all=None):
        result = MagicMock()
        mock_mappings = MagicMock()
        mock_mappings.first.return_value = m_first
        mock_mappings.all.return_value = m_all or []
        result.mappings.return_value = mock_mappings

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = s_all or []
        result.scalars.return_value = mock_scalars

        return result

    # First call returns the view result, subsequent calls return empty ORM results
    first_result = _make_result(m_first=mappings_first, m_all=mappings_all)
    fallback_result = _make_result(s_all=scalars_all or [])

    db.execute = AsyncMock(side_effect=[first_result, fallback_result, fallback_result, fallback_result])

    return db


def _make_db_view_raises():
    """DB where the first execute raises (simulating missing view), subsequent work."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    # First call raises (view doesn't exist), second returns empty ORM result
    fallback_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_scalars.first.return_value = None
    fallback_result.scalars.return_value = mock_scalars
    mock_mappings = MagicMock()
    mock_mappings.all.return_value = []
    mock_mappings.first.return_value = None
    fallback_result.mappings.return_value = mock_mappings

    db.execute = AsyncMock(side_effect=[
        Exception("relation mv_category_benchmarks does not exist"),
        fallback_result,
        fallback_result,
    ])

    return db


def _make_outcome(
    user_id=None,
    category="Electronics",
    outcome_label=None,
    confidence=Decimal("0.72"),
    change_percent=Decimal("-5.00"),
    revenue_lift_7d=3.5,
    data_completeness=0.85,
    recommendation_source="rule_based",
):
    """Build a mock RecommendationOutcome for programmatic fallback tests."""
    o = MagicMock()
    o.user_id = user_id or uuid4()
    o.product_category = category
    o.outcome_label = outcome_label or OutcomeLabel.POSITIVE
    o.original_confidence = confidence
    o.price_change_percent = change_percent
    o.revenue_lift_7d = revenue_lift_7d
    o.data_completeness = data_completeness
    o.recommendation_source = recommendation_source
    return o


# ══════════════════════════════════════════════════════════════════
# 1. CATEGORY BENCHMARKS (materialized view)
# ══════════════════════════════════════════════════════════════════

class TestCategoryBenchmarksView:

    @pytest.mark.asyncio
    async def test_returns_benchmarks_from_view(self):
        row = _view_row_benchmarks(merchant_count=8)
        db = _make_db_for_view(mappings_first=row)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_category_benchmarks("Electronics")

        assert result is not None
        assert result["category"] == "Electronics"
        assert result["merchant_count"] == 8
        assert result["source"] == "materialized_view"

    @pytest.mark.asyncio
    async def test_k_anonymity_returns_none(self):
        row = _view_row_benchmarks(merchant_count=3)  # Below default k=5
        db = _make_db_for_view(mappings_first=row)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_category_benchmarks("Electronics")

        assert result is None

    @pytest.mark.asyncio
    async def test_optimal_range_included(self):
        row = _view_row_benchmarks(
            change_p25=-3.0,
            change_median=-5.0,
            change_p75=-8.0,
            positive_sample_size=30,
        )
        db = _make_db_for_view(mappings_first=row)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_category_benchmarks("Electronics")

        assert result["optimal_price_change_range"] is not None
        assert result["optimal_price_change_range"]["p25"] == -3.0
        assert result["optimal_price_change_range"]["median"] == -5.0

    @pytest.mark.asyncio
    async def test_lift_values_included(self):
        row = _view_row_benchmarks(avg_lift_7d=3.5, avg_lift_14d=4.2, avg_lift_30d=5.1)
        db = _make_db_for_view(mappings_first=row)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_category_benchmarks("Electronics")

        assert result["avg_revenue_lift_7d"] == 3.5
        assert result["avg_revenue_lift_14d"] == 4.2
        assert result["avg_revenue_lift_30d"] == 5.1

    @pytest.mark.asyncio
    async def test_no_optimal_range_when_sample_too_small(self):
        row = _view_row_benchmarks(positive_sample_size=2, change_p25=-3.0)
        db = _make_db_for_view(mappings_first=row)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_category_benchmarks("Electronics")

        assert result["optimal_price_change_range"] is None


# ══════════════════════════════════════════════════════════════════
# 2. CATEGORY BENCHMARKS FALLBACK
# ══════════════════════════════════════════════════════════════════

class TestCategoryBenchmarksFallback:

    @pytest.mark.asyncio
    async def test_falls_back_when_view_missing(self):
        db = _make_db_view_raises()

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_category_benchmarks("Electronics")

        # Falls back to programmatic, which returns None for empty data
        assert result is None

    @pytest.mark.asyncio
    async def test_programmatic_with_outcomes(self):
        """Directly test _get_category_benchmarks_programmatic."""
        users = [uuid4() for _ in range(6)]  # 6 distinct merchants > k=5
        outcomes = []
        for i, uid in enumerate(users):
            outcomes.append(_make_outcome(
                user_id=uid,
                outcome_label=OutcomeLabel.POSITIVE if i < 4 else OutcomeLabel.NEGATIVE,
            ))

        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = outcomes
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        svc = OutcomeBenchmarkService(db)
        result = await svc._get_category_benchmarks_programmatic("Electronics")

        assert result is not None
        assert result["merchant_count"] == 6
        assert result["source"] == "programmatic"
        assert result["success_rate"] > 0


# ══════════════════════════════════════════════════════════════════
# 3. AVAILABLE CATEGORIES
# ══════════════════════════════════════════════════════════════════

class TestAvailableCategories:

    @pytest.mark.asyncio
    async def test_returns_from_view(self):
        rows = [
            {"product_category": "Electronics", "merchant_count": 10, "outcome_count": 50},
            {"product_category": "Clothing", "merchant_count": 7, "outcome_count": 30},
        ]
        db = _make_db_for_view(mappings_all=rows)

        svc = OutcomeBenchmarkService(db)
        result = await svc.list_available_categories()

        assert len(result) == 2
        assert result[0]["category"] == "Electronics"

    @pytest.mark.asyncio
    async def test_empty_view_falls_back(self):
        db = _make_db_view_raises()

        svc = OutcomeBenchmarkService(db)
        result = await svc.list_available_categories()

        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════
# 4. DATA GAP FAILURE RATES
# ══════════════════════════════════════════════════════════════════

class TestDataGapFailureRates:

    @pytest.mark.asyncio
    async def test_cross_merchant_uses_view(self):
        rows = [
            _view_row_data_gap(category="Electronics", failure_gap=30.0),
            _view_row_data_gap(category="Clothing", failure_gap=15.0),
        ]
        db = _make_db_for_view(mappings_all=rows)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_data_gap_failure_rates(user_id=None)

        assert len(result) == 2
        assert result[0]["category"] == "Electronics"
        assert result[0]["failure_gap"] == 30.0

    @pytest.mark.asyncio
    async def test_user_scoped_uses_programmatic(self):
        """User-scoped queries always use programmatic path."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        db.execute = AsyncMock(return_value=mock_result)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_data_gap_failure_rates(user_id=uuid4())

        assert isinstance(result, list)


# ══════════════════════════════════════════════════════════════════
# 5. SCOUT PRIORITY QUEUE
# ══════════════════════════════════════════════════════════════════

class TestScoutPriorityQueue:

    @pytest.mark.asyncio
    async def test_high_gap_gets_1h_interval(self):
        rows = [_view_row_data_gap(
            category="Electronics",
            failure_gap=25.0,
            low_data_outcomes=5,
            scout_priority="high",
        )]
        db = _make_db_for_view(mappings_all=rows)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_scout_priority_queue(user_id=None)

        assert len(result) == 1
        assert result[0]["suggested_scrape_interval_hours"] == 1

    @pytest.mark.asyncio
    async def test_medium_gap_gets_2h_interval(self):
        rows = [_view_row_data_gap(
            category="Clothing",
            failure_gap=15.0,
            low_data_outcomes=5,
            scout_priority="medium",
        )]
        db = _make_db_for_view(mappings_all=rows)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_scout_priority_queue(user_id=None)

        assert len(result) == 1
        assert result[0]["suggested_scrape_interval_hours"] == 2

    @pytest.mark.asyncio
    async def test_low_gap_gets_4h_interval(self):
        rows = [_view_row_data_gap(
            category="Books",
            failure_gap=5.0,
            low_data_outcomes=5,
            scout_priority="low",
        )]
        db = _make_db_for_view(mappings_all=rows)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_scout_priority_queue(user_id=None)

        assert len(result) == 1
        assert result[0]["suggested_scrape_interval_hours"] == 4

    @pytest.mark.asyncio
    async def test_filters_low_evidence_categories(self):
        """Categories with low_data_outcomes < 2 are excluded."""
        rows = [_view_row_data_gap(
            category="Niche",
            failure_gap=50.0,
            low_data_outcomes=1  # Below threshold
        )]
        db = _make_db_for_view(mappings_all=rows)

        svc = OutcomeBenchmarkService(db)
        result = await svc.get_scout_priority_queue(user_id=None)

        assert len(result) == 0


# ══════════════════════════════════════════════════════════════════
# 6. STRATEGIST CONTEXT
# ══════════════════════════════════════════════════════════════════

class TestStrategistContext:

    @pytest.mark.asyncio
    async def test_generates_prompt_string(self):
        row = _view_row_benchmarks(
            merchant_count=8,
            success_rate=62.5,
            avg_lift_7d=3.5,
            avg_lift_30d=5.1,
        )
        db = _make_db_for_view(mappings_first=row)

        svc = OutcomeBenchmarkService(db)
        context = await svc.get_category_context_for_strategist("Electronics")

        assert context is not None
        assert "Electronics" in context
        assert "62.5%" in context

    @pytest.mark.asyncio
    async def test_returns_none_when_insufficient_data(self):
        row = _view_row_benchmarks(merchant_count=3)  # Below k=5
        db = _make_db_for_view(mappings_first=row)

        svc = OutcomeBenchmarkService(db)
        context = await svc.get_category_context_for_strategist("Electronics")

        assert context is None

    @pytest.mark.asyncio
    async def test_includes_lift_when_available(self):
        row = _view_row_benchmarks(avg_lift_7d=3.5, avg_lift_30d=5.1)
        db = _make_db_for_view(mappings_first=row)

        svc = OutcomeBenchmarkService(db)
        context = await svc.get_category_context_for_strategist("Electronics")

        assert "7-day" in context
        assert "30-day" in context

    @pytest.mark.asyncio
    async def test_includes_optimal_range(self):
        row = _view_row_benchmarks(
            change_p25=-3.0, change_median=-5.0, change_p75=-8.0,
            positive_sample_size=30,
        )
        db = _make_db_for_view(mappings_first=row)

        svc = OutcomeBenchmarkService(db)
        context = await svc.get_category_context_for_strategist("Electronics")

        assert "Optimal" in context or "optimal" in context


# ══════════════════════════════════════════════════════════════════
# 7. VIEW REFRESH
# ══════════════════════════════════════════════════════════════════

class TestRefreshViews:

    @pytest.mark.asyncio
    async def test_refreshes_all_three_views(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        svc = OutcomeBenchmarkService(db)
        result = await svc.refresh_views()

        assert "mv_category_benchmarks" in result
        assert "mv_category_data_gaps" in result
        assert "mv_available_categories" in result

    @pytest.mark.asyncio
    async def test_concurrent_refresh_fallback(self):
        """When CONCURRENTLY fails, falls back to regular refresh."""
        call_count = 0

        async def _execute_side_effect(stmt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            stmt_str = str(stmt) if hasattr(stmt, 'text') else str(stmt)
            if "CONCURRENTLY" in stmt_str:
                raise Exception("Cannot refresh concurrently")
            return MagicMock()

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=_execute_side_effect)
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        svc = OutcomeBenchmarkService(db)
        result = await svc.refresh_views()

        # All three should have been refreshed via regular path
        for view_name, status in result.items():
            assert status in ("refreshed", "refreshed_regular"), f"{view_name}: {status}"

    @pytest.mark.asyncio
    async def test_total_failure_reports_error(self):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("DB down"))
        db.commit = AsyncMock()
        db.rollback = AsyncMock()

        svc = OutcomeBenchmarkService(db)
        result = await svc.refresh_views()

        for view_name, status in result.items():
            assert "failed" in status


# ══════════════════════════════════════════════════════════════════
# 8. STATIC HELPERS
# ══════════════════════════════════════════════════════════════════

class TestStaticHelpers:

    def test_optimal_range_with_enough_data(self):
        outcomes = []
        for pct in [-2, -3, -4, -5, -6, -7, -8, -9, -10]:
            o = MagicMock()
            o.outcome_label = OutcomeLabel.POSITIVE
            o.price_change_percent = Decimal(str(pct))
            outcomes.append(o)

        result = OutcomeBenchmarkService._calculate_optimal_change_range(outcomes)

        assert result is not None
        assert result["sample_size"] == 9
        assert result["p25"] <= result["median"] <= result["p75"]

    def test_optimal_range_insufficient_data(self):
        outcomes = []
        for pct in [-5, -6]:
            o = MagicMock()
            o.outcome_label = OutcomeLabel.POSITIVE
            o.price_change_percent = Decimal(str(pct))
            outcomes.append(o)

        result = OutcomeBenchmarkService._calculate_optimal_change_range(outcomes)
        assert result is None

    def test_source_breakdown_groups_correctly(self):
        outcomes = []
        for i in range(5):
            o = MagicMock()
            o.recommendation_source = "rule_based"
            o.outcome_label = OutcomeLabel.POSITIVE if i < 3 else OutcomeLabel.NEGATIVE
            outcomes.append(o)

        result = OutcomeBenchmarkService._aggregate_by_source(outcomes)

        assert "rule_based" in result
        assert result["rule_based"]["count"] == 5
        assert result["rule_based"]["success_rate"] == 60.0

    def test_source_breakdown_filters_small_samples(self):
        o = MagicMock()
        o.recommendation_source = "ai_agent"
        o.outcome_label = OutcomeLabel.POSITIVE
        outcomes = [o]  # Only 1 outcome — should be filtered

        result = OutcomeBenchmarkService._aggregate_by_source(outcomes)
        assert "ai_agent" not in result


# ══════════════════════════════════════════════════════════════════
# RESTORE sys.modules
# ══════════════════════════════════════════════════════════════════

for _key, _orig in _saved.items():
    sys.modules[_key] = _orig


