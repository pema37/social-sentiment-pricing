"""
Celery Application Configuration for AP Background Workers.

This module configures the Celery app with:
- Redis as broker and backend
- Task includes for all worker modules
- Beat schedule for periodic tasks

PATCHED (2025-01-07): Added sync_verification_tasks for periodic price sync checks
PATCHED (2026-02-17): Added outcome_measurement_tasks for multi-window feedback loop
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
        "workers.tasks.outcome_measurement_tasks",
        "workers.tasks.benchmark_refresh_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    task_soft_time_limit=270,  # Soft limit 30 seconds before hard limit
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

    # === Outcome Measurement tasks (feedback loop) ===

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
}

