# backend/services/notification/slack_service.py
"""
Slack notification service using webhooks.

Simple webhook integration - user provides their webhook URL.
No Slack app installation required.
"""

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from core.config import settings
from core.url_validation import validate_webhook_url

logger = logging.getLogger(__name__)


@dataclass
class SlackResult:
    """Result of a Slack webhook send attempt."""

    success: bool
    error: str | None = None


class SlackService:
    """
    Slack webhook service for alert notifications.

    Usage:
        service = SlackService()
        result = await service.send_alert(
            webhook_url="https://hooks.slack.com/services/T.../B.../xxx",
            alert_title="Sentiment Drop Detected",
            alert_message="Product X sentiment dropped 25%...",
            severity="high"
        )
    """

    def __init__(self):
        self.default_webhook_url = settings.SLACK_WEBHOOK_URL
        self.timeout = 10.0  # seconds

    async def send_alert(
        self,
        alert_title: str,
        alert_message: str,
        severity: str = "medium",
        webhook_url: str | None = None,
        alert_data: dict[str, Any] | None = None,
    ) -> SlackResult:
        """
        Send an alert to Slack via webhook.

        Args:
            alert_title: Alert title/headline
            alert_message: Main alert message
            severity: Alert severity (low, medium, high, critical)
            webhook_url: Slack webhook URL (uses default if not provided)
            alert_data: Optional extra data to include

        Returns:
            SlackResult with success status and any error message
        """
        url = webhook_url or self.default_webhook_url

        if not url:
            logger.warning("No Slack webhook URL configured - skipping notification")
            return SlackResult(success=False, error="No Slack webhook URL configured")

        # Validate URL to prevent SSRF
        url_error = validate_webhook_url(url)
        if url_error:
            logger.warning(f"Slack webhook URL rejected: {url_error}")
            return SlackResult(success=False, error=f"Invalid webhook URL: {url_error}")

        # Build Slack message payload
        payload = self._build_payload(
            alert_title=alert_title,
            alert_message=alert_message,
            severity=severity,
            alert_data=alert_data,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    logger.info(f"Slack notification sent: {alert_title}")
                    return SlackResult(success=True)
                else:
                    error_msg = f"Slack returned status {response.status_code}: {response.text}"
                    logger.error(f"Slack send failed: {error_msg}")
                    return SlackResult(success=False, error=error_msg)

        except httpx.TimeoutException:
            error_msg = "Slack webhook request timed out"
            logger.error(error_msg)
            return SlackResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Slack send error: {e!s}"
            logger.exception(error_msg)
            return SlackResult(success=False, error=error_msg)

    def _build_payload(
        self,
        alert_title: str,
        alert_message: str,
        severity: str,
        alert_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build Slack Block Kit payload."""

        severity_emoji = {
            "low": "ℹ️",
            "medium": "⚠️",
            "high": "🔴",
            "critical": "🚨",
        }
        emoji = severity_emoji.get(severity.lower(), "⚠️")

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} {alert_title}", "emoji": True}},
            {"type": "section", "text": {"type": "mrkdwn", "text": alert_message}},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"*Severity:* {severity.upper()} | *Source:* Social Sentiment Pricing"}
                ],
            },
        ]

        # Add data fields if provided
        if alert_data:
            fields = [
                {"type": "mrkdwn", "text": f"*{k}:*\n{v}"}
                for k, v in list(alert_data.items())[:10]  # Slack limit
            ]
            blocks.insert(2, {"type": "section", "fields": fields})

        # Add divider at the end
        blocks.append({"type": "divider"})

        return {
            "blocks": blocks,
            "text": f"{emoji} {alert_title}: {alert_message}",  # Fallback text
        }
