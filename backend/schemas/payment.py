"""
Payment Schemas

All request/response models for payment endpoints.
Separated from routes for maintainability and reusability.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

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
    features: List[str]


class PlanListResponse(BaseModel):
    """List of available plans."""
    plans: List[PlanInfo]


# =============================================================================
# SUBSCRIPTION SCHEMAS
# =============================================================================

class SubscriptionInfo(BaseModel):
    """Current subscription information."""
    tier: str
    status: str
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    product_limit: int
    products_used: int = 0


class SubscribeRequest(BaseModel):
    """Request to subscribe to a plan."""
    tier: str = Field(..., description="Subscription tier: starter, professional, enterprise")
    billing_cycle: str = Field(default="monthly", description="Billing cycle: monthly or yearly")


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
    network_options: List[str] = ["bsv", "ethereum"]


class PaymentInfo(BaseModel):
    """Payment information for display."""
    id: str
    amount: str
    status: str
    payment_type: str
    created_at: datetime
    transaction_hash: Optional[str] = None
    network: Optional[str] = None


class PaymentHistoryResponse(BaseModel):
    """Paginated payment history."""
    payments: List[PaymentInfo]
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
    from_address: Optional[str] = Field(default=None, description="Sender wallet address")


class ConfirmPaymentResponse(BaseModel):
    """Response after confirming payment."""
    success: bool
    message: str
    payment_id: Optional[str] = None
    payment_status: Optional[str] = None
    subscription_tier: Optional[str] = None
    subscription_status: Optional[str] = None
    verified_on_chain: bool = False


# =============================================================================
# BLOCKCHAIN VERIFICATION SCHEMAS
# =============================================================================

class TransactionVerification(BaseModel):
    """Result of blockchain transaction verification."""
    verified: bool
    transaction_hash: str
    network: str
    amount: Optional[str] = None
    amount_raw: Optional[int] = None
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    memo: Optional[str] = None
    confirmations: int = 0
    block_height: Optional[int] = None
    timestamp: Optional[datetime] = None
    error: Optional[str] = None


# =============================================================================
# ERROR SCHEMAS
# =============================================================================

class PaymentError(BaseModel):
    """Payment error response."""
    error: str
    code: str
    details: Optional[dict] = None

