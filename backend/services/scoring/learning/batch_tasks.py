"""
Batch Tasks — Celery tasks for the Tier 2 weekly learning cycle.

Schedule (via Celery Beat in workers/scheduler.py):
  - weekly_feature_compute:  Sunday 04:00 UTC
  - weekly_prior_update:     Sunday 05:00 UTC  (after features computed)
  - refresh_context_cache:   Sunday 05:30 UTC  (after priors updated)

These three tasks run in sequence. Each one is independently idempotent
(safe to retry). Together they form the weekly learning cycle:

  1. Query DB for outcome records from the last 90 days
  2. FeatureEngineer.compute() → CategoryFeatures per category
  3. PriorUpdater.update_all() → dampened Bayesian prior updates
  4. Cache CategoryFeatures for ContextInjector at recommendation time

The Celery app import and DB session are deferred so this module can
be tested with pure-Python mocks. The orchestration logic lives in
LearningCycleOrchestrator, which is framework-agnostic.

Phase 3 Intelligence Environment — Block A, File 4.

Place at: backend/services/scoring/learning/batch_tasks.py
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .context_injector import ContextInjector, ScoringContext
from .feature_engineer import CategoryFeatures, FeatureEngineer, OutcomeRecord
from .prior_updater import PriorUpdater, UpdateConfig, UpdateResult

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# CYCLE RESULT: Full audit of a learning cycle
# ──────────────────────────────────────────────────────────


@dataclass
class CycleResult:
    """Complete audit trail for one weekly learning cycle."""

    cycle_id: str
    started_at: datetime
    completed_at: datetime | None = None

    # Step 1: Data fetch
    outcome_records_fetched: int = 0
    fetch_time_ms: float = 0

    # Step 2: Feature computation
    categories_computed: int = 0
    features_time_ms: float = 0

    # Step 3: Prior updates
    prior_update_result: UpdateResult | None = None
    prior_time_ms: float = 0

    # Step 4: Cache refresh
    categories_cached: int = 0
    cache_time_ms: float = 0

    # Overall
    total_time_ms: float = 0
    success: bool = False
    error: str | None = None

    @property
    def summary(self) -> str:
        status = "SUCCESS" if self.success else f"FAILED: {self.error}"
        updated = 0
        skipped = 0
        if self.prior_update_result:
            updated = self.prior_update_result.total_categories_updated
            skipped = self.prior_update_result.total_categories_skipped
        return (
            f"Cycle {self.cycle_id}: {status} | "
            f"{self.outcome_records_fetched} outcomes → "
            f"{self.categories_computed} categories → "
            f"{updated} priors updated, {skipped} skipped | "
            f"{self.total_time_ms:.0f}ms"
        )


# ──────────────────────────────────────────────────────────
# FEATURE CACHE: In-memory (swap for Redis in production)
# ──────────────────────────────────────────────────────────


class FeatureCache:
    """
    Cache for CategoryFeatures consumed by ContextInjector.

    Default: in-memory dict. In production, subclass and override
    set/get/list to use Redis or another shared cache.

    This cache is read at recommendation time (hot path) and written
    weekly by batch_tasks. Thread-safe for reads (dict reads are atomic
    in CPython). Writes happen only during the weekly cycle.
    """

    def __init__(self):
        self._store: dict[str, CategoryFeatures] = {}
        self._updated_at: datetime | None = None

    def set(self, category: str, features: CategoryFeatures) -> None:
        """Cache features for a category."""
        self._store[category] = features
        self._updated_at = datetime.now(UTC)

    def get(self, category: str) -> CategoryFeatures | None:
        """Retrieve cached features. Returns None if not cached."""
        return self._store.get(category)

    def set_batch(self, features_dict: dict[str, CategoryFeatures]) -> int:
        """Cache multiple categories at once. Returns count cached."""
        for cat, feat in features_dict.items():
            self._store[cat] = feat
        self._updated_at = datetime.now(UTC)
        return len(features_dict)

    def list_categories(self) -> list[str]:
        """List all cached category keys."""
        return list(self._store.keys())

    @property
    def updated_at(self) -> datetime | None:
        return self._updated_at

    @property
    def size(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        """Clear all cached features."""
        self._store.clear()
        self._updated_at = None


# ──────────────────────────────────────────────────────────
# ORCHESTRATOR: Framework-agnostic learning cycle
# ──────────────────────────────────────────────────────────


class LearningCycleOrchestrator:
    """
    Runs the complete weekly learning cycle.

    Framework-agnostic: no Celery dependency. The Celery tasks
    (at the bottom of this file) delegate to this class.

    Dependencies are injected via constructor:
    - outcome_fetcher: callable that returns list[OutcomeRecord]
    - prior_store: CategoryPriorStore instance
    - feature_cache: FeatureCache instance
    - update_config: dampening configuration

    Usage:
        orchestrator = LearningCycleOrchestrator(
            outcome_fetcher=lambda days: query_db(days),
            prior_store=scoring_engine.prior_store,
            feature_cache=app_feature_cache,
        )
        result = orchestrator.run_full_cycle()
    """

    def __init__(
        self,
        outcome_fetcher: Callable[[int], Sequence[OutcomeRecord]],
        prior_store: Any,  # CategoryPriorStore (duck-typed)
        feature_cache: FeatureCache,
        update_config: UpdateConfig | None = None,
        lookback_days: int = 90,
    ):
        self._fetcher = outcome_fetcher
        self._feature_engine = FeatureEngineer()
        self._prior_updater = PriorUpdater(prior_store, update_config)
        self._context_injector = ContextInjector()
        self._cache = feature_cache
        self._lookback_days = lookback_days
        self._history: list[CycleResult] = []

    @property
    def feature_engine(self) -> FeatureEngineer:
        return self._feature_engine

    @property
    def prior_updater(self) -> PriorUpdater:
        return self._prior_updater

    @property
    def context_injector(self) -> ContextInjector:
        return self._context_injector

    @property
    def cache(self) -> FeatureCache:
        return self._cache

    @property
    def history(self) -> list[CycleResult]:
        return list(self._history)

    def run_full_cycle(self, cycle_id: str | None = None) -> CycleResult:
        """
        Execute the complete learning cycle:
          1. Fetch outcomes
          2. Compute features
          3. Update priors
          4. Refresh cache

        Returns CycleResult with full audit trail.
        """
        if cycle_id is None:
            cycle_id = datetime.now(UTC).strftime("cycle_%Y%m%d_%H%M%S")

        result = CycleResult(
            cycle_id=cycle_id,
            started_at=datetime.now(UTC),
        )

        total_start = time.monotonic()

        try:
            # ── Step 1: Fetch outcome records ──
            t0 = time.monotonic()
            outcomes = self._fetcher(self._lookback_days)
            result.outcome_records_fetched = len(outcomes)
            result.fetch_time_ms = (time.monotonic() - t0) * 1000

            if not outcomes:
                result.success = True
                result.completed_at = datetime.now(UTC)
                result.total_time_ms = (time.monotonic() - total_start) * 1000
                logger.info("Learning cycle %s: no outcomes to process", cycle_id)
                self._history.append(result)
                return result

            # ── Step 2: Compute features ──
            t1 = time.monotonic()
            features_dict = self._feature_engine.compute(outcomes)
            result.categories_computed = len(features_dict)
            result.features_time_ms = (time.monotonic() - t1) * 1000

            # ── Step 3: Update priors ──
            t2 = time.monotonic()
            update_result = self._prior_updater.update_all(features_dict)
            result.prior_update_result = update_result
            result.prior_time_ms = (time.monotonic() - t2) * 1000

            # ── Step 4: Cache features for ContextInjector ──
            t3 = time.monotonic()
            result.categories_cached = self._cache.set_batch(features_dict)
            result.cache_time_ms = (time.monotonic() - t3) * 1000

            result.success = True

        except Exception as e:
            result.error = f"{type(e).__name__}: {e!s}"
            logger.exception("Learning cycle %s failed: %s", cycle_id, result.error)

        result.completed_at = datetime.now(UTC)
        result.total_time_ms = (time.monotonic() - total_start) * 1000

        self._history.append(result)
        logger.info(result.summary)

        return result

    def run_features_only(self, outcomes: Sequence[OutcomeRecord]) -> dict[str, CategoryFeatures]:
        """
        Compute features without updating priors or cache.

        Useful for dry-run analysis or testing.
        """
        return self._feature_engine.compute(outcomes)

    def run_prior_update_only(self, features_dict: dict[str, CategoryFeatures]) -> UpdateResult:
        """
        Update priors from pre-computed features without fetching or caching.

        Useful for replaying historical data or testing dampening.
        """
        return self._prior_updater.update_all(features_dict)

    def get_context_for_category(self, category: str) -> tuple[ScoringContext | None, str]:
        """
        Get cached context for a category at recommendation time.

        Returns (ScoringContext, agent_text) or (None, "") if not cached.
        """
        features = self._cache.get(category)
        if features is None:
            return None, ""
        return self._context_injector.build(features)


# ──────────────────────────────────────────────────────────
# DB QUERY BUILDER (production implementation sketch)
# ──────────────────────────────────────────────────────────


def build_outcome_fetcher_sql(lookback_days: int = 90) -> str:
    """
    SQL query to fetch outcome records for the learning cycle.

    This is the query the Celery task executes against PostgreSQL.
    Returns rows that map directly to OutcomeRecord fields.

    The actual DB session management happens in the Celery task,
    not here — keeping this as a pure string builder.
    """
    return f"""
    SELECT
        pr.recommendation_id,
        pr.category_id AS category,
        pr.created_at,
        pr.recommended_price,
        pr.original_price,
        pr.recommended_change_pct,
        pr.confidence_score,
        po.action,
        po.actual_price_set,
        po.merchant_modified_to,
        pi.revenue_baseline_7d AS revenue_before_7d,
        pi.revenue_after_7d,
        pi.revenue_delta_pct,
        pi.units_baseline_7d AS units_before_7d,
        pi.units_after_7d,
        pi.margin_before,
        pi.margin_after,
        po.strategy_arm,
        po.is_exploration
    FROM pricing_recommendations pr
    JOIN pricing_outcomes po
        ON pr.recommendation_id = po.recommendation_id
    LEFT JOIN pricing_impacts pi
        ON pr.recommendation_id = pi.recommendation_id
        AND pi.measurement_window = '7d'
    WHERE pr.created_at >= NOW() - INTERVAL '{lookback_days} days'
        AND po.action IS NOT NULL
    ORDER BY pr.created_at DESC
    """


def row_to_outcome_record(row: dict) -> OutcomeRecord:
    """
    Convert a DB row (dict) to an OutcomeRecord.

    The Celery task calls this for each row returned by the SQL query.
    Handles type coercion and None values.
    """
    return OutcomeRecord(
        recommendation_id=str(row["recommendation_id"]),
        category=str(row.get("category", "unknown")),
        created_at=row["created_at"],
        recommended_price=float(row["recommended_price"]),
        original_price=float(row["original_price"]),
        recommended_change_pct=float(row.get("recommended_change_pct", 0)),
        confidence_score=float(row.get("confidence_score", 0.5)),
        action=str(row["action"]),
        actual_price_set=float(row["actual_price_set"]) if row.get("actual_price_set") else None,
        merchant_modified_to=float(row["merchant_modified_to"]) if row.get("merchant_modified_to") else None,
        revenue_before_7d=float(row["revenue_before_7d"]) if row.get("revenue_before_7d") else None,
        revenue_after_7d=float(row["revenue_after_7d"]) if row.get("revenue_after_7d") else None,
        revenue_delta_pct=float(row["revenue_delta_pct"]) if row.get("revenue_delta_pct") else None,
        units_before_7d=int(row["units_before_7d"]) if row.get("units_before_7d") else None,
        units_after_7d=int(row["units_after_7d"]) if row.get("units_after_7d") else None,
        margin_before=float(row["margin_before"]) if row.get("margin_before") else None,
        margin_after=float(row["margin_after"]) if row.get("margin_after") else None,
        strategy_arm=str(row["strategy_arm"]) if row.get("strategy_arm") else None,
        is_exploration=bool(row.get("is_exploration", False)),
    )


# ──────────────────────────────────────────────────────────
# CELERY BEAT SCHEDULE (add to workers/scheduler.py)
# ──────────────────────────────────────────────────────────

CELERY_BEAT_SCHEDULE = {
    "weekly-feature-compute": {
        "task": "services.scoring.learning.batch_tasks.weekly_feature_compute",
        "schedule": {
            "minute": 0,
            "hour": 4,
            "day_of_week": 0,  # Sunday
        },
        "description": "Compute per-category features from 90-day outcomes",
    },
    "weekly-prior-update": {
        "task": "services.scoring.learning.batch_tasks.weekly_prior_update",
        "schedule": {
            "minute": 0,
            "hour": 5,
            "day_of_week": 0,  # Sunday
        },
        "description": "Update Bayesian priors from computed features",
    },
    "weekly-context-cache-refresh": {
        "task": "services.scoring.learning.batch_tasks.refresh_context_cache",
        "schedule": {
            "minute": 30,
            "hour": 5,
            "day_of_week": 0,  # Sunday
        },
        "description": "Refresh ContextInjector cache from latest features",
    },
}


# ──────────────────────────────────────────────────────────
# CELERY TASKS (production wiring)
#
# These are thin wrappers around LearningCycleOrchestrator.
# The actual Celery app import is deferred to avoid import
# issues when this module is tested without Celery installed.
#
# In production, add to workers/tasks.py:
#   from services.scoring.learning.batch_tasks import (
#       weekly_feature_compute,
#       weekly_prior_update,
#       refresh_context_cache,
#   )
# ──────────────────────────────────────────────────────────


def _get_celery_app():
    """Deferred import of the Celery app."""
    try:
        from workers.celery_app import celery_app

        return celery_app
    except ImportError:
        return None


def _get_orchestrator() -> LearningCycleOrchestrator:
    """
    Build the orchestrator with production dependencies.

    This is called once per task invocation. In production,
    the prior_store and feature_cache should be singletons
    managed by the application lifecycle.
    """
    # Deferred production imports
    from services.scoring import ScoringEngine

    # Get the singleton scoring engine (which owns the prior store)
    engine = ScoringEngine()

    # Feature cache — in production, use Redis-backed implementation
    # For now, use module-level singleton
    global _feature_cache
    if "_feature_cache" not in globals() or _feature_cache is None:
        _feature_cache = FeatureCache()

    def fetch_outcomes(lookback_days: int) -> list[OutcomeRecord]:
        """Query DB for outcome records."""
        from database.session import get_db_session

        sql = build_outcome_fetcher_sql(lookback_days)
        with get_db_session() as session:
            rows = session.execute(sql).mappings().all()
            return [row_to_outcome_record(dict(r)) for r in rows]

    return LearningCycleOrchestrator(
        outcome_fetcher=fetch_outcomes,
        prior_store=engine.prior_store,
        feature_cache=_feature_cache,
    )


# Module-level cache singleton (replaced by Redis in production)
_feature_cache: FeatureCache | None = None


def get_feature_cache() -> FeatureCache:
    """
    Get the module-level feature cache singleton.

    Called by the recommendation service to retrieve cached
    CategoryFeatures for ContextInjector.
    """
    global _feature_cache
    if _feature_cache is None:
        _feature_cache = FeatureCache()
    return _feature_cache
