#!/bin/bash
set -e

echo "Starting SSP Backend Services..."

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A workers.celery_app worker --loglevel=info &
CELERY_WORKER_PID=$!

# Start Celery beat (scheduler) in background
echo "Starting Celery beat scheduler..."
celery -A workers.celery_app beat --loglevel=info &
CELERY_BEAT_PID=$!

# Give Celery a moment to start
sleep 2

echo "Celery worker PID: $CELERY_WORKER_PID"
echo "Celery beat PID: $CELERY_BEAT_PID"

# Start the API server (foreground)
echo "Starting Uvicorn API server on port ${PORT:-8000}..."
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}

