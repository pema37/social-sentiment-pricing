"""
Tests for benchmark_refresh_tasks.py Celery tasks.

Covers:
1. refresh_benchmark_views() — refreshes all 3 views
2. Concurrent refresh fallback — falls back to regular REFRESH
3. Total failure reporting
4. benchmark_view_stats() — row counts for views
5. MATERIALIZED_VIEWS list correctness

The source does NOT use OutcomeBenchmarkService. It runs raw SQL
via text() on a session from get_task_session_maker().

We patch get_task_session_maker to return a mock session factory.

Place at: backend/tests/unit/test_benchmark_refresh_tasks.py
Run: pytest backend/tests/unit/test_benchmark_refresh_tasks.py -v
"""

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ══════════════════════════════════════════════════════════════════
# sys.modules ISOLATION
# ══════════════════════════════════════════════════════════════════

_saved = {}

# Mock db.session / core.db.session (prevent asyncpg connection)
for _key in ["db.session", "core.db.session"]:
    if _key in sys.modules:
        _saved[_key] = sys.modules[_key]
_mock_db = types.ModuleType("db.session")
_mock_db.get_session = MagicMock()
_mock_db.run_async = MagicMock()
_mock_db.get_session_context = MagicMock()
sys.modules.setdefault("db.session", _mock_db)

_mock_core_db = types.ModuleType("core.db.session")
_mock_core_db.get_session = MagicMock()
sys.modules.setdefault("core.db.session", _mock_core_db)

# Mock workers.celery_app (prevent Redis/broker connection)
if "workers.celery_app" not in sys.modules:
    _mock_celery_mod = types.ModuleType("workers.celery_app")
    _mock_celery_app = MagicMock()
    # celery_app.task() should return a decorator that returns the function as-is
    _mock_celery_app.task = lambda *args, **kwargs: lambda fn: fn
    _mock_celery_mod.celery_app = _mock_celery_app
    sys.modules["workers.celery_app"] = _mock_celery_mod
    _saved["workers.celery_app"] = None  # Mark for cleanup

# Mock core.config
if "core.config" not in sys.modules:
    _mock_config_mod = types.ModuleType("core.config")
    _mock_settings = MagicMock()
    _mock_settings.DATABASE_URL = "postgresql://test:test@localhost/test"
    _mock_config_mod.settings = _mock_settings
    sys.modules["core.config"] = _mock_config_mod
    _saved["core.config"] = None

# Mock core.logging
if "core.logging" not in sys.modules:
    _mock_logging_mod = types.ModuleType("core.logging")
    _mock_logging_mod.get_logger = MagicMock(return_value=MagicMock())
    sys.modules["core.logging"] = _mock_logging_mod
    _saved["core.logging"] = None

# Now import the module under test
from workers.tasks.benchmark_refresh_tasks import (
    _refresh_benchmark_views,
    _get_view_stats,
    refresh_benchmark_views,
    benchmark_view_stats,
    MATERIALIZED_VIEWS,
)


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _mock_session_maker(execute_side_effect=None):
    """
    Build a mock session factory that returns an async context manager session.

    The source does:
        async with session_maker() as db:
            await db.execute(text(...))
    """
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=execute_side_effect)
    mock_db.commit = AsyncMock()
    mock_db.rollback = AsyncMock()

    # session_maker() returns an async context manager
    mock_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = mock_ctx

    return mock_factory, mock_db


# ══════════════════════════════════════════════════════════════════
# 1. MATERIALIZED_VIEWS LIST
# ══════════════════════════════════════════════════════════════════

class TestMaterializedViewsList:

    def test_contains_three_views(self):
        assert len(MATERIALIZED_VIEWS) == 3

    def test_contains_expected_views(self):
        assert "mv_category_benchmarks" in MATERIALIZED_VIEWS
        assert "mv_category_data_gaps" in MATERIALIZED_VIEWS
        assert "mv_available_categories" in MATERIALIZED_VIEWS


# ══════════════════════════════════════════════════════════════════
# 2. REFRESH ALL VIEWS — SUCCESS
# ══════════════════════════════════════════════════════════════════

class TestRefreshSuccess:

    @pytest.mark.asyncio
    async def test_refreshes_all_views_concurrently(self):
        mock_factory, mock_db = _mock_session_maker()

        with patch(
            "workers.tasks.benchmark_refresh_tasks.get_task_session_maker",
            return_value=mock_factory.return_value,
        ):
            # get_task_session_maker returns session_maker
            # session_maker() returns async context manager
            # We need to patch so that get_task_session_maker() returns our factory
            pass

        # Direct approach: patch at module level
        with patch(
            "workers.tasks.benchmark_refresh_tasks.get_task_session_maker",
            return_value=mock_factory,
        ):
            result = await _refresh_benchmark_views()

        assert len(result) == 3
        for view_name in MATERIALIZED_VIEWS:
            assert view_name in result
            assert result[view_name] == "refreshed_concurrently"

    @pytest.mark.asyncio
    async def test_execute_called_for_each_view(self):
        mock_factory, mock_db = _mock_session_maker()

        with patch(
            "workers.tasks.benchmark_refresh_tasks.get_task_session_maker",
            return_value=mock_factory,
        ):
            await _refresh_benchmark_views()

        # 3 views = 3 execute calls (one REFRESH CONCURRENTLY each)
        assert mock_db.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_commits_after_each_view(self):
        mock_factory, mock_db = _mock_session_maker()

        with patch(
            "workers.tasks.benchmark_refresh_tasks.get_task_session_maker",
            return_value=mock_factory,
        ):
            await _refresh_benchmark_views()

        assert mock_db.commit.call_count == 3


