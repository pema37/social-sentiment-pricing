# backend/workers/tasks/notification_tasks.py
"""
Celery tasks for async notification dispatch.

Handles sending alerts via email, Slack, webhook without blocking API requests.
"""

import asyncio
import contextlib
import logging
import re
from datetime import UTC
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import select

from core.config import settings
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_task_session_maker():
    """Create a fresh async session maker with NullPool for Celery tasks."""
    db_url = settings.DATABASE_URL

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "sslmode=" in db_url:
        db_url = re.sub(r"[\?&]sslmode=[^&]*", "", db_url)
        db_url = db_url.replace("?&", "?").replace("&&", "&").rstrip("?&")

    use_ssl = "neon.tech" in db_url or "railway" in db_url

    engine = create_async_engine(
        db_url,
        echo=False,
        poolclass=NullPool,
        connect_args={"ssl": True} if use_ssl else {},
    )

    return sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _run_async(coro):
    """Run async code in sync Celery task with a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@contextlib.asynccontextmanager
async def _get_task_session():
    """Async context manager for a NullPool session in Celery tasks."""
    session_maker = _get_task_session_maker()
    async with session_maker() as session:
        yield session


@celery_app.task(
    bind=True,
    name="notifications.dispatch_alert",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def dispatch_alert_task(
    self,
    alert_id: str,
) -> dict[str, Any]:
    """
    Dispatch an alert to all configured channels.

    This task:
    1. Loads the alert from database
    2. Gets channel settings from alert configuration (or user defaults)
    3. Sends to each channel (email, slack, webhook, in_app)
    4. Updates alert with delivery status

    Args:
        alert_id: UUID of the alert to dispatch

    Returns:
        Dict with channels_sent, channels_failed, errors
    """
    return _run_async(_dispatch_alert_async(alert_id))


async def _dispatch_alert_async(alert_id: str) -> dict[str, Any]:
    """Async implementation of alert dispatch."""
    from datetime import datetime

    from models.alert import Alert, AlertChannel, AlertConfiguration, AlertStatus
    from models.user import User
    from services.notification import NotificationDispatcher

    async with _get_task_session() as session:
        # Load alert
        result = await session.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalars().first()

        if not alert:
            logger.error(f"Alert not found: {alert_id}")
            return {"error": "Alert not found"}

        if alert.status not in (AlertStatus.PENDING, AlertStatus.FAILED):
            logger.info(f"Alert {alert_id} already processed (status: {alert.status})")
            return {"skipped": True, "reason": f"Status is {alert.status.value}"}

        # Load user for default settings
        user_result = await session.execute(select(User).where(User.id == alert.user_id))
        user = user_result.scalars().first()

        if not user:
            logger.error(f"User not found for alert: {alert_id}")
            return {"error": "User not found"}

        # Load configuration if exists
        config = None
        if alert.configuration_id:
            config_result = await session.execute(
                select(AlertConfiguration).where(AlertConfiguration.id == alert.configuration_id)
            )
            config = config_result.scalars().first()

        # Determine channels and settings
        channels = _get_channels(alert, config)
        channel_settings = _get_channel_settings(alert, config, user)

        # Initialize services
        dispatcher = NotificationDispatcher()
        webhook_service = dispatcher.webhook_service

        channels_sent = []
        channels_failed = []
        errors = {}

        # Dispatch to each channel
        for channel in channels:
            try:
                if channel == AlertChannel.EMAIL:
                    email = channel_settings.get("email") or user.email
                    if email:
                        from services.notification.email_service import EmailService

                        email_service = EmailService()
                        result = await email_service.send_alert_email(
                            to_email=email,
                            subject=f"[SSP Alert] {alert.title}",
                            alert_title=alert.title,
                            alert_message=alert.message,
                            severity=alert.severity.value,
                            alert_data=alert.data,
                        )
                        if result.success:
                            channels_sent.append("email")
                        else:
                            channels_failed.append("email")
                            errors["email"] = result.error or "Unknown error"
                    else:
                        channels_failed.append("email")
                        errors["email"] = "No email address configured"

                elif channel == AlertChannel.SLACK:
                    slack_url = channel_settings.get("slack_webhook_url")
                    if slack_url:
                        from services.notification.slack_service import SlackService

                        slack_service = SlackService()
                        result = await slack_service.send_alert(
                            webhook_url=slack_url,
                            alert_title=alert.title,
                            alert_message=alert.message,
                            severity=alert.severity.value,
                            alert_data=alert.data,
                        )
                        if result.success:
                            channels_sent.append("slack")
                        else:
                            channels_failed.append("slack")
                            errors["slack"] = result.error or "Unknown error"
                    else:
                        channels_failed.append("slack")
                        errors["slack"] = "No Slack webhook URL configured"

                elif channel == AlertChannel.WEBHOOK:
                    webhook_url = channel_settings.get("webhook_url")
                    webhook_secret = channel_settings.get("webhook_secret")
                    if webhook_url:
                        result = await webhook_service.send_alert(
                            webhook_url=webhook_url,
                            webhook_secret=webhook_secret,
                            alert_id=str(alert.id),
                            alert_title=alert.title,
                            alert_message=alert.message,
                            alert_type=alert.alert_type.value,
                            severity=alert.severity.value,
                            alert_data=alert.data,
                        )
                        if result.success:
                            channels_sent.append("webhook")
                        else:
                            channels_failed.append("webhook")
                            errors["webhook"] = result.error or "Unknown error"
                    else:
                        channels_failed.append("webhook")
                        errors["webhook"] = "No webhook URL configured"

                elif channel == AlertChannel.IN_APP:
                    # In-app is just the database record - always succeeds
                    channels_sent.append("in_app")

            except Exception as e:
                channel_name = channel.value if hasattr(channel, "value") else str(channel)
                channels_failed.append(channel_name)
                errors[channel_name] = str(e)
                logger.exception(f"Error dispatching to {channel_name}: {e}")

        # Update alert status
        alert.channels_sent = channels_sent
        alert.channels_failed = channels_failed
        alert.sent_at = datetime.now(UTC)

        if channels_sent:
            alert.status = AlertStatus.SENT
        else:
            alert.status = AlertStatus.FAILED

        session.add(alert)
        await session.commit()

        logger.info(
            f"Alert {alert_id} dispatched",
            extra={
                "channels_sent": channels_sent,
                "channels_failed": channels_failed,
            },
        )

        return {
            "alert_id": str(alert_id),
            "channels_sent": channels_sent,
            "channels_failed": channels_failed,
            "errors": errors,
        }


def _get_channels(alert, config) -> list:
    """Determine which channels to send to."""
    from models.alert import AlertChannel

    if config and config.channels:
        # Convert string values back to enum if needed
        channels = []
        for ch in config.channels:
            if isinstance(ch, AlertChannel):
                channels.append(ch)
            elif isinstance(ch, str):
                with contextlib.suppress(ValueError):
                    channels.append(AlertChannel(ch))
        return channels if channels else [AlertChannel.IN_APP]

    # Default to in-app only
    return [AlertChannel.IN_APP]


def _get_channel_settings(alert, config, user) -> dict[str, Any]:
    """Get channel-specific settings."""
    settings = {}

    # From configuration
    if config and config.channel_settings:
        settings.update(config.channel_settings)

    # User email as fallback
    if user and user.email:
        settings.setdefault("email", user.email)

    return settings


@celery_app.task(
    name="notifications.dispatch_bulk",
    max_retries=2,
)
def dispatch_bulk_alerts_task(alert_ids: list[str]) -> dict[str, Any]:
    """
    Dispatch multiple alerts.

    Args:
        alert_ids: List of alert UUIDs to dispatch

    Returns:
        Summary of dispatch results
    """
    results = {
        "total": len(alert_ids),
        "dispatched": 0,
        "failed": 0,
        "errors": [],
    }

    for alert_id in alert_ids:
        try:
            dispatch_alert_task.delay(alert_id)
            results["dispatched"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"alert_id": alert_id, "error": str(e)})

    return results
