# backend/services/notification/notification_dispatcher.py
"""
Multi-channel notification dispatcher.

Orchestrates sending alerts across Email, Slack, and In-App channels.
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from backend.services.notification.email_service import EmailService, EmailResult
from backend.services.notification.slack_service import SlackService, SlackResult
from backend.models.alert import AlertChannel

logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    """Result of dispatching to multiple channels."""
    channels_sent: List[str] = field(default_factory=list)
    channels_failed: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """At least one channel succeeded."""
        return len(self.channels_sent) > 0
    
    @property
    def partial(self) -> bool:
        """Some channels succeeded, some failed."""
        return len(self.channels_sent) > 0 and len(self.channels_failed) > 0


class NotificationDispatcher:
    """
    Dispatches alerts to multiple notification channels.
    
    Usage:
        dispatcher = NotificationDispatcher()
        result = await dispatcher.dispatch(
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK],
            alert_title="Price Alert",
            alert_message="Product X price dropped...",
            severity="high",
            recipient_email="user@example.com",
            slack_webhook_url="https://hooks.slack.com/..."
        )
    """
    
    def __init__(self):
        self.email_service = EmailService()
        self.slack_service = SlackService()
    
    async def dispatch(
        self,
        channels: List[AlertChannel],
        alert_title: str,
        alert_message: str,
        severity: str = "medium",
        alert_data: Optional[Dict[str, Any]] = None,
        # Email-specific
        recipient_email: Optional[str] = None,
        email_subject: Optional[str] = None,
        # Slack-specific
        slack_webhook_url: Optional[str] = None,
    ) -> DispatchResult:
        """
        Dispatch alert to specified channels.
        
        Args:
            channels: List of channels to send to
            alert_title: Alert headline
            alert_message: Main message
            severity: low/medium/high/critical
            alert_data: Optional structured data
            recipient_email: Email address (required for EMAIL channel)
            email_subject: Custom email subject (defaults to alert_title)
            slack_webhook_url: Slack webhook (uses default if not provided)
            
        Returns:
            DispatchResult with success/failure per channel
        """
        result = DispatchResult()
        
        for channel in channels:
            if channel == AlertChannel.EMAIL:
                await self._send_email(
                    result=result,
                    recipient_email=recipient_email,
                    subject=email_subject or f"[SSP Alert] {alert_title}",
                    alert_title=alert_title,
                    alert_message=alert_message,
                    severity=severity,
                    alert_data=alert_data,
                )
                
            elif channel == AlertChannel.SLACK:
                await self._send_slack(
                    result=result,
                    webhook_url=slack_webhook_url,
                    alert_title=alert_title,
                    alert_message=alert_message,
                    severity=severity,
                    alert_data=alert_data,
                )
                
            elif channel == AlertChannel.IN_APP:
                # In-app is just database storage - always succeeds
                result.channels_sent.append("in_app")
                logger.debug(f"In-app alert recorded: {alert_title}")
                
            elif channel == AlertChannel.WEBHOOK:
                # Webhook support - future enhancement
                result.channels_failed.append("webhook")
                result.errors["webhook"] = "Webhook channel not yet implemented"
        
        return result
    
    async def _send_email(
        self,
        result: DispatchResult,
        recipient_email: Optional[str],
        subject: str,
        alert_title: str,
        alert_message: str,
        severity: str,
        alert_data: Optional[Dict[str, Any]],
    ) -> None:
        """Send email and update result."""
        if not recipient_email:
            result.channels_failed.append("email")
            result.errors["email"] = "No recipient email provided"
            return
        
        email_result: EmailResult = await self.email_service.send_alert_email(
            to_email=recipient_email,
            subject=subject,
            alert_title=alert_title,
            alert_message=alert_message,
            alert_data=alert_data,
            severity=severity,
        )
        
        if email_result.success:
            result.channels_sent.append("email")
        else:
            result.channels_failed.append("email")
            result.errors["email"] = email_result.error or "Unknown error"
    
    async def _send_slack(
        self,
        result: DispatchResult,
        webhook_url: Optional[str],
        alert_title: str,
        alert_message: str,
        severity: str,
        alert_data: Optional[Dict[str, Any]],
    ) -> None:
        """Send Slack notification and update result."""
        slack_result: SlackResult = await self.slack_service.send_alert(
            webhook_url=webhook_url,
            alert_title=alert_title,
            alert_message=alert_message,
            severity=severity,
            alert_data=alert_data,
        )
        
        if slack_result.success:
            result.channels_sent.append("slack")
        else:
            result.channels_failed.append("slack")
            result.errors["slack"] = slack_result.error or "Unknown error"


# Convenience function for quick alerts
async def send_quick_alert(
    title: str,
    message: str,
    severity: str = "medium",
    email: Optional[str] = None,
    slack_webhook: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> DispatchResult:
    """
    Quick way to send an alert without creating a dispatcher.
    
    Usage:
        from backend.services.notification import send_quick_alert
        
        result = await send_quick_alert(
            title="Sentiment Drop",
            message="Product X dropped 25%",
            severity="high",
            email="user@example.com"
        )
    """
    channels = [AlertChannel.IN_APP]  # Always include in-app
    
    if email:
        channels.append(AlertChannel.EMAIL)
    if slack_webhook:
        channels.append(AlertChannel.SLACK)
    
    dispatcher = NotificationDispatcher()
    return await dispatcher.dispatch(
        channels=channels,
        alert_title=title,
        alert_message=message,
        severity=severity,
        alert_data=data,
        recipient_email=email,
        slack_webhook_url=slack_webhook,
    )
