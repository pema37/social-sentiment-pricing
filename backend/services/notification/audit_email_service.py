"""
Audit Email Delivery Service

Sends retrospective audit PDFs to prospects or team members via SendGrid.
Uses the existing SendGrid configuration from EmailService.

Usage:
    service = AuditEmailService()
    result = await service.send_audit_pdf(
        to_email="prospect@store.com",
        pdf_bytes=pdf_bytes,
        store_name="Cool Store",
        headline_impact="$12,400",
    )
"""

import base64
import logging
from dataclasses import dataclass

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AuditEmailResult:
    """Result of an audit email send attempt."""

    success: bool
    message_id: str | None = None
    error: str | None = None


class AuditEmailService:
    """Sends audit PDF reports via SendGrid."""

    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.from_email)

    def _get_client(self):
        if not self._client and self.is_configured:
            try:
                from sendgrid import SendGridAPIClient

                self._client = SendGridAPIClient(self.api_key)
            except ImportError:
                logger.error("sendgrid package not installed")
                return None
        return self._client

    async def send_audit_pdf(
        self,
        to_email: str,
        pdf_bytes: bytes,
        store_name: str | None = None,
        headline_impact: str = "$0",
        lookback_days: int = 90,
        sender_name: str | None = None,
        personal_note: str | None = None,
    ) -> AuditEmailResult:
        """
        Send a pricing audit PDF via email.

        Args:
            to_email: Recipient email
            pdf_bytes: Raw PDF file bytes
            store_name: Prospect's store name (for subject line)
            headline_impact: The big number, e.g. "$12,400"
            lookback_days: Audit period
            sender_name: Your name for the sign-off
            personal_note: Optional personal message above the CTA
        """
        if not self.is_configured:
            logger.warning("SendGrid not configured — skipping audit email")
            return AuditEmailResult(success=False, error="SendGrid not configured (missing API key or from email)")

        client = self._get_client()
        if not client:
            return AuditEmailResult(success=False, error="Failed to initialize SendGrid client")

        try:
            from sendgrid.helpers.mail import (
                Attachment,
                Content,
                Disposition,
                Email,
                FileContent,
                FileName,
                FileType,
                Mail,
                To,
            )

            store_label = store_name or "your store"
            subject = f"Your Free Pricing Audit — {headline_impact} left on the table"

            html_content = self._build_html(
                store_name=store_label,
                headline_impact=headline_impact,
                lookback_days=lookback_days,
                sender_name=sender_name,
                personal_note=personal_note,
            )

            plain_content = self._build_plain(
                store_name=store_label,
                headline_impact=headline_impact,
                lookback_days=lookback_days,
                sender_name=sender_name,
                personal_note=personal_note,
            )

            message = Mail(
                from_email=Email(self.from_email, sender_name or "ActualPrice"),
                to_emails=To(to_email),
                subject=subject,
            )
            message.content = [
                Content("text/plain", plain_content),
                Content("text/html", html_content),
            ]

            # Attach the PDF
            encoded_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
            filename = f"pricing-audit-{lookback_days}d.pdf"

            attachment = Attachment()
            attachment.file_content = FileContent(encoded_pdf)
            attachment.file_name = FileName(filename)
            attachment.file_type = FileType("application/pdf")
            attachment.disposition = Disposition("attachment")
            message.attachment = attachment

            response = client.send(message)

            if response.status_code in (200, 201, 202):
                message_id = response.headers.get("X-Message-Id", "unknown")
                logger.info(f"Audit email sent to {to_email}, message_id={message_id}")
                return AuditEmailResult(success=True, message_id=message_id)
            else:
                error_msg = f"SendGrid returned status {response.status_code}"
                logger.error(f"Audit email failed: {error_msg}")
                return AuditEmailResult(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Audit email error: {e!s}"
            logger.exception(error_msg)
            return AuditEmailResult(success=False, error=error_msg)

    def _build_html(
        self,
        store_name: str,
        headline_impact: str,
        lookback_days: int,
        sender_name: str | None,
        personal_note: str | None,
    ) -> str:
        note_section = ""
        if personal_note:
            note_section = f"""
            <p style="color: #374151; line-height: 1.6; margin: 16px 0; padding: 12px 16px;
                      background: #f9fafb; border-left: 3px solid #1e40af; border-radius: 4px;">
                {personal_note}
            </p>
            """

        sign_off = sender_name or "The ActualPrice Team"

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

        <!-- Brand Header -->
        <div style="background: linear-gradient(135deg, #1e40af, #1e3a8a); padding: 24px;">
            <h1 style="color: white; margin: 0; font-size: 20px; font-weight: 700;">
                ActualPrice — Pricing Intelligence
            </h1>
        </div>

        <!-- Body -->
        <div style="padding: 24px;">
            <p style="color: #374151; line-height: 1.6; font-size: 16px;">
                Hi there,
            </p>

            <p style="color: #374151; line-height: 1.6;">
                I ran a free pricing analysis on <strong>{store_name}</strong> covering the
                last {lookback_days} days. Here's what I found:
            </p>

            <!-- Headline Number -->
            <div style="background: linear-gradient(135deg, #fef2f2, #fff7ed); border: 1px solid #fecaca;
                        border-radius: 12px; padding: 24px; text-align: center; margin: 20px 0;">
                <p style="color: #dc2626; font-size: 14px; text-transform: uppercase;
                          letter-spacing: 1px; margin: 0 0 8px 0; font-weight: 600;">
                    Estimated Money Left on the Table
                </p>
                <p style="color: #b91c1c; font-size: 42px; font-weight: 900; margin: 0;">
                    {headline_impact}
                </p>
                <p style="color: #6b7280; font-size: 14px; margin: 8px 0 0 0;">
                    Over the last {lookback_days} days
                </p>
            </div>

            <p style="color: #374151; line-height: 1.6;">
                The full breakdown is attached as a PDF — it shows every product,
                how many days each was over or underpriced, and the estimated
                revenue impact.
            </p>

            {note_section}

            <!-- CTA -->
            <div style="text-align: center; margin: 24px 0;">
                <a href="https://cal.com/actualprice/demo"
                   style="display: inline-block; padding: 14px 32px; background: #1e40af;
                          color: white; text-decoration: none; border-radius: 8px;
                          font-weight: 600; font-size: 16px;">
                    Book a 15-min Demo
                </a>
                <p style="color: #9ca3af; font-size: 12px; margin-top: 8px;">
                    See how ActualPrice can automate this for you 24/7
                </p>
            </div>

            <p style="color: #374151; line-height: 1.6;">
                Best,<br>
                <strong>{sign_off}</strong>
            </p>
        </div>

        <!-- Footer -->
        <div style="background: #f9fafb; padding: 16px 24px; border-top: 1px solid #e5e7eb;">
            <p style="color: #9ca3af; font-size: 11px; margin: 0; text-align: center;">
                ActualPrice — AI-powered pricing intelligence for e-commerce merchants
            </p>
        </div>
    </div>
</body>
</html>
        """

    def _build_plain(
        self,
        store_name: str,
        headline_impact: str,
        lookback_days: int,
        sender_name: str | None,
        personal_note: str | None,
    ) -> str:
        lines = [
            "Hi there,",
            "",
            f"I ran a free pricing analysis on {store_name} covering the last {lookback_days} days.",
            "",
            f"Estimated money left on the table: {headline_impact}",
            "",
            "The full breakdown is attached as a PDF — it shows every product,",
            "how many days each was over or underpriced, and the estimated revenue impact.",
            "",
        ]

        if personal_note:
            lines.extend([personal_note, ""])

        lines.extend(
            [
                "Want to see how ActualPrice can automate this for you?",
                "Book a demo: https://cal.com/actualprice/demo",
                "",
                "Best,",
                sender_name or "The ActualPrice Team",
                "",
                "---",
                "ActualPrice — AI-powered pricing intelligence for e-commerce merchants",
            ]
        )

        return "\n".join(lines)
