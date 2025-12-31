# backend/workers/celery_app.py
"""
Celery Application Configuration for SSP Background Workers.

This module configures the Celery app with:
- Redis as broker and backend
- Task includes for all worker modules
- Beat schedule for periodic tasks
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
        "task": "ingestion.fetch_all_mentions",  # ✅ Matches registered task name
        "schedule": crontab(minute="*/30"),
        "options": {"queue": "default"},
    },
    
    # Process unprocessed mentions every 5 minutes
    "process-mentions": {
        "task": "ingestion.process_pending_mentions",  # ✅ Matches registered task name
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "default"},
    },

    # === Pricing tasks ===

    # Generate recommendations for all products every hour (at minute 0)
    "generate-recommendations": {
        "task": "workers.tasks.pricing_tasks.generate_all_recommendations",
        "schedule": crontab(minute=0),
        "options": {"queue": "default"},
    },
    
    # Check competitor prices every 30 minutes (at minute 15 and 45)
    "check-competitor-prices": {
        "task": "workers.tasks.pricing_tasks.check_competitor_prices",
        "schedule": crontab(minute="15,45"),
        "options": {"queue": "default"},
    },
    
    # Expire old recommendations every 6 hours (at minute 0)
    "expire-recommendations": {
        "task": "workers.tasks.pricing_tasks.expire_recommendations",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"queue": "default"},
    },
}

# Optional: Configure task routes for different queues (future scaling)
# celery_app.conf.task_routes = {
#     "ingestion.*": {"queue": "ingestion"},
#     "workers.tasks.pricing_tasks.*": {"queue": "pricing"},
# }

