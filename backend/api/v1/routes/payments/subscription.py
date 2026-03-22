"""
Subscription Routes

Thin HTTP layer that delegates all business logic to SubscriptionService.
Following single responsibility principle - routes only handle:
- Request parsing
- Authentication
- Response formatting
- HTTP error mapping
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from db.session import get_session
from models.user import User
from schemas.payment import (
    ConfirmPaymentRequest,
    ConfirmPaymentResponse,
    PaymentHistoryResponse,
    PaymentInfo,
    PaymentRequest,
    PlanInfo,
    SubscribeRequest,
    SubscriptionInfo,
)
from services.payment import PLANS, SubscriptionService

router = APIRouter(tags=["subscriptions"])


# =============================================================================
# DEPENDENCY
# =============================================================================


def get_subscription_service(
    session: AsyncSession = Depends(get_session),
) -> SubscriptionService:
    """Dependency injection for subscription service."""
    return SubscriptionService(session)


# =============================================================================
# PLAN ENDPOINTS
# =============================================================================


@router.get("/plans", response_model=list[PlanInfo])
async def get_plans():
    """Get all available subscription plans."""
    return PLANS


# =============================================================================
# SUBSCRIPTION ENDPOINTS
# =============================================================================


@router.get("/subscription", response_model=SubscriptionInfo)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get current user's subscription."""
    return await service.get_user_subscription(current_user)


@router.post("/downgrade-to-free", response_model=SubscriptionInfo)
async def downgrade_to_free(
    current_user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Downgrade the current user's subscription to the free tier.

    This cancels any active paid subscription and moves them to free.
    No payment required.
    """
    return await service.downgrade_to_free(current_user)


@router.post("/subscribe", response_model=PaymentRequest)
async def subscribe(
    data: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Create a subscription payment request.

    Returns payment details for the user to complete via MNEE.
    The recipient_address will be network-specific:
    - For 'ethereum': Returns Ethereum wallet (0x...)
    - For 'bsv': Returns BSV wallet (1... or $handle)
    """
    try:
        payment_request, _ = await service.create_subscription_payment(
            user=current_user,
            tier=data.tier,
            billing_cycle=data.billing_cycle,
            network=data.network,  # FIXED: Pass network to service!
        )
        return payment_request
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# PAYMENT ENDPOINTS
# =============================================================================


@router.get("/history", response_model=PaymentHistoryResponse)
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
    limit: int = 20,
    offset: int = 0,
):
    """Get user's payment history."""
    capped_limit = min(limit, 100)
    payments, total = await service.get_payment_history(
        user=current_user,
        limit=capped_limit,
        offset=offset,
    )
    return PaymentHistoryResponse(
        payments=payments,
        total=total,
        limit=capped_limit,
        offset=offset,
    )


@router.get("/{payment_id}", response_model=PaymentInfo)
async def get_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """Get payment status."""
    try:
        payment_uuid = UUID(payment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment ID format",
        )

    payment = await service.get_payment(payment_uuid, current_user)

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return payment


@router.post("/{payment_id}/confirm", response_model=ConfirmPaymentResponse)
async def confirm_payment(
    payment_id: str,
    data: ConfirmPaymentRequest,
    current_user: User = Depends(get_current_user),
    service: SubscriptionService = Depends(get_subscription_service),
):
    """
    Confirm a payment with transaction hash.
    Verifies the transaction on blockchain and activates subscription.
    """
    try:
        payment_uuid = UUID(payment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment ID format",
        )

    result = await service.confirm_payment(
        payment_id=payment_uuid,
        user=current_user,
        transaction_hash=data.transaction_hash,
        network=data.network,
    )

    if not result.success and "not found" in result.message.lower():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result.message,
        )

    return result
