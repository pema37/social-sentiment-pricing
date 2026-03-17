# backend/api/v1/routes/payments/webhook.py

"""
MNEE Webhook Endpoints

Handles payment confirmations from MNEE.
"""

import hashlib
import hmac
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import settings
from db.session import get_session
from models.payment import Payment, PaymentStatus
from models.subscription import Subscription, SubscriptionStatus, SubscriptionTier

router = APIRouter(tags=["webhooks"])


# =============================================================================
# SCHEMAS
# =============================================================================


class MneeWebhookPayload(BaseModel):
    """MNEE webhook payload."""

    transaction_id: str
    from_address: str
    to_address: str
    amount: str
    amount_raw: int
    memo: str | None = None
    block_height: int | None = None
    confirmations: int = 0


class WebhookResponse(BaseModel):
    """Webhook response."""

    success: bool
    message: str


# =============================================================================
# HELPERS
# =============================================================================


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify MNEE webhook signature.
    """
    secret = settings.MNEE_WEBHOOK_SECRET
    if not secret:
        # No secret configured, skip verification in development
        return True

    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


async def process_payment_confirmation(
    payment: Payment,
    payload: MneeWebhookPayload,
    session: AsyncSession,
):
    """
    Process a confirmed payment and activate subscription.
    """
    # Update payment status
    payment.status = PaymentStatus.CONFIRMED
    payment.transaction_hash = payload.transaction_id
    payment.confirmed_at = datetime.now(UTC)
    session.add(payment)

    # If this is a subscription payment, create/update subscription
    if payment.metadata and payment.metadata.get("tier"):
        tier = SubscriptionTier(payment.metadata["tier"])
        billing_cycle = payment.metadata.get("billing_cycle", "monthly")

        # Calculate period
        now = datetime.now(UTC)
        if billing_cycle == "yearly":
            period_end = now + timedelta(days=365)
        else:
            period_end = now + timedelta(days=30)

        # Check for existing subscription
        result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == payment.user_id)
            .where(Subscription.status == SubscriptionStatus.ACTIVE)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing subscription
            existing.tier = tier
            existing.current_period_start = now
            existing.current_period_end = period_end
            session.add(existing)
        else:
            # Create new subscription
            subscription = Subscription(
                user_id=payment.user_id,
                tier=tier,
                status=SubscriptionStatus.ACTIVE,
                current_period_start=now,
                current_period_end=period_end,
            )
            session.add(subscription)

    await session.commit()


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/webhook/mnee", response_model=WebhookResponse)
async def mnee_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Handle MNEE payment webhooks.
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify signature if configured
    signature = request.headers.get("X-MNEE-Signature", "")
    if settings.MNEE_WEBHOOK_SECRET and not verify_webhook_signature(body, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse payload
    try:
        payload = MneeWebhookPayload.model_validate_json(body)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid payload: {e!s}",
        )

    # Extract payment ID from memo (format: SSP-{payment_id_prefix})
    if not payload.memo or not payload.memo.startswith("SSP-"):
        # Not our payment, ignore
        return WebhookResponse(success=True, message="Ignored: not SSP payment")

    payment_id_prefix = payload.memo[4:]  # Remove "SSP-" prefix

    # Find matching payment
    result = await session.execute(
        select(Payment).where(Payment.id.startswith(payment_id_prefix)).where(Payment.status == PaymentStatus.PENDING)
    )
    payment = result.scalar_one_or_none()

    if not payment:
        return WebhookResponse(success=True, message="Payment not found or already processed")

    # Verify amount matches
    if payload.amount_raw < payment.amount_raw:
        payment.status = PaymentStatus.FAILED
        payment.metadata = {**payment.metadata, "error": "Insufficient amount"}
        session.add(payment)
        await session.commit()
        return WebhookResponse(success=False, message="Insufficient payment amount")

    # Process payment in background
    background_tasks.add_task(
        process_payment_confirmation,
        payment,
        payload,
        session,
    )

    return WebhookResponse(success=True, message="Payment processing")


@router.get("/webhook/mnee/test")
async def test_webhook():
    """
    Test endpoint to verify webhook is reachable.
    """
    return {
        "status": "ok",
        "message": "MNEE webhook endpoint is active",
        "timestamp": datetime.now(UTC).isoformat(),
    }
