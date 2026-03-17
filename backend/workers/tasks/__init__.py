# backend/workers/tasks/__init__.py
"""
Celery task modules.

All tasks are auto-discovered by Celery from these modules.
"""

from workers.tasks.notification_tasks import (
    dispatch_alert_task,
    dispatch_bulk_alerts_task,
)

# Note: Other tasks (ingestion, pricing, sync_verification) are auto-discovered
# by Celery via the celery_app.autodiscover_tasks() call in celery_app.py

__all__ = [
    "dispatch_alert_task",
    "dispatch_bulk_alerts_task",
]
