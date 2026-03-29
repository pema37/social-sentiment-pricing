"""
FILE: backend/workers/celery_app.py
FULL REPLACE

Patch history:
  PATCHED (2025-01-07): Added sync_verification_tasks
  PATCHED (2026-02-17): Added outcome_measurement_tasks
  PATCHED (2026-02-18): Phase 5 IE tasks
  PATCHED (2026-03-13): check-integration-health beat entry
  PATCHED (2026-03-28a): Dedicated sync/sentiment queues + TASK_ROUTES. Concurrency 4.
  PATCHED (2026-03-28b): visibility_timeout=43200, broker_transport_options,
                         max_tasks_per_child, broker_pool_limit, without-gossip flags.
  PATCHED (2026-03-29): [NEW] setup_event_loop via worker_process_init — persistent
                         asyncio event loop per prefork worker. Eliminates GC churn
                         from asyncio.run() and enables httpx connection pool reuse.
                        [FIXED] result_expires=86400 (was 3600). Chord callbacks
                         silently never fire when chunk results expire before the
                         callback reads them. 24h is safe for this workload.
                        [ADDED] sync_integration_products_complete to TASK_ROUTES.

DEPLOY COMMANDS (Railway):

  # Worker (all queues)
  celery -A workers.celery_app worker --pool=prefork --concurrency=4 \\
    --max-tasks-per-child=1000 \\
    --without-gossip --without-mingle \\
    --prefetch-multiplier=1 \\
    --loglevel=info \\
    -Q celery,sync,sentiment

  # Beat (replicas: 1 — never run more than one)
  celery -A workers.celery_app beat --loglevel=info --pidfile=/tmp/celerybeat.pid
"""

import asyncio
import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init
from kombu import Exchange, Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


