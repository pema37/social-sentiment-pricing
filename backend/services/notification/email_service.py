# backend/services/notification/email_service.py
"""
Email notification service using SendGrid.

SendGrid Free Tier: 100 emails/day
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    """Result of an email send attempt."""

    success: bool
    message_id: str | None = None
    error: str | None = None


class EmailService:
    """
    SendGrid email service for alert notifications.

    Usage:
        service = EmailService()
        result = await service.send_alert_email(
            to_email="user@example.com",
            subject="Price Alert",
            alert_title="Sentiment Drop Detected",
            alert_message="Product X sentiment dropped 25%...",
            alert_data={"product": "X", "change": -0.25}
        )
    """

    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self._client = None

    @property
    def is_configured(self) -> bool:
        """Check if SendGrid is properly configured."""
        return bool(self.api_key and self.from_email)

    def _get_client(self):
        """Lazy-load SendGrid client."""
        if not self._client and self.is_configured:
            try:
                from sendgrid import SendGridAPIClient

                self._client = SendGridAPIClient(self.api_key)
            except ImportError:
                logger.error("sendgrid package not installed. Run: pip install sendgrid")
                return None
        return self._client

    async def send_alert_email(
        self,
        to_email: str,
        subject: str,
        alert_title: str,
        alert_message: str,
        alert_data: dict[str, Any] | None = None,
        severity: str = "medium",
    ) -> EmailResult:
        """
        Send an alert notification email.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            alert_title: Alert title/headline
            alert_message: Main alert message
            alert_data: Optional structured data to include
            severity: Alert severity (low, medium, high, critical)

        Returns:
            EmailResult with success status and any error message
        """
        if not self.is_configured:
            logger.warning("SendGrid not configured - skipping email notification")
            return EmailResult(success=False, error="SendGrid not configured (missing API key or from email)")

        client = self._get_client()
        if not client:
            return EmailResult(success=False, error="Failed to initialize SendGrid client")

        try:
            from sendgrid.helpers.mail import Content, Email, Mail, To

            # Build HTML content
            html_content = self._build_alert_html(
                alert_title=alert_title,
                alert_message=alert_message,
                alert_data=alert_data,
                severity=severity,
            )

            # Build plain text fallback
            plain_content = self._build_alert_plain(
                alert_title=alert_title,
                alert_message=alert_message,
                alert_data=alert_data,
            )

            message = Mail(
                from_email=Email(self.from_email),
                to_emails=To(to_email),
                subject=subject,
            )
            message.content = [
                Content("text/plain", plain_content),
                Content("text/html", html_content),
            ]

            response = await asyncio.to_thread(client.send, message)

            if response.status_code in (200, 201, 202):
                message_id = response.headers.get("X-Message-Id", "unknown")
                logger.info(f"Email sent successfully to {to_email}, message_id={message_id}")
                return EmailResult(success=True, message_id=message_id)
            else:
                error_msg = f"SendGrid returned status {response.status_code}"
                logger.error(f"Email send failed: {error_msg}")
                return EmailResult(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Email send error: {e!s}"
            logger.exception(error_msg)
            return EmailResult(success=False, error=error_msg)

    def _build_alert_html(
        self,
        alert_title: str,
        alert_message: str,
        alert_data: dict[str, Any] | None,
        severity: str,
    ) -> str:
        """Build HTML email content for alert."""
        severity_colors = {
            "low": "#6B7280",  # Gray
            "medium": "#F59E0B",  # Amber
            "high": "#EF4444",  # Red
            "critical": "#DC2626",  # Dark Red
        }
        color = severity_colors.get(severity.lower(), "#6B7280")

        data_section = ""
        if alert_data:
            data_items = "".join(
                f"<tr><td style='padding: 4px 8px; border-bottom: 1px solid #eee;'><strong>{k}:</strong></td>"
                f"<td style='padding: 4px 8px; border-bottom: 1px solid #eee;'>{v}</td></tr>"
                for k, v in alert_data.items()
            )
            data_section = f"""
            <table style='width: 100%; margin-top: 16px; font-size: 14px;'>
                {data_items}
            </table>
            """

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             background-color: #f3f4f6; margin: 0; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden;">

        <!-- Header -->
        <div style="background-color: {color}; padding: 16px 24px;">
            <h1 style="color: white; margin: 0; font-size: 18px; font-weight: 600;">
                ⚠️ {alert_title}
            </h1>
            <span style="color: rgba(255,255,255,0.8); font-size: 12px; text-transform: uppercase;">
                {severity.upper()} PRIORITY
            </span>
        </div>

        <!-- Body -->
        <div style="padding: 24px;">
            <p style="color: #374151; line-height: 1.6; margin: 0 0 16px 0; white-space: pre-wrap;">
                {alert_message}
            </p>

            {data_section}
        </div>

        <!-- Footer -->
        <div style="background-color: #f9fafb; padding: 16px 24px; border-top: 1px solid #e5e7eb;">
            <p style="color: #6b7280; font-size: 12px; margin: 0;">
                This alert was generated by Social Sentiment Pricing.
            </p>
        </div>
    </div>
</body>
</html>
        """

    def _build_alert_plain(
        self,
        alert_title: str,
        alert_message: str,
        alert_data: dict[str, Any] | None,
    ) -> str:
        """Build plain text email content for alert."""
        lines = [
            f"=== {alert_title} ===",
            "",
            alert_message,
            "",
        ]

        if alert_data:
            lines.append("Details:")
            for k, v in alert_data.items():
                lines.append(f"  - {k}: {v}")
            lines.append("")

        lines.extend(
            [
                "---",
                "This alert was generated by Social Sentiment Pricing.",
            ]
        )

        return "\n".join(lines)
