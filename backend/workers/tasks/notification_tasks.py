# backend/workers/tasks/notification_tasks.py
"""
Celery tasks for async notification dispatch.

Handles sending alerts via email, Slack, webhook without blocking API requests.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID

from workers.celery_app import celery_app
# Use run_async helper and async session context from session.py
from db.session import run_async, get_session_context
from sqlmodel import select

logger = logging.getLogger(__name__)


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
) -> Dict[str, Any]:
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
    # Use run_async helper from session.py
    return run_async(_dispatch_alert_async(alert_id))


async def _dispatch_alert_async(alert_id: str) -> Dict[str, Any]:
    """Async implementation of alert dispatch."""
    from models.alert import Alert, AlertConfiguration, AlertStatus, AlertChannel
    from models.user import User
    from services.notification import NotificationDispatcher
    from services.notification.webhook_service import WebhookService
    from datetime import datetime
    
    # Use existing get_session_context from session.py
    async with get_session_context() as session:
        # Load alert
        result = await session.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalars().first()
        
        if not alert:
            logger.error(f"Alert not found: {alert_id}")
            return {"error": "Alert not found"}
        
        if alert.status not in (AlertStatus.PENDING, AlertStatus.FAILED):
            logger.info(f"Alert {alert_id} already processed (status: {alert.status})")
            return {"skipped": True, "reason": f"Status is {alert.status.value}"}
        
        # Load user for default settings
        user_result = await session.execute(
            select(User).where(User.id == alert.user_id)
        )
        user = user_result.scalars().first()
        
        if not user:
            logger.error(f"User not found for alert: {alert_id}")
            return {"error": "User not found"}
        
        # Load configuration if exists
        config = None
        if alert.configuration_id:
            config_result = await session.execute(
                select(AlertConfiguration).where(
                    AlertConfiguration.id == alert.configuration_id
                )
            )
            config = config_result.scalars().first()
        
        # Determine channels and settings
        channels = _get_channels(alert, config)
        channel_settings = _get_channel_settings(alert, config, user)
        
        # Initialize services
        dispatcher = NotificationDispatcher()
        webhook_service = WebhookService()
        
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
                channel_name = channel.value if hasattr(channel, 'value') else str(channel)
                channels_failed.append(channel_name)
                errors[channel_name] = str(e)
                logger.exception(f"Error dispatching to {channel_name}: {e}")
        
        # Update alert status
        alert.channels_sent = channels_sent
        alert.channels_failed = channels_failed
        alert.sent_at = datetime.utcnow()
        
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
            }
        )
        
        return {
            "alert_id": str(alert_id),
            "channels_sent": channels_sent,
            "channels_failed": channels_failed,
            "errors": errors,
        }


def _get_channels(alert, config) -> List:
    """Determine which channels to send to."""
    from models.alert import AlertChannel
    
    if config and config.channels:
        # Convert string values back to enum if needed
        channels = []
        for ch in config.channels:
            if isinstance(ch, AlertChannel):
                channels.append(ch)
            elif isinstance(ch, str):
                try:
                    channels.append(AlertChannel(ch))
                except ValueError:
                    pass
        return channels if channels else [AlertChannel.IN_APP]
    
    # Default to in-app only
    return [AlertChannel.IN_APP]


def _get_channel_settings(alert, config, user) -> Dict[str, Any]:
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
def dispatch_bulk_alerts_task(alert_ids: List[str]) -> Dict[str, Any]:
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