# ══════════════════════════════════════════════════════════════════
# 3. CONCURRENT REFRESH FALLBACK
# ══════════════════════════════════════════════════════════════════

class TestConcurrentFallback:

    @pytest.mark.asyncio
    async def test_falls_back_to_regular_refresh(self):
        """When CONCURRENTLY fails, falls back to regular REFRESH."""
        call_count = 0

        async def _execute(stmt, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            stmt_str = str(stmt)
            if "CONCURRENTLY" in stmt_str:
                raise Exception("cannot refresh concurrently: no unique index")
            # Regular refresh succeeds
            return MagicMock()

        mock_factory, mock_db = _mock_session_maker(execute_side_effect=_execute)

        with patch(
            "workers.tasks.benchmark_refresh_tasks.get_task_session_maker",
            return_value=mock_factory,
        ):
            result = await _refresh_benchmark_views()

        for view_name in MATERIALIZED_VIEWS:
            assert result[view_name] == "refreshed_regular"

    @pytest.mark.asyncio
    async def test_rollback_called_on_concurrent_failure(self):
        async def _execute(stmt, *args, **kwargs):
            if "CONCURRENTLY" in str(stmt):
                raise Exception("cannot refresh concurrently")
            return MagicMock()

        mock_factory, mock_db = _mock_session_maker(execute_side_effect=_execute)

        with patch(
            "workers.tasks.benchmark_refresh_tasks.get_task_session_maker",
            return_value=mock_factory,
        ):
            await _refresh_benchmark_views()

        # Rollback called once per view (3 views, each concurrent fails)
        assert mock_db.rollback.call_count == 3


# ══════════════════════════════════════════════════════════════════
# 4. TOTAL FAILURE
# ══════════════════════════════════════════════════════════════════

class TestTotalFailure:

    @pytest.mark.asyncio
    async def test_reports_failure_for_all_views(self):
        async def _execute(stmt, *args, **kwargs):
            raise Exception("database is down")

        mock_factory, mock_db = _mock_session_maker(execute_side_effect=_execute)

        with patch(
            "workers.tasks.benchmark_refresh_tasks.get_task_session_maker",
            return_value=mock_factory,
        ):
            result = await _refresh_benchmark_views()

        for view_name in MATERIALIZED_VIEWS:
            assert "failed" in result[view_name]


# ══════════════════════════════════════════════════════════════════
# 5. VIEW STATS
# ══════════════════════════════════════════════════════════════════

class TestViewStats:

    @pytest.mark.asyncio
    async def test_returns_counts_for_all_views(self):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42

        mock_factory, mock_db = _mock_session_maker()
        mock_db.execute = AsyncMock(return_value=mock_result)

        with patch(
            "workers.tasks.benchmark_refresh_tasks.get_task_session_maker",
            return_value=mock_factory,
        ):
            result = await _get_view_stats()

        assert len(result) == 3
        for view_name in MATERIALIZED_VIEWS:
            assert result[view_name] == 42

    @pytest.mark.asyncio
    async def test_handles_missing_view(self):
        async def _execute(stmt, *args, **kwargs):
            raise Exception("relation does not exist")

        mock_factory, mock_db = _mock_session_maker(execute_side_effect=_execute)

        with patch(
            "workers.tasks.benchmark_refresh_tasks.get_task_session_maker",
            return_value=mock_factory,
        ):
            result = await _get_view_stats()

        for view_name in MATERIALIZED_VIEWS:
            assert "error" in str(result[view_name])


# ══════════════════════════════════════════════════════════════════
# 6. CELERY TASK WRAPPERS
# ══════════════════════════════════════════════════════════════════

class TestCeleryWrappers:

    def test_refresh_task_is_callable(self):
        assert callable(refresh_benchmark_views)

    def test_stats_task_is_callable(self):
        assert callable(benchmark_view_stats)


# ══════════════════════════════════════════════════════════════════
# RESTORE sys.modules
# ══════════════════════════════════════════════════════════════════

for _key, _orig in _saved.items():
    if _orig is None:
        sys.modules.pop(_key, None)
    else:
        sys.modules[_key] = _orig


        