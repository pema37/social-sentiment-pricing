# backend/services/notification/webhook_service.py
"""
Generic webhook notification service.

Sends alerts to user-defined webhook URLs with HMAC signature support.
"""

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class WebhookResult:
    """Result of a webhook send attempt."""

    success: bool
    status_code: int | None = None
    error: str | None = None


class WebhookService:
    """
    Generic webhook service for alert notifications.

    Sends JSON payloads to user-defined URLs with optional HMAC signing.

    Usage:
        service = WebhookService()
        result = await service.send_alert(
            webhook_url="https://myserver.com/alerts",
            webhook_secret="my-secret-key",  # optional
            alert_title="Sentiment Drop Detected",
            alert_message="Product X sentiment dropped 25%...",
            severity="high",
            alert_data={"product_id": "123", "score": -0.45}
        )
    """

    def __init__(self):
        self.timeout = 10.0  # seconds
        self.max_retries = 2

    async def send_alert(
        self,
        webhook_url: str,
        alert_title: str,
        alert_message: str,
        severity: str = "medium",
        alert_type: str | None = None,
        alert_id: str | None = None,
        webhook_secret: str | None = None,
        alert_data: dict[str, Any] | None = None,
    ) -> WebhookResult:
        """
        Send an alert to a webhook URL.

        Args:
            webhook_url: Target URL to POST to
            alert_title: Alert title/headline
            alert_message: Main alert message
            severity: Alert severity (low, medium, high, critical)
            alert_type: Type of alert (sentiment_drop, price_recommendation, etc.)
            alert_id: Unique alert ID for deduplication
            webhook_secret: Optional secret for HMAC-SHA256 signature
            alert_data: Optional extra data to include

        Returns:
            WebhookResult with success status, status code, and any error
        """
        if not webhook_url:
            return WebhookResult(success=False, error="No webhook URL provided")

        # Build payload
        payload = self._build_payload(
            alert_id=alert_id,
            alert_title=alert_title,
            alert_message=alert_message,
            alert_type=alert_type,
            severity=severity,
            alert_data=alert_data,
        )

        # Build headers
        headers = self._build_headers(payload, webhook_secret)

        # Send with retries
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        webhook_url,
                        json=payload,
                        headers=headers,
                    )

                    if response.status_code in (200, 201, 202, 204):
                        logger.info(
                            "Webhook sent successfully",
                            extra={
                                "webhook_url": self._mask_url(webhook_url),
                                "alert_title": alert_title,
                                "status_code": response.status_code,
                            },
                        )
                        return WebhookResult(
                            success=True,
                            status_code=response.status_code,
                        )
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                        logger.warning(
                            "Webhook returned non-success status",
                            extra={
                                "webhook_url": self._mask_url(webhook_url),
                                "status_code": response.status_code,
                                "attempt": attempt + 1,
                            },
                        )

            except httpx.TimeoutException:
                last_error = "Request timed out"
                logger.warning(f"Webhook timeout, attempt {attempt + 1}")
            except httpx.ConnectError as e:
                last_error = f"Connection failed: {e!s}"
                logger.warning(f"Webhook connection error, attempt {attempt + 1}")
            except Exception as e:
                last_error = f"Unexpected error: {e!s}"
                logger.exception(f"Webhook send error, attempt {attempt + 1}")

            # Wait before retry (exponential backoff)
            if attempt < self.max_retries:
                await self._sleep(2**attempt)

        logger.error(
            f"Webhook failed after {self.max_retries + 1} attempts",
            extra={
                "webhook_url": self._mask_url(webhook_url),
                "error": last_error,
            },
        )
        return WebhookResult(success=False, error=last_error)

    def _build_payload(
        self,
        alert_id: str | None,
        alert_title: str,
        alert_message: str,
        alert_type: str | None,
        severity: str,
        alert_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build webhook JSON payload."""
        payload = {
            "event": "alert",
            "timestamp": int(time.time()),
            "alert": {
                "id": alert_id,
                "title": alert_title,
                "message": alert_message,
                "type": alert_type,
                "severity": severity,
            },
            "source": "social-sentiment-pricing",
        }

        if alert_data:
            payload["alert"]["data"] = alert_data

        return payload

    def _build_headers(
        self,
        payload: dict[str, Any],
        secret: str | None,
    ) -> dict[str, str]:
        """Build request headers with optional HMAC signature."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "SSP-Webhook/1.0",
        }

        if secret:
            # Create HMAC-SHA256 signature
            payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
            signature = hmac.new(
                secret.encode("utf-8"),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()
            headers["X-SSP-Signature"] = f"sha256={signature}"
            headers["X-SSP-Timestamp"] = str(int(time.time()))

        return headers

    def _mask_url(self, url: str) -> str:
        """Mask webhook URL for logging (hide sensitive parts)."""
        if len(url) > 30:
            return url[:20] + "..." + url[-10:]
        return url

    async def _sleep(self, seconds: float) -> None:
        """Async sleep for retry backoff."""
        import asyncio

        await asyncio.sleep(seconds)
