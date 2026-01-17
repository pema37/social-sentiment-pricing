#!/bin/bash
# backend/start.sh

# FIRST THING - prove the script runs at all
echo "SCRIPT STARTED AT $(date)"
env | grep -E "^(PORT|DATABASE|REDIS|ENVIRONMENT)" | head -10

set -e

echo "=== SSP Backend Starting ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "PORT: ${PORT:-NOT SET}"
echo "ENVIRONMENT: ${ENVIRONMENT:-NOT SET}"
echo "DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'yes' || echo 'NO')"
echo "REDIS_URL set: $([ -n "$REDIS_URL" ] && echo 'yes' || echo 'NO')"
echo "==============================="

# Clear stale Celery beat schedule
echo "Clearing stale celerybeat-schedule files..."
rm -f celerybeat-schedule /app/celerybeat-schedule 2>/dev/null || true

# Only start Celery if Redis is available
if [ -n "$REDIS_URL" ]; then
    echo "Starting Celery worker..."
    celery -A workers.celery_app worker \
        --loglevel=info \
        --concurrency=2 \
        &
    CELERY_WORKER_PID=$!
    echo "Celery worker PID: $CELERY_WORKER_PID"

    echo "Starting Celery beat scheduler..."
    celery -A workers.celery_app beat \
        --loglevel=info \
        &
    CELERY_BEAT_PID=$!
    echo "Celery beat PID: $CELERY_BEAT_PID"
    
    # Give Celery a moment to initialize
    sleep 2
else
    echo "WARNING: REDIS_URL not set, skipping Celery workers..."
fi

# Validate PORT is set
if [ -z "$PORT" ]; then
    echo "ERROR: PORT environment variable is not set!"
    echo "Defaulting to 8080 for local testing..."
    PORT=8080
fi

# Start Uvicorn API server
echo "Starting Uvicorn API server on port ${PORT}..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --workers 1 \
    --log-level info


    