"""
Payment Schemas

All request/response models for payment endpoints.
Separated from routes for maintainability and reusability.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# =============================================================================
# PLAN SCHEMAS
# =============================================================================


class PlanInfo(BaseModel):
    """Subscription plan information."""

    tier: str
    name: str
    price_monthly: float
    price_yearly: float
    product_limit: int
    features: list[str]


class PlanListResponse(BaseModel):
    """List of available plans."""

    plans: list[PlanInfo]


# =============================================================================
# SUBSCRIPTION SCHEMAS
# =============================================================================


class SubscriptionInfo(BaseModel):
    """Current subscription information."""

    tier: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    product_limit: int
    products_used: int = 0


class SubscribeRequest(BaseModel):
    """Request to subscribe to a plan."""

    tier: str = Field(..., description="Subscription tier: starter, professional, enterprise")
    billing_cycle: str = Field(default="monthly", description="Billing cycle: monthly or yearly")
    network: Literal["ethereum", "bsv"] = Field(default="bsv", description="Payment network: ethereum or bsv")


# =============================================================================
# PAYMENT SCHEMAS
# =============================================================================


class PaymentRequest(BaseModel):
    """Payment request details returned after initiating subscription."""

    payment_id: str
    amount: str
    amount_raw: int
    currency: str = "MNEE"
    recipient_address: str
    memo: str
    expires_at: datetime
    network: str = "bsv"  # NEW: Which network this payment is for
    network_options: list[str] = ["bsv", "ethereum"]


class PaymentInfo(BaseModel):
    """Payment information for display."""

    id: str
    amount: str
    status: str
    payment_type: str
    created_at: datetime
    transaction_hash: str | None = None
    network: str | None = None


class PaymentHistoryResponse(BaseModel):
    """Paginated payment history."""

    payments: list[PaymentInfo]
    total: int
    limit: int
    offset: int


# =============================================================================
# PAYMENT CONFIRMATION SCHEMAS
# =============================================================================


class ConfirmPaymentRequest(BaseModel):
    """Request to confirm a payment with transaction details."""

    transaction_hash: str = Field(..., description="Blockchain transaction hash/ID")
    network: str = Field(default="bsv", description="Network: bsv or ethereum")
    from_address: str | None = Field(default=None, description="Sender wallet address")


class ConfirmPaymentResponse(BaseModel):
    """Response after confirming payment."""

    success: bool
    message: str
    payment_id: str | None = None
    payment_status: str | None = None
    subscription_tier: str | None = None
    subscription_status: str | None = None
    verified_on_chain: bool = False


# =============================================================================
# BLOCKCHAIN VERIFICATION SCHEMAS
# =============================================================================


class TransactionVerification(BaseModel):
    """Result of blockchain transaction verification."""

    verified: bool
    transaction_hash: str
    network: str
    amount: str | None = None
    amount_raw: int | None = None
    from_address: str | None = None
    to_address: str | None = None
    memo: str | None = None
    confirmations: int = 0
    block_height: int | None = None
    timestamp: datetime | None = None
    error: str | None = None


# =============================================================================
# ERROR SCHEMAS
# =============================================================================


class PaymentError(BaseModel):
    """Payment error response."""

    error: str
    code: str
    details: dict | None = None
