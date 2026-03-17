# backend/services/notification/__init__.py
"""
Notification Services

Multi-channel alert delivery: Email (SendGrid), Slack (Webhooks), Webhook (Custom), In-App.
Alert generation from system events.
"""

from services.notification.alert_generator import AlertGenerator
from services.notification.email_service import EmailService
from services.notification.notification_dispatcher import (
    NotificationDispatcher,
    send_quick_alert,
)
from services.notification.slack_service import SlackService
from services.notification.webhook_service import WebhookService

__all__ = [
    "AlertGenerator",
    "EmailService",
    "NotificationDispatcher",
    "SlackService",
    "WebhookService",
    "send_quick_alert",
]
