# backend/workers/celery_app.py
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
)

# Scheduled tasks (beat schedule)
celery_app.conf.beat_schedule = {
    # Fetch social mentions every 30 minutes
    "fetch-social-mentions": {
        "task": "workers.tasks.ingestion_tasks.fetch_social_mentions",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
    },
    # Process unprocessed mentions every 5 minutes
    "process-mentions": {
        "task": "workers.tasks.ingestion_tasks.process_pending_mentions",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },

    # === Pricing tasks ===

    # Generate recommendations every hour
    "generate-recommendations": {
        "task": "workers.tasks.pricing_tasks.generate_all_recommendations",
        "schedule": crontab(minute=0),  # Every hour at :00
    },
    # Check competitor prices every 15 minutes
    "check-competitor-prices": {
        "task": "workers.tasks.pricing_tasks.check_competitor_prices",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    # Expire old recommendations every 6 hours
    "expire-recommendations": {
        "task": "workers.tasks.pricing_tasks.expire_recommendations",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
    },
}

