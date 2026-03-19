# backend/core/alerting.py
"""
Alerting service for critical notifications.
Supports Slack webhooks and email (via SendGrid).
"""

from enum import StrEnum

import httpx

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


SEVERITY_COLORS = {
    AlertSeverity.INFO: "#36a64f",  # Green
    AlertSeverity.WARNING: "#ff9800",  # Orange
    AlertSeverity.ERROR: "#f44336",  # Red
    AlertSeverity.CRITICAL: "#9c27b0",  # Purple
}

SEVERITY_EMOJI = {
    AlertSeverity.INFO: "ℹ️",
    AlertSeverity.WARNING: "⚠️",
    AlertSeverity.ERROR: "🚨",
    AlertSeverity.CRITICAL: "🔥",
}


async def send_slack_alert(
    title: str,
    message: str,
    severity: AlertSeverity = AlertSeverity.INFO,
    fields: dict[str, str] | None = None,
    link: str | None = None,
) -> bool:
    """
    Send an alert to Slack via webhook.

    Args:
        title: Alert title
        message: Alert message body
        severity: Alert severity level
        fields: Optional key-value pairs to display
        link: Optional link to include

    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.SLACK_WEBHOOK_URL:
        logger.debug("Slack webhook not configured, skipping alert")
        return False

    emoji = SEVERITY_EMOJI.get(severity, "")
    color = SEVERITY_COLORS.get(severity, "#808080")

    # Build Slack attachment
    attachment = {
        "color": color,
        "title": f"{emoji} {title}",
        "text": message,
        "footer": f"{settings.APP_NAME} | {settings.ENVIRONMENT}",
        "ts": int(__import__("time").time()),
    }

    # Add fields if provided
    if fields:
        attachment["fields"] = [{"title": k, "value": v, "short": len(v) < 30} for k, v in fields.items()]

    # Add link button if provided
    if link:
        attachment["actions"] = [
            {
                "type": "button",
                "text": "View Details",
                "url": link,
            }
        ]

    payload = {"attachments": [attachment]}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.SLACK_WEBHOOK_URL,
                json=payload,
            )

            if response.status_code == 200:
                logger.info("Slack alert sent", title=title, severity=severity.value)
                return True
            else:
                logger.error(
                    "Slack alert failed",
                    status_code=response.status_code,
                    response=response.text,
                )
                return False

    except Exception as e:
        logger.error("Failed to send Slack alert", error=str(e))
        return False


async def send_email_alert(
    subject: str,
    message: str,
    severity: AlertSeverity = AlertSeverity.INFO,
    to_email: str | None = None,
) -> bool:
    """
    Send an alert via email using SendGrid.

    Args:
        subject: Email subject
        message: Email body (plain text)
        severity: Alert severity level
        to_email: Recipient email (defaults to ALERT_EMAIL)

    Returns:
        True if sent successfully, False otherwise
    """
    if not settings.SENDGRID_API_KEY:
        logger.debug("SendGrid not configured, skipping email alert")
        return False

    recipient = to_email or settings.ALERT_EMAIL
    if not recipient:
        logger.debug("No alert email configured, skipping")
        return False

    if not settings.SENDGRID_FROM_EMAIL:
        logger.debug("No from email configured, skipping")
        return False

    emoji = SEVERITY_EMOJI.get(severity, "")

    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": settings.SENDGRID_FROM_EMAIL},
        "subject": f"{emoji} [{severity.value.upper()}] {subject}",
        "content": [
            {
                "type": "text/plain",
                "value": f"{message}\n\n---\nEnvironment: {settings.ENVIRONMENT}\nApp: {settings.APP_NAME}",
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code in (200, 202):
                logger.info("Email alert sent", subject=subject, to=recipient)
                return True
            else:
                logger.error(
                    "Email alert failed",
                    status_code=response.status_code,
                    response=response.text,
                )
                return False

    except Exception as e:
        logger.error("Failed to send email alert", error=str(e))
        return False


async def send_alert(
    title: str,
    message: str,
    severity: AlertSeverity = AlertSeverity.INFO,
    fields: dict[str, str] | None = None,
    channels: list | None = None,
) -> dict[str, bool]:
    """
    Send alert to multiple channels.

    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        fields: Optional additional fields
        channels: List of channels ('slack', 'email'). Defaults to all configured.

    Returns:
        Dict of channel -> success status
    """
    if channels is None:
        channels = ["slack", "email"]

    results = {}

    if "slack" in channels:
        results["slack"] = await send_slack_alert(
            title=title,
            message=message,
            severity=severity,
            fields=fields,
        )

    if "email" in channels:
        results["email"] = await send_email_alert(
            subject=title,
            message=message,
            severity=severity,
        )

    return results


# Convenience functions for common alerts
async def alert_error(title: str, message: str, **kwargs):
    """Send an error alert."""
    return await send_alert(title, message, AlertSeverity.ERROR, **kwargs)


async def alert_critical(title: str, message: str, **kwargs):
    """Send a critical alert."""
    return await send_alert(title, message, AlertSeverity.CRITICAL, **kwargs)


async def alert_warning(title: str, message: str, **kwargs):
    """Send a warning alert."""
    return await send_alert(title, message, AlertSeverity.WARNING, **kwargs)


async def alert_info(title: str, message: str, **kwargs):
    """Send an info alert."""
    return await send_alert(title, message, AlertSeverity.INFO, **kwargs)
