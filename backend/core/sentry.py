# backend/core/sentry.py
"""
Sentry error tracking and performance monitoring.
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


def configure_sentry() -> None:
    """Initialize Sentry SDK if DSN is configured."""
    
    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN not configured, skipping initialization")
        return
    
    try:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            release=f"{settings.APP_NAME}@{settings.APP_VERSION}",
            
            # Performance monitoring
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
            
            # Integrations
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                RedisIntegration(),
                CeleryIntegration(),
                LoggingIntegration(
                    level=None,  # Capture all levels
                    event_level=40,  # Only send ERROR and above to Sentry
                ),
            ],
            
            # Data scrubbing
            send_default_pii=False,
            
            # Filter out health checks and static files
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
        )
    except Exception as e:
        logger.warning(f"Sentry initialization failed: {e}")
        return
    
    logger.info(
        "Sentry initialized",
        environment=settings.ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )


def _before_send(event, hint):
    """Filter events before sending to Sentry."""
    # Skip certain exceptions
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]
        
        # Skip 404s and validation errors
        if exc_type.__name__ in ("HTTPException",):
            if hasattr(exc_value, "status_code") and exc_value.status_code in (404, 422):
                return None
    
    return event


def _before_send_transaction(event, hint):
    """Filter transactions before sending to Sentry."""
    # Skip health check endpoints
    transaction_name = event.get("transaction", "")
    if any(path in transaction_name for path in ["/health", "/ready", "/live"]):
        return None
    
    return event


def capture_exception(error: Exception, **context) -> None:
    """Capture an exception with additional context."""
    with sentry_sdk.push_scope() as scope:
        for key, value in context.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", **context) -> None:
    """Capture a message with additional context."""
    with sentry_sdk.push_scope() as scope:
        for key, value in context.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_message(message, level=level)


def set_user(user_id: str, email: str = None, username: str = None) -> None:
    """Set user context for Sentry."""
    sentry_sdk.set_user({
        "id": user_id,
        "email": email,
        "username": username,
    })

    