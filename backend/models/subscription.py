"""
Subscription Model

Tracks user subscription tiers, billing periods, and limits.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from enum import Enum

from sqlmodel import SQLModel, Field


class SubscriptionTier(str, Enum):
    """Available subscription tiers."""
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    TRIALING = "trialing"


# =============================================================================
# Subscription Model
# =============================================================================

class SubscriptionBase(SQLModel):
    """Base subscription fields."""
    
    # Plan info
    tier: SubscriptionTier = Field(default=SubscriptionTier.FREE)
    status: SubscriptionStatus = Field(default=SubscriptionStatus.ACTIVE)
    
    # Pricing
    monthly_price: str = Field(default="0.00", max_length=20)
    
    # Billing period
    current_period_start: Optional[datetime] = Field(default=None)
    current_period_end: Optional[datetime] = Field(default=None)
    
    # Cancellation
    cancelled_at: Optional[datetime] = Field(default=None)
    cancel_at_period_end: bool = Field(default=False)


class Subscription(SubscriptionBase, table=True):
    """User subscription record."""
    
    __tablename__ = "subscriptions"
    
    # Primary key
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    # One subscription per user
    user_id: UUID = Field(foreign_key="users.id", unique=True, index=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Pydantic Schemas for API
# =============================================================================

class SubscriptionCreate(SQLModel):
    """Schema for creating a subscription."""
    tier: SubscriptionTier = SubscriptionTier.FREE


class SubscriptionUpdate(SQLModel):
    """Schema for updating a subscription."""
    tier: Optional[SubscriptionTier] = None
    status: Optional[SubscriptionStatus] = None
    cancel_at_period_end: Optional[bool] = None


class SubscriptionResponse(SubscriptionBase):
    """Schema for subscription API response."""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# =============================================================================
# Tier Configuration
# =============================================================================

TIER_LIMITS = {
    SubscriptionTier.FREE: {
        "products": 5,
        "competitors": 3,
        "api_calls": 100,
        "price": "0.00",
    },
    SubscriptionTier.STARTER: {
        "products": 50,
        "competitors": 20,
        "api_calls": 5000,
        "price": "29.00",
    },
    SubscriptionTier.PROFESSIONAL: {
        "products": 500,
        "competitors": 100,
        "api_calls": 50000,
        "price": "99.00",
    },
    SubscriptionTier.ENTERPRISE: {
        "products": -1,  # Unlimited
        "competitors": -1,
        "api_calls": -1,
        "price": "299.00",
    },
}


def get_tier_limits(tier: SubscriptionTier) -> dict:
    """Get limits for a subscription tier."""
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])


def get_tier_price(tier: SubscriptionTier) -> str:
    """Get monthly price for a tier."""
    limits = get_tier_limits(tier)
    return limits["price"]