# ---------------------------------------------------------------------------
# Persistent event loop per prefork worker
# ---------------------------------------------------------------------------
# asyncio.run() creates and destroys an event loop on every Celery task call.
# This breaks httpx/aiohttp connection pool reuse (new pool per task = no
# keepalive) and adds GC overhead. The fix: each worker PROCESS gets one
# persistent loop created at startup via worker_process_init. run_async()
# in ingestion_tasks.py calls asyncio.get_event_loop().run_until_complete()
# which picks up this loop automatically. No changes needed in task code.
# Thread-safety: each prefork process is memory-isolated — no shared state.
@worker_process_init.connect
def setup_event_loop(**kwargs):
    """Create one persistent asyncio event loop per prefork worker process."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)


# ---------------------------------------------------------------------------
# Queue definitions
# ---------------------------------------------------------------------------
TASK_QUEUES = (
    Queue("celery",    Exchange("celery",    type="direct"), routing_key="celery"),
    Queue("sync",      Exchange("sync",      type="direct"), routing_key="sync",
          queue_arguments={"x-max-priority": 10}),
    Queue("sentiment", Exchange("sentiment", type="direct"), routing_key="sentiment"),
)

TASK_ROUTES = {
    # Sync lane — all sync tasks routed to the dedicated sync queue
    "workers.tasks.sync_tasks.sync_integration_products":          {"queue": "sync"},
    "workers.tasks.sync_tasks.sync_integration_products_chunk":    {"queue": "sync"},
    "workers.tasks.sync_tasks.sync_integration_products_complete": {"queue": "sync"},
    "workers.tasks.sync_tasks.sync_integration_products_error":    {"queue": "sync"},
    "workers.tasks.sync_tasks.sync_all_integrations":              {"queue": "sync"},
    # Sentiment / ingestion lane
    "ingestion.fetch_all_mentions":                                {"queue": "sentiment"},
    "ingestion.fetch_for_product":                                 {"queue": "sentiment"},
    "ingestion.process_pending_mentions":                          {"queue": "sentiment"},
}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
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

celery_app.conf.update(
    # --- Serialisation ---
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,

    # --- Timeouts ---
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", "300")),
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "270")),

    # --- Worker reliability ---
    worker_max_tasks_per_child=1000,       # Recycle children to prevent memory leaks
    worker_concurrency=4,
    worker_prefetch_multiplier=1,           # Fair scheduling with acks_late
    task_acks_late=True,                   # Ack only after completion — safe requeue on crash
    task_reject_on_worker_lost=True,       # Requeue if worker is OOM-killed

    # --- Monitoring (Flower) without gossip overhead ---
    worker_send_task_events=True,
    task_send_sent_event=True,

    # --- Redis broker tuning ---
    # visibility_timeout MUST exceed longest possible task runtime.
    # Default 3600s: any task running > 1h with acks_late=True gets silently
    # redelivered → DUPLICATE EXECUTION. Set to 12h (43200s).
    # Rule: visibility_timeout > time_limit > soft_time_limit
    broker_transport_options={
        "visibility_timeout": int(os.getenv("CELERY_VISIBILITY_TIMEOUT", "43200")),
        "socket_keepalive": True,
        "health_check_interval": 60,
        "retry_on_timeout": True,
    },

    # Railway has strict Redis connection limits. None = NullPool on broker
    # (open+close per op). Trades tiny latency for predictable connection count.
    broker_pool_limit=None,

    # --- Result backend ---
    # CRITICAL FOR CHORDS: chunk results must exist when the callback reads them.
    # With retries + 4 workers, a chord can take > 1h. result_expires=3600 means
    # results expire before the callback fires → callback never fires → sync_status
    # stuck at "syncing" forever. 86400 = 24h, safe for this workload.
    # NEVER set result_expires=0 or None with chords.
    result_expires=86400,

    # --- Queues ---
    task_queues=TASK_QUEUES,
    task_routes=TASK_ROUTES,
    task_default_queue="celery",
)

# ---------------------------------------------------------------------------
# Beat schedule
# ---------------------------------------------------------------------------
celery_app.conf.beat_schedule = {
    # === Ingestion (sentiment lane) ===
    "fetch-social-mentions": {
        "task": "ingestion.fetch_all_mentions",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "sentiment"},
    },
    "process-mentions": {
        "task": "ingestion.process_pending_mentions",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "sentiment"},
    },
    # === Pricing ===
    "generate-recommendations": {
        "task": "workers.tasks.pricing_tasks.generate_all_recommendations",
        "schedule": crontab(minute=0),
        "options": {"queue": "celery"},
    },
    "check-competitor-prices": {
        "task": "workers.tasks.pricing_tasks.check_competitor_prices",
        "schedule": crontab(minute="15,45"),
        "options": {"queue": "celery"},
    },
    "expire-recommendations": {
        "task": "workers.tasks.pricing_tasks.expire_recommendations",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"queue": "celery"},
    },
    # === Sync Verification ===
    "verify-price-syncs": {
        "task": "workers.tasks.sync_verification_tasks.verify_price_syncs",
        "schedule": crontab(minute=30, hour="*/6"),
        "options": {"queue": "celery"},
    },
    "recover-stuck-syncs": {
        "task": "workers.tasks.sync_verification_tasks.recover_stuck_syncs",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "celery"},
    },
    "check-integration-health": {
        "task": "workers.tasks.sync_verification_tasks.check_all_integration_health",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "celery"},
    },
    # === Outcome Measurement ===
    "measure-outcomes-7d": {
        "task": "workers.tasks.outcome_measurement_tasks.measure_outcomes_7d",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "celery"},
    },
    "measure-outcomes-14d": {
        "task": "workers.tasks.outcome_measurement_tasks.measure_outcomes_14d",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "celery"},
    },
    "measure-outcomes-30d": {
        "task": "workers.tasks.outcome_measurement_tasks.measure_outcomes_30d",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "celery"},
    },
    # === Benchmark Refresh ===
    "refresh-benchmark-views": {
        "task": "workers.tasks.benchmark_refresh_tasks.refresh_benchmark_views",
        "schedule": crontab(hour=4, minute=30),
        "options": {"queue": "celery"},
    },
    # === Retrospective Audit ===
    "generate-weekly-audits": {
        "task": "workers.tasks.audit_tasks.generate_weekly_audits",
        "schedule": crontab(hour=5, minute=0, day_of_week="sunday"),
        "options": {"queue": "celery"},
    },
}

# Phase 5 IE schedule — preserved verbatim
from workers.tasks.intelligence_tasks import register_ie_beat_schedule  # noqa: E402

register_ie_beat_schedule(celery_app)





