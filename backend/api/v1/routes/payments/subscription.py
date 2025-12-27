# backend/api/v1/routes/payments/subscription.py

"""
Subscription Management Endpoints

Handles subscription plans, upgrades, and payment processing.
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import BaseModel

from db.session import get_session
from core.deps import get_current_user
from models.user import User
from models.subscription import Subscription, SubscriptionTier, TIER_LIMITS_STR
from models.payment import Payment

router = APIRouter(tags=["subscriptions"])


# =============================================================================
# SCHEMAS
# =============================================================================

class PlanInfo(BaseModel):
    """Subscription plan information."""
    tier: str
    name: str
    price_monthly: float
    price_yearly: float
    product_limit: int
    features: List[str]


class SubscriptionInfo(BaseModel):
    """Current subscription information."""
    tier: str
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    product_limit: int
    products_used: int


class SubscribeRequest(BaseModel):
    """Request to subscribe to a plan."""
    tier: str
    billing_cycle: str = "monthly"  # monthly or yearly


class PaymentRequest(BaseModel):
    """Payment request details."""
    payment_id: str
    amount: str
    amount_raw: int
    recipient_address: str
    memo: str
    expires_at: datetime


class PaymentInfo(BaseModel):
    """Payment information."""
    id: str
    amount: str
    status: str
    payment_type: str
    created_at: datetime
    transaction_hash: Optional[str]


# =============================================================================
# PLAN DEFINITIONS
# =============================================================================

PLANS: List[PlanInfo] = [
    PlanInfo(
        tier="free",
        name="Free",
        price_monthly=0,
        price_yearly=0,
        product_limit=5,
        features=[
            "Up to 5 products",
            "Basic sentiment analysis",
            "Daily price updates",
            "Email support",
        ],
    ),
    PlanInfo(
        tier="starter",
        name="Starter",
        price_monthly=29,
        price_yearly=290,
        product_limit=50,
        features=[
            "Up to 50 products",
            "Advanced sentiment analysis",
            "Hourly price updates",
            "Competitor tracking (3 competitors)",
            "Priority email support",
        ],
    ),
    PlanInfo(
        tier="professional",
        name="Professional",
        price_monthly=99,
        price_yearly=990,
        product_limit=500,
        features=[
            "Up to 500 products",
            "Real-time sentiment analysis",
            "Real-time price updates",
            "Competitor tracking (10 competitors)",
            "API access",
            "Dedicated support",
        ],
    ),
    PlanInfo(
        tier="enterprise",
        name="Enterprise",
        price_monthly=299,
        price_yearly=2990,
        product_limit=-1,  # Unlimited
        features=[
            "Unlimited products",
            "Real-time sentiment analysis",
            "Real-time price updates",
            "Unlimited competitor tracking",
            "Full API access",
            "Custom integrations",
            "24/7 dedicated support",
            "SLA guarantee",
        ],
    ),
]


def get_product_limit(tier: str) -> int:
    """Get product limit for a tier."""
    tier_config = TIER_LIMITS_STR.get(tier, TIER_LIMITS_STR["free"])
    return tier_config.get("products", 5)


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/plans", response_model=List[PlanInfo])
async def get_plans():
    """
    Get all available subscription plans.
    """
    return PLANS


@router.get("/subscription", response_model=SubscriptionInfo)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get current user's subscription.
    """
    # Find active subscription - using string comparison
    result = await session.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .where(Subscription.status == "active")
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        # Return free tier info
        return SubscriptionInfo(
            tier="free",
            status="active",
            current_period_start=None,
            current_period_end=None,
            product_limit=get_product_limit("free"),
            products_used=0,  # TODO: Get actual count
        )
    
    # subscription.tier and subscription.status are now strings, not Enums
    return SubscriptionInfo(
        tier=subscription.tier,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        product_limit=get_product_limit(subscription.tier),
        products_used=0,  # TODO: Get actual count
    )


@router.post("/subscribe", response_model=PaymentRequest)
async def subscribe(
    data: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a subscription payment request.
    Returns payment details for the user to complete via MNEE.
    """
    # Validate tier
    valid_tiers = ["free", "starter", "professional", "enterprise"]
    if data.tier not in valid_tiers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {data.tier}. Must be one of: {valid_tiers}",
        )
    
    # Free tier doesn't need payment
    if data.tier == "free":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Free tier doesn't require payment",
        )
    
    # Get plan pricing
    plan = next((p for p in PLANS if p.tier == data.tier), None)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plan not found",
        )
    
    # Calculate amount
    if data.billing_cycle == "yearly":
        amount = plan.price_yearly
    else:
        amount = plan.price_monthly
    
    # MNEE uses 5 decimal places (1 MNEE = $1)
    amount_raw = int(amount * 100000)
    
    # Create pending payment record
    # Pass UUID object (not string) - database column is UUID type
    payment_id = uuid4()
    
    payment = Payment(
        id=payment_id,  # UUID object, not str(uuid4())
        user_id=current_user.id,
        amount=str(amount),
        amount_raw=amount_raw,
        payment_type="subscription",
        status="pending",
        metadata_json=json.dumps({
            "tier": data.tier,
            "billing_cycle": data.billing_cycle,
        }),
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    
    # Get SSP wallet address from environment or use placeholder
    recipient_address = os.getenv("SSP_MNEE_WALLET_ADDRESS", "")
    if not recipient_address:
        # Use a placeholder for demo - in production this should fail
        recipient_address = "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"
    
    # Convert UUID to string for response
    payment_id_str = str(payment.id)
    
    return PaymentRequest(
        payment_id=payment_id_str,
        amount=f"{amount:.2f}",
        amount_raw=amount_raw,
        recipient_address=recipient_address,
        memo=f"SSP-{payment_id_str[:8]}",
        expires_at=datetime.utcnow() + timedelta(hours=1),
    )


@router.get("/payments/{payment_id}", response_model=PaymentInfo)
async def get_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get payment status.
    """
    result = await session.execute(
        select(Payment)
        .where(Payment.id == payment_id)
        .where(Payment.user_id == current_user.id)
    )
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    
    return PaymentInfo(
        id=payment.id,
        amount=payment.amount,
        status=payment.status,
        payment_type=payment.payment_type,
        created_at=payment.created_at,
        transaction_hash=payment.transaction_hash,
    )


@router.get("/history", response_model=List[PaymentInfo])
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    limit: int = 20,
    offset: int = 0,
):
    """
    Get user's payment history.
    """
    result = await session.execute(
        select(Payment)
        .where(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    payments = result.scalars().all()
    
    return [
        PaymentInfo(
            id=p.id,
            amount=p.amount,
            status=p.status,
            payment_type=p.payment_type,
            created_at=p.created_at,
            transaction_hash=p.transaction_hash,
        )
        for p in payments
    ]
