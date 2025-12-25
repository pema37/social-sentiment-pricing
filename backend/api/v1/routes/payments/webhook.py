"""
Payment Webhook Routes

Handles MNEE payment webhook notifications.
"""

import hmac
import hashlib
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status, BackgroundTasks
from pydantic import BaseModel

from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Schemas
# =============================================================================

class WebhookResponse(BaseModel):
    """Webhook acknowledgment response."""
    status: str = "ok"
    message: Optional[str] = None


# =============================================================================
# Webhook Verification
# =============================================================================

def verify_mnee_signature(payload: bytes, signature: str) -> bool:
    """
    Verify MNEE webhook signature.
    
    Args:
        payload: Raw request body
        signature: X-Mnee-Signature header value
        
    Returns:
        True if signature is valid
    """
    webhook_secret = settings.MNEE_WEBHOOK_SECRET
    
    if not webhook_secret:
        logger.warning("MNEE_WEBHOOK_SECRET not configured - skipping verification")
        # In development, allow unverified webhooks
        return settings.ENVIRONMENT == "development"
    
    expected = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    
    return hmac.compare_digest(expected, signature)


# =============================================================================
# Background Tasks
# =============================================================================

async def process_payment_received(data: dict):
    """
    Process payment.received webhook event.
    
    Called when MNEE detects incoming payment.
    """
    txid = data.get("txid")
    memo = data.get("memo", "")
    amount = data.get("amount")
    
    logger.info(f"Payment received: txid={txid}, memo={memo}, amount={amount}")
    
    # Parse memo to find payment
    # Memo format: SSP-{user_id}-{tier}-{timestamp}
    if not memo.startswith("SSP-"):
        logger.warning(f"Unknown memo format: {memo}")
        return
    
    parts = memo.split("-")
    if len(parts) < 3:
        logger.warning(f"Invalid memo format: {memo}")
        return
    
    user_id = parts[1]
    tier = parts[2]
    
    logger.info(f"Payment matched: user={user_id}, tier={tier}")
    
    # TODO: Update payment record in database
    # payment.status = "processing"
    # payment.txid = txid
    # await db.commit()


async def process_payment_confirmed(data: dict):
    """
    Process payment.confirmed webhook event.
    
    Called when payment is confirmed on blockchain.
    Activates user subscription.
    """
    txid = data.get("txid")
    memo = data.get("memo", "")
    
    logger.info(f"Payment confirmed: txid={txid}")
    
    if not memo.startswith("SSP-"):
        logger.warning(f"Unknown memo format: {memo}")
        return
    
    parts = memo.split("-")
    if len(parts) < 3:
        return
    
    user_id = parts[1]
    tier = parts[2]
    
    logger.info(f"Activating subscription: user={user_id}, tier={tier}")
    
    # TODO: Activate subscription in database
    # subscription.tier = tier
    # subscription.status = "active"
    # subscription.current_period_start = datetime.utcnow()
    # subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
    # await db.commit()


async def process_payment_failed(data: dict):
    """
    Process payment.failed webhook event.
    
    Called when payment fails.
    """
    txid = data.get("txid")
    reason = data.get("reason", "Unknown")
    
    logger.warning(f"Payment failed: txid={txid}, reason={reason}")
    
    # TODO: Update payment record
    # payment.status = "failed"
    # payment.error_message = reason
    # await db.commit()
    
    # TODO: Notify user of failed payment


# =============================================================================
# Routes
# =============================================================================

@router.post(
    "/webhook/mnee",
    response_model=WebhookResponse,
    summary="MNEE payment webhook",
    description="Receives payment notifications from MNEE"
)
async def mnee_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Handle MNEE payment webhooks.
    
    Events:
    - payment.received: Payment detected
    - payment.confirmed: Payment confirmed on blockchain
    - payment.failed: Payment failed
    """
    # Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("X-Mnee-Signature", "")
    
    # Verify signature
    if not verify_mnee_signature(body, signature):
        logger.warning("Invalid MNEE webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )
    
    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )
    
    event_type = payload.get("type")
    data = payload.get("data", {})
    
    logger.info(f"MNEE webhook received: {event_type}")
    
    # Route to appropriate handler
    if event_type == "payment.received":
        background_tasks.add_task(process_payment_received, data)
    
    elif event_type == "payment.confirmed":
        background_tasks.add_task(process_payment_confirmed, data)
    
    elif event_type == "payment.failed":
        background_tasks.add_task(process_payment_failed, data)
    
    else:
        logger.warning(f"Unknown webhook event type: {event_type}")
    
    return WebhookResponse(status="ok")


@router.get(
    "/webhook/mnee/test",
    response_model=WebhookResponse,
    summary="Test webhook endpoint",
    description="Verify webhook endpoint is reachable (for MNEE setup)"
)
async def test_webhook():
    """
    Test endpoint for MNEE webhook verification.
    
    MNEE may ping this to verify the webhook URL is valid.
    """
    return WebhookResponse(
        status="ok",
        message="MNEE webhook endpoint is active",
    )
