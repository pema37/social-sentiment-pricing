#!/bin/bash
# backend/start.sh
# Startup script for SSP Backend Services

set -e

echo "Starting SSP Backend Services..."

# Clear stale Celery beat schedule to ensure fresh schedule is loaded
# This prevents issues where old task names persist after code updates
echo "Clearing stale celerybeat-schedule files..."
rm -f celerybeat-schedule
rm -f /app/celerybeat-schedule
rm -f /home/claude/celerybeat-schedule

# Start Celery worker in the background
echo "Starting Celery worker..."
celery -A workers.celery_app worker \
    --loglevel=info \
    --concurrency=4 \
    --pool=prefork \
    &
CELERY_WORKER_PID=$!
echo "Celery worker PID: $CELERY_WORKER_PID"

# Start Celery beat scheduler in the background
echo "Starting Celery beat scheduler..."
celery -A workers.celery_app beat \
    --loglevel=info \
    &
CELERY_BEAT_PID=$!
echo "Celery beat PID: $CELERY_BEAT_PID"

# Start Uvicorn API server
echo "Starting Uvicorn API server on port ${PORT:-8080}..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8080} \
    --workers 1 \
    --log-level info

    