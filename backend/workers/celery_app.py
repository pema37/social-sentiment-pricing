"""
Celery Application Configuration for AP Background Workers.

This module configures the Celery app with:
- Redis as broker and backend
- Task includes for all worker modules
- Beat schedule for periodic tasks

PATCHED (2025-01-07): Added sync_verification_tasks for periodic price sync checks
PATCHED (2026-02-17): Added outcome_measurement_tasks for multi-window feedback loop
PATCHED (2026-02-18): Phase 5 — Added intelligence_tasks for IE learning/experimentation/calibration
PATCHED (2026-03-13): Added check-integration-health beat entry (every 30 min).
    Polls ACTIVE + ERROR integrations and writes status back to DB so the
    frontend diagnostic panel reflects real connection state automatically.
"""

import os

from celery import Celery
from celery.schedules import crontab

# Use Redis URL from environment (Railway provides this)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "ssp_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "workers.tasks.ingestion_tasks",
        "workers.tasks.pricing_tasks",
        "workers.tasks.sync_verification_tasks",
        "workers.tasks.sync_tasks",
        "workers.tasks.outcome_measurement_tasks",
        "workers.tasks.benchmark_refresh_tasks",
        "workers.tasks.intelligence_tasks",
        "workers.tasks.audit_tasks",
        "workers.tasks.notification_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", "300")),  # default 5 min
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "270")),  # default 4.5 min
    worker_prefetch_multiplier=1,  # Fetch one task at a time (better for long tasks)
    task_acks_late=True,  # Acknowledge after task completion (safer)
)

# Scheduled tasks (beat schedule)
# IMPORTANT: Task names must match the `name=` parameter in @celery_app.task decorator
celery_app.conf.beat_schedule = {
    # === Ingestion tasks ===
    # Fetch social mentions for all products every 30 minutes
    "fetch-social-mentions": {
        "task": "ingestion.fetch_all_mentions",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "celery"},
    },
    # Process unprocessed mentions every 5 minutes
    "process-mentions": {
        "task": "ingestion.process_pending_mentions",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "celery"},
    },
    # === Pricing tasks ===
    # Generate recommendations for all products every hour (at minute 0)
    "generate-recommendations": {
        "task": "workers.tasks.pricing_tasks.generate_all_recommendations",
        "schedule": crontab(minute=0),
        "options": {"queue": "celery"},
    },
    # Check competitor prices every 30 minutes (at minute 15 and 45)
    "check-competitor-prices": {
        "task": "workers.tasks.pricing_tasks.check_competitor_prices",
        "schedule": crontab(minute="15,45"),
        "options": {"queue": "celery"},
    },
    # Expire old recommendations every 6 hours (at minute 0)
    "expire-recommendations": {
        "task": "workers.tasks.pricing_tasks.expire_recommendations",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"queue": "celery"},
    },
    # === Sync Verification tasks ===
    # Verify price syncs every 6 hours (at minute 30)
    "verify-price-syncs": {
        "task": "workers.tasks.sync_verification_tasks.verify_price_syncs",
        "schedule": crontab(minute=30, hour="*/6"),
        "options": {"queue": "celery"},
    },
    # ADDED (2026-03-13): Poll integration health every 30 minutes.
    # Calls health_check() on all ACTIVE + ERROR integrations and writes
    # the result back to the integrations table. This ensures a revoked
    # Shopify token surfaces as status=ERROR automatically — without
    # waiting for a merchant to manually trigger a health check — so the
    # frontend reconnect CTA appears promptly and init_oauth can proceed.
    "check-integration-health": {
        "task": "workers.tasks.sync_verification_tasks.check_all_integration_health",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "celery"},
    },
    # === Outcome Measurement tasks (Phase 1 feedback loop) ===
    # Measure 7-day impact daily at 2 AM
    "measure-outcomes-7d": {
        "task": "workers.tasks.outcome_measurement_tasks.measure_outcomes_7d",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "celery"},
    },
    # Measure 14-day impact daily at 3 AM
    "measure-outcomes-14d": {
        "task": "workers.tasks.outcome_measurement_tasks.measure_outcomes_14d",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "celery"},
    },
    # Measure 30-day impact daily at 4 AM
    "measure-outcomes-30d": {
        "task": "workers.tasks.outcome_measurement_tasks.measure_outcomes_30d",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "celery"},
    },
    # === Benchmark Materialized View Refresh ===
    # Refresh category benchmark views daily at 4:30 AM
    "refresh-benchmark-views": {
        "task": "workers.tasks.benchmark_refresh_tasks.refresh_benchmark_views",
        "schedule": crontab(hour=4, minute=30),
        "options": {"queue": "celery"},
    },
    # === Retrospective Audit tasks ===
    # Generate 90-day pricing audits for all users every Sunday at 5 AM
    "generate-weekly-audits": {
        "task": "workers.tasks.audit_tasks.generate_weekly_audits",
        "schedule": crontab(hour=5, minute=0, day_of_week="sunday"),
        "options": {"queue": "celery"},
    },
}

# ═══════════════════════════════════════════════════════════════════════
# Phase 5: Intelligence Environment — register IE beat schedule
# Merges 10 tasks (learning, experimentation, calibration, drift detection)
# into beat_schedule non-destructively alongside Phase 1 tasks above.
#
# Schedule added:
#   4:00 AM Sun  — weekly_feature_compute      (Phase 3A)
#   5:00 AM Sun  — weekly_prior_update          (Phase 3A)
#   5:30 AM Sun  — refresh_context_cache        (Phase 3A)
#   6:00 AM Daily — daily_bandit_update          (Phase 3B)
#   6:30 AM Sun  — weekly_convergence_check     (Phase 3B)
#   7:00 AM Daily — persist_bandit_state         (Phase 3B)
#   7:30 AM Sun  — weekly_calibration           (Phase 3C)
#   8:00 AM Sun  — weekly_drift_detection       (Phase 3C)
#   8:30 AM Sun  — weekly_scout_feedback        (Phase 3C)
#   9:00 AM Sun  — weekly_analyst_feedback      (Phase 3C)
# ═══════════════════════════════════════════════════════════════════════
from workers.tasks.intelligence_tasks import register_ie_beat_schedule  # noqa: E402

register_ie_beat_schedule(celery_app)
