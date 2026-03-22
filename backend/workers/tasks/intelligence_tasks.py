"""
Intelligence Environment Celery Tasks
=======================================
Phase 5 — Integration Wiring

Thin Celery wrappers around Phase 3 framework-agnostic orchestrators.
Each task: get DB session > call orchestrator > log result.

Combined Celery Beat Schedule (all phases):
  2:00 AM  — measure_7d_outcomes        (Phase 1, Daily)
  3:00 AM  — measure_14d_outcomes       (Phase 1, Daily)
  4:00 AM  — measure_30d_outcomes       (Phase 1, Daily)
  4:00 AM  — weekly_feature_compute     (Phase 3A, Sunday)
  4:30 AM  — refresh_benchmark_views    (Phase 1, Daily)
  5:00 AM  — weekly_prior_update        (Phase 3A, Sunday)
  5:30 AM  — refresh_context_cache      (Phase 3A, Sunday)
  6:00 AM  — daily_bandit_update        (Phase 3B, Daily)
  6:30 AM  — weekly_convergence_check   (Phase 3B, Sunday)
  7:00 AM  — persist_bandit_state       (Phase 3B, Daily)

Location: backend/workers/tasks/intelligence_tasks.py
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task registry — import the Celery app
# ---------------------------------------------------------------------------


# Lazy import to avoid circular deps at module level
def _get_celery_app():
    from workers.celery_app import celery_app

    return celery_app


def _get_db_session():
    """Get a sync DB session for Celery tasks."""
    from db.session import SessionLocal

    return SessionLocal()


# ---------------------------------------------------------------------------
# Decorator helper for consistent error handling
# ---------------------------------------------------------------------------


def _task_wrapper(task_name: str, fn, *args, **kwargs) -> dict[str, Any]:
    """
    Standard wrapper for all IE tasks:
    - Logs start/end with duration
    - Catches and logs exceptions
    - Returns status dict for monitoring
    """
    start = time.monotonic()
    logger.info("[IE] Starting task: %s", task_name)

    try:
        result = fn(*args, **kwargs)
        duration_ms = (time.monotonic() - start) * 1000
        logger.info("[IE] Task %s completed in %.0fms: %s", task_name, duration_ms, result)
        return {
            "task": task_name,
            "status": "success",
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.now(UTC).isoformat(),
            "result": result,
        }
    except Exception as exc:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error(
            "[IE] Task %s failed after %.0fms: %s",
            task_name,
            duration_ms,
            exc,
            exc_info=True,
        )
        # Re-raise so Celery sees the failure and can trigger retry logic
        raise


# ===================================================================
# Phase 3 Block A: Tier 2 Batch Learning Tasks
# ===================================================================


def weekly_feature_compute_impl() -> dict:
    """
    Compute CategoryFeatures from 90-day outcomes.

    Calls: feature_engineer.compute_all_categories()
    Output: Cached features for prior_updater and context_injector.
    """
    from services.scoring.learning.feature_engineer import FeatureEngineer

    db = _get_db_session()
    try:
        engineer = FeatureEngineer(db_session=db)
        results = engineer.compute_all_categories()
        return {
            "categories_processed": len(results),
            "categories": [r.get("category_id") for r in results],
        }
    finally:
        db.close()


def weekly_prior_update_impl() -> dict:
    """
    Update CategoryPriorStore from computed features.

    Calls: prior_updater.update_all_priors()
    Uses: EMA alpha=0.3, max 20% shift, outlier filtering.
    """
    from services.scoring.learning.prior_updater import PriorUpdater

    db = _get_db_session()
    try:
        updater = PriorUpdater(db_session=db)
        results = updater.update_all_priors()
        return {
            "priors_updated": len(results),
            "categories": [r.get("category_id") for r in results],
        }
    finally:
        db.close()


def refresh_context_cache_impl() -> dict:
    """
    Refresh the ContextInjector cache for hot-path reads.

    Calls: context_injector.refresh_cache()
    Output: Pre-computed context strings for all active categories.
    """
    from services.scoring.learning.context_injector import ContextInjector

    db = _get_db_session()
    try:
        injector = ContextInjector(db_session=db)
        count = injector.refresh_cache()
        return {"categories_cached": count}
    finally:
        db.close()


# ===================================================================
# Phase 3 Block B: Thompson Sampling Experimentation Tasks
# ===================================================================


def daily_bandit_update_impl() -> dict:
    """
    Process unprocessed outcomes through the Thompson Sampling bandit.

    Calls: experiment_manager.process_unprocessed_outcomes()
    Updates: Beta distribution parameters for each arm.
    Marks: pricing_outcomes.bandit_processed = true
    """
    from services.scoring.experimentation.experiment_manager import (
        ExperimentManager,
    )

    db = _get_db_session()
    try:
        manager = ExperimentManager(db_session=db)
        results = manager.process_unprocessed_outcomes()
        return {
            "outcomes_processed": results.get("processed", 0),
            "categories_updated": results.get("categories", 0),
        }
    finally:
        db.close()


def weekly_convergence_check_impl() -> dict:
    """
    Check which categories have a statistically significant winning arm.

    Calls: experiment_manager.check_all_convergence()
    Updates: bandit_state.converged_arm when winner detected.
    """
    from services.scoring.experimentation.experiment_manager import (
        ExperimentManager,
    )

    db = _get_db_session()
    try:
        manager = ExperimentManager(db_session=db)
        results = manager.check_all_convergence()
        return {
            "categories_checked": results.get("checked", 0),
            "newly_converged": results.get("converged", 0),
            "converged_categories": results.get("converged_list", []),
        }
    finally:
        db.close()


def persist_bandit_state_impl() -> dict:
    """
    Serialize bandit state to DB for crash recovery.

    Calls: experiment_manager.persist_state()
    Writes: Full Beta distribution params to bandit_state table.
    """
    from services.scoring.experimentation.experiment_manager import (
        ExperimentManager,
    )

    db = _get_db_session()
    try:
        manager = ExperimentManager(db_session=db)
        count = manager.persist_state()
        return {"categories_persisted": count}
    finally:
        db.close()


# ===================================================================
# Phase 3 Block C: Backward Learning Tasks
# ===================================================================


def weekly_calibration_impl() -> dict:
    """
    Run isotonic PAV calibration across all categories.

    Calls: calibrator.recalibrate_all()
    Updates: Per-category calibration maps.
    """
    from services.scoring.learning.calibrator import Calibrator

    db = _get_db_session()
    try:
        calibrator = Calibrator(db_session=db)
        results = calibrator.recalibrate_all()
        return {
            "categories_calibrated": len(results),
            "global_pearson_r": results.get("global_r"),
        }
    finally:
        db.close()


def weekly_drift_detection_impl() -> dict:
    """
    Run drift detection: correlation drop, KS shift, acceptance trends.

    Calls: drift_detector.detect_all()
    Output: Drift alerts for categories needing attention.
    """
    from services.scoring.learning.drift_detector import DriftDetector

    db = _get_db_session()
    try:
        detector = DriftDetector(db_session=db)
        alerts = detector.detect_all()
        return {
            "categories_checked": alerts.get("checked", 0),
            "alerts_generated": alerts.get("alert_count", 0),
            "critical_alerts": alerts.get("critical", 0),
        }
    finally:
        db.close()


def weekly_scout_feedback_impl() -> dict:
    """
    Backward learning: correlate failures with data gaps.

    Calls: scout_feedback.compute_priority_adjustments()
    Output: ScrapingPriorityAdjustments for Scout scheduler.
    """
    from services.scoring.learning.scout_feedback import ScoutFeedback

    db = _get_db_session()
    try:
        feedback = ScoutFeedback(db_session=db)
        results = feedback.compute_priority_adjustments()
        return {
            "categories_analyzed": results.get("analyzed", 0),
            "priority_changes": results.get("changes", 0),
        }
    finally:
        db.close()


def weekly_analyst_feedback_impl() -> dict:
    """
    Backward learning: correlate component scores with outcomes.

    Calls: analyst_feedback.compute_weight_recommendations()
    Output: Weight rebalancing suggestions for ScoreFusion.
    """
    from services.scoring.learning.analyst_feedback import AnalystFeedback

    db = _get_db_session()
    try:
        feedback = AnalystFeedback(db_session=db)
        results = feedback.compute_weight_recommendations()
        return {
            "components_analyzed": results.get("components", 0),
            "weight_changes_recommended": results.get("changes", 0),
        }
    finally:
        db.close()


# ===================================================================
# Register all tasks with Celery
# ===================================================================

# Get the Celery app
app = _get_celery_app()


# -- Phase 3 Block A --
@app.task(name="ie.weekly_feature_compute", bind=True, max_retries=2, default_retry_delay=300, acks_late=True)
def weekly_feature_compute(self):
    return _task_wrapper("weekly_feature_compute", weekly_feature_compute_impl)


@app.task(name="ie.weekly_prior_update", bind=True, max_retries=2, default_retry_delay=300, acks_late=True)
def weekly_prior_update(self):
    return _task_wrapper("weekly_prior_update", weekly_prior_update_impl)


@app.task(name="ie.refresh_context_cache", bind=True, max_retries=2, default_retry_delay=60, acks_late=True)
def refresh_context_cache(self):
    return _task_wrapper("refresh_context_cache", refresh_context_cache_impl)


# -- Phase 3 Block B --
@app.task(name="ie.daily_bandit_update", bind=True, max_retries=3, default_retry_delay=120, acks_late=True)
def daily_bandit_update(self):
    return _task_wrapper("daily_bandit_update", daily_bandit_update_impl)


@app.task(name="ie.weekly_convergence_check", bind=True, max_retries=2, default_retry_delay=300, acks_late=True)
def weekly_convergence_check(self):
    return _task_wrapper("weekly_convergence_check", weekly_convergence_check_impl)


@app.task(name="ie.persist_bandit_state", bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def persist_bandit_state(self):
    return _task_wrapper("persist_bandit_state", persist_bandit_state_impl)


# -- Phase 3 Block C --
@app.task(name="ie.weekly_calibration", bind=True, max_retries=2, default_retry_delay=300, acks_late=True)
def weekly_calibration(self):
    return _task_wrapper("weekly_calibration", weekly_calibration_impl)


@app.task(name="ie.weekly_drift_detection", bind=True, max_retries=2, default_retry_delay=300, acks_late=True)
def weekly_drift_detection(self):
    return _task_wrapper("weekly_drift_detection", weekly_drift_detection_impl)


@app.task(name="ie.weekly_scout_feedback", bind=True, max_retries=2, default_retry_delay=300, acks_late=True)
def weekly_scout_feedback(self):
    return _task_wrapper("weekly_scout_feedback", weekly_scout_feedback_impl)


@app.task(name="ie.weekly_analyst_feedback", bind=True, max_retries=2, default_retry_delay=300, acks_late=True)
def weekly_analyst_feedback(self):
    return _task_wrapper("weekly_analyst_feedback", weekly_analyst_feedback_impl)


# ===================================================================
# Beat schedule entries to merge into celery_app.py
# ===================================================================

IE_BEAT_SCHEDULE = {
    # Phase 3 Block A: Tier 2 Batch Learning (Sunday)
    "ie-weekly-feature-compute": {
        "task": "ie.weekly_feature_compute",
        "schedule": {
            "minute": 0,
            "hour": 4,
            "day_of_week": 0,  # Sunday
        },
    },
    "ie-weekly-prior-update": {
        "task": "ie.weekly_prior_update",
        "schedule": {
            "minute": 0,
            "hour": 5,
            "day_of_week": 0,
        },
    },
    "ie-refresh-context-cache": {
        "task": "ie.refresh_context_cache",
        "schedule": {
            "minute": 30,
            "hour": 5,
            "day_of_week": 0,
        },
    },
    # Phase 3 Block B: Thompson Sampling (Daily / Sunday)
    "ie-daily-bandit-update": {
        "task": "ie.daily_bandit_update",
        "schedule": {
            "minute": 0,
            "hour": 6,
        },
    },
    "ie-weekly-convergence-check": {
        "task": "ie.weekly_convergence_check",
        "schedule": {
            "minute": 30,
            "hour": 6,
            "day_of_week": 0,
        },
    },
    "ie-persist-bandit-state": {
        "task": "ie.persist_bandit_state",
        "schedule": {
            "minute": 0,
            "hour": 7,
        },
    },
    # Phase 3 Block C: Backward Learning (Sunday)
    "ie-weekly-calibration": {
        "task": "ie.weekly_calibration",
        "schedule": {
            "minute": 30,
            "hour": 7,
            "day_of_week": 0,
        },
    },
    "ie-weekly-drift-detection": {
        "task": "ie.weekly_drift_detection",
        "schedule": {
            "minute": 0,
            "hour": 8,
            "day_of_week": 0,
        },
    },
    "ie-weekly-scout-feedback": {
        "task": "ie.weekly_scout_feedback",
        "schedule": {
            "minute": 30,
            "hour": 8,
            "day_of_week": 0,
        },
    },
    "ie-weekly-analyst-feedback": {
        "task": "ie.weekly_analyst_feedback",
        "schedule": {
            "minute": 0,
            "hour": 9,
            "day_of_week": 0,
        },
    },
}


# ===================================================================
# Merge helper — call this from celery_app.py
# ===================================================================


def register_ie_beat_schedule(app_instance) -> None:
    """
    Merge IE beat schedules into the existing Celery Beat configuration.

    Usage in celery_app.py:
        from workers.tasks.intelligence_tasks import register_ie_beat_schedule
        register_ie_beat_schedule(celery_app)
    """
    from celery.schedules import crontab

    existing = getattr(app_instance.conf, "beat_schedule", {}) or {}

    for name, config in IE_BEAT_SCHEDULE.items():
        sched = config["schedule"]
        existing[name] = {
            "task": config["task"],
            "schedule": crontab(
                minute=sched.get("minute", 0),
                hour=sched.get("hour", 0),
                day_of_week=sched.get("day_of_week", "*"),
            ),
        }

    app_instance.conf.beat_schedule = existing
    logger.info("[IE] Registered %d beat schedule entries", len(IE_BEAT_SCHEDULE))
