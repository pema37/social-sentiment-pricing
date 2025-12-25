"""
Subscription Routes

Handles subscription plans, billing, and payment history.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_db
from core.deps import get_current_user
from core.config import settings
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Pricing Configuration
# =============================================================================

SUBSCRIPTION_TIERS = {
    "free": {
        "name": "Free",
        "monthly_price": "0.00",
        "products_limit": 5,
        "competitors_limit": 3,
        "api_calls_limit": 100,
        "features": [
            "Basic sentiment analysis",
            "Manual pricing",
            "5 products",
        ],
    },
    "starter": {
        "name": "Starter",
        "monthly_price": "29.00",
        "products_limit": 50,
        "competitors_limit": 20,
        "api_calls_limit": 5000,
        "features": [
            "Everything in Free",
            "Auto pricing suggestions",
            "Competitor tracking",
            "Email alerts",
            "50 products",
        ],
    },
    "professional": {
        "name": "Professional",
        "monthly_price": "99.00",
        "products_limit": 500,
        "competitors_limit": 100,
        "api_calls_limit": 50000,
        "popular": True,
        "features": [
            "Everything in Starter",
            "Advanced sentiment analysis",
            "All alert types",
            "API access",
            "Priority support",
            "500 products",
        ],
    },
    "enterprise": {
        "name": "Enterprise",
        "monthly_price": "299.00",
        "products_limit": -1,  # Unlimited
        "competitors_limit": -1,
        "api_calls_limit": -1,
        "features": [
            "Everything in Professional",
            "Unlimited products",
            "Custom integrations",
            "Dedicated support",
            "SLA guarantee",
        ],
    },
}


# =============================================================================
# Schemas
# =============================================================================

class PlanResponse(BaseModel):
    """Single plan details."""
    id: str
    name: str
    monthly_price: str
    products_limit: int
    competitors_limit: int
    api_calls_limit: int
    features: List[str]
    popular: bool = False


class PlansResponse(BaseModel):
    """All available plans."""
    plans: List[PlanResponse]


class SubscriptionResponse(BaseModel):
    """Current subscription status."""
    tier: str
    name: str
    status: str
    monthly_price: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    limits: dict
    features: List[str]


class SubscribeRequest(BaseModel):
    """Request to subscribe to a plan."""
    tier: str = Field(..., pattern="^(free|starter|professional|enterprise)$")


class PaymentRequestResponse(BaseModel):
    """Payment request for subscription."""
    payment_id: str
    status: str
    tier: str
    amount: str
    currency: str = "MNEE"
    payment_address: str
    memo: str
    expires_at: datetime
    instructions: dict


class PaymentStatusResponse(BaseModel):
    """Payment status check."""
    payment_id: str
    status: str
    amount: str
    currency: str
    created_at: datetime
    confirmed_at: Optional[datetime] = None
    txid: Optional[str] = None


class PaymentHistoryItem(BaseModel):
    """Single payment in history."""
    id: str
    amount: str
    currency: str
    status: str
    description: Optional[str] = None
    created_at: datetime
    txid: Optional[str] = None


class PaymentHistoryResponse(BaseModel):
    """Payment history list."""
    payments: List[PaymentHistoryItem]
    total: int
    limit: int
    offset: int


# =============================================================================
# Routes
# =============================================================================

@router.get(
    "/plans",
    response_model=PlansResponse,
    summary="Get available plans",
    description="List all subscription plans with pricing and features"
)
async def get_plans():
    """Get all available subscription plans."""
    plans = [
        PlanResponse(
            id=tier_id,
            name=tier["name"],
            monthly_price=tier["monthly_price"],
            products_limit=tier["products_limit"],
            competitors_limit=tier["competitors_limit"],
            api_calls_limit=tier["api_calls_limit"],
            features=tier["features"],
            popular=tier.get("popular", False),
        )
        for tier_id, tier in SUBSCRIPTION_TIERS.items()
    ]
    
    return PlansResponse(plans=plans)


@router.get(
    "/subscription",
    response_model=SubscriptionResponse,
    summary="Get current subscription",
    description="Get user's current subscription status and limits"
)
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's subscription."""
    # For now, return free tier
    # TODO: Query subscription from database when models are ready
    
    tier_id = "free"  # Default to free
    tier = SUBSCRIPTION_TIERS[tier_id]
    
    return SubscriptionResponse(
        tier=tier_id,
        name=tier["name"],
        status="active",
        monthly_price=tier["monthly_price"],
        current_period_start=None,
        current_period_end=None,
        limits={
            "products": tier["products_limit"],
            "competitors": tier["competitors_limit"],
            "api_calls": tier["api_calls_limit"],
        },
        features=tier["features"],
    )


@router.post(
    "/subscribe",
    response_model=PaymentRequestResponse,
    summary="Subscribe to a plan",
    description="Create a payment request for a subscription"
)
async def subscribe(
    request: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a subscription payment request.
    
    Returns payment details including MNEE address to send payment.
    """
    tier = request.tier.lower()
    
    if tier not in SUBSCRIPTION_TIERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier. Choose from: {list(SUBSCRIPTION_TIERS.keys())}",
        )
    
    tier_config = SUBSCRIPTION_TIERS[tier]
    amount = tier_config["monthly_price"]
    
    # Free tier - just activate
    if tier == "free":
        return PaymentRequestResponse(
            payment_id=str(uuid4()),
            status="active",
            tier=tier,
            amount="0.00",
            payment_address="",
            memo="",
            expires_at=datetime.utcnow(),
            instructions={
                "message": "Free tier activated. No payment required.",
            },
        )
    
    # Get SSP's receiving wallet
    ssp_wallet = settings.SSP_MNEE_WALLET_ADDRESS
    
    if not ssp_wallet:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment system not configured. Please contact support.",
        )
    
    # Create payment request
    payment_id = str(uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=24)
    memo = f"SSP-{current_user.id}-{tier}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    # TODO: Save payment to database when models are ready
    
    logger.info(f"Payment request created: {payment_id} for user {current_user.id}")
    
    return PaymentRequestResponse(
        payment_id=payment_id,
        status="pending",
        tier=tier,
        amount=amount,
        payment_address=ssp_wallet,
        memo=memo,
        expires_at=expires_at,
        instructions={
            "step1": f"Send exactly {amount} MNEE to the payment address",
            "step2": f"Include memo: {memo}",
            "step3": "Payment confirms within minutes",
            "step4": "Subscription activates automatically",
        },
    )


@router.get(
    "/payments/{payment_id}",
    response_model=PaymentStatusResponse,
    summary="Check payment status",
    description="Check status of a pending payment"
)
async def get_payment_status(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get status of a payment."""
    # TODO: Query from database when models are ready
    
    # For now, return mock pending status
    return PaymentStatusResponse(
        payment_id=payment_id,
        status="pending",
        amount="0.00",
        currency="MNEE",
        created_at=datetime.utcnow(),
    )


@router.get(
    "/history",
    response_model=PaymentHistoryResponse,
    summary="Get payment history",
    description="List user's payment history"
)
async def get_payment_history(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user's payment history."""
    # TODO: Query from database when models are ready
    
    return PaymentHistoryResponse(
        payments=[],
        total=0,
        limit=limit,
        offset=offset,
    )
