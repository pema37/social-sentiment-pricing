"""
Benchmark Refresh Tasks - Celery tasks to refresh materialized views.

Refreshes the three materialized views that power category benchmarks:
  - mv_category_benchmarks
  - mv_category_data_gaps
  - mv_available_categories

Schedule: Daily at 4:30 AM (after the 30d measurement task at 4 AM)
Also callable on-demand via the /api/v1/outcomes/benchmarks/refresh endpoint.

Uses REFRESH CONCURRENTLY so reads aren't blocked during refresh.
Requires the UNIQUE INDEX on each view (created by migration ie002).

Place at: backend/workers/tasks/benchmark_refresh_tasks.py
Then add to celery_app.py include list and beat_schedule.
"""

import asyncio
import re

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from workers.celery_app import celery_app
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# HELPERS (same pattern as outcome_measurement_tasks.py)
# ──────────────────────────────────────────────

def get_task_session_maker():
    """Create a fresh async session maker for Celery tasks."""
    db_url = settings.DATABASE_URL

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "sslmode=" in db_url:
        db_url = re.sub(r'[\?&]sslmode=[^&]*', '', db_url)
        db_url = db_url.replace('?&', '?').replace('&&', '&').rstrip('?&')

    use_ssl = "neon.tech" in db_url or "railway" in db_url

    engine = create_async_engine(
        db_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"ssl": True} if use_ssl else {},
    )

    return sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def run_async(coro):
    """Run async code in sync Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            loop.close()


# ──────────────────────────────────────────────
# ASYNC IMPLEMENTATION
# ──────────────────────────────────────────────

MATERIALIZED_VIEWS = [
    "mv_category_benchmarks",
    "mv_category_data_gaps",
    "mv_available_categories",
]


async def _refresh_benchmark_views():
    """
    Refresh all three materialized views.

    Uses REFRESH CONCURRENTLY so existing data remains readable
    while the refresh runs. Falls back to regular REFRESH if
    concurrent refresh fails (e.g., view has no data yet).
    """
    session_maker = get_task_session_maker()
    results = {}

    async with session_maker() as db:
        for view_name in MATERIALIZED_VIEWS:
            try:
                # Try concurrent refresh first (non-blocking reads)
                await db.execute(
                    text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}")
                )
                await db.commit()
                results[view_name] = "refreshed_concurrently"
                logger.info(f"Refreshed {view_name} concurrently")

            except Exception as e:
                await db.rollback()
                error_msg = str(e).lower()

                # If concurrent fails (empty view, no unique index, etc.),
                # fall back to regular refresh
                if "concurrently" in error_msg or "unique" in error_msg or "has not been populated" in error_msg:
                    try:
                        await db.execute(
                            text(f"REFRESH MATERIALIZED VIEW {view_name}")
                        )
                        await db.commit()
                        results[view_name] = "refreshed_regular"
                        logger.info(f"Refreshed {view_name} (regular, not concurrent)")

                    except Exception as e2:
                        await db.rollback()
                        results[view_name] = f"failed: {e2}"
                        logger.error(f"Failed to refresh {view_name}: {e2}")
                else:
                    results[view_name] = f"failed: {e}"
                    logger.error(f"Failed to refresh {view_name}: {e}")

    logger.info(f"Benchmark view refresh complete: {results}")
    return results


async def _get_view_stats():
    """Get row counts for each materialized view."""
    session_maker = get_task_session_maker()
    stats = {}

    async with session_maker() as db:
        for view_name in MATERIALIZED_VIEWS:
            try:
                result = await db.execute(
                    text(f"SELECT COUNT(*) FROM {view_name}")
                )
                count = result.scalar() or 0
                stats[view_name] = count
            except Exception as e:
                stats[view_name] = f"error: {e}"

    return stats


# ──────────────────────────────────────────────
# CELERY TASKS
# ──────────────────────────────────────────────

@celery_app.task(name="workers.tasks.benchmark_refresh_tasks.refresh_benchmark_views")
def refresh_benchmark_views():
    """
    Refresh all materialized benchmark views.

    Scheduled: Daily at 4:30 AM (after 30d measurement completes at 4 AM)
    Also callable on-demand for immediate refresh.
    """
    return run_async(_refresh_benchmark_views())


@celery_app.task(name="workers.tasks.benchmark_refresh_tasks.benchmark_view_stats")
def benchmark_view_stats():
    """
    Report row counts for materialized views.

    Use: Manual trigger or monitoring dashboard.
    """
    return run_async(_get_view_stats())



