"""
Subscription Model
Tracks user subscription tiers, billing periods, and limits.

UPDATED (2026-02-20): Added shopify_charge_id and shopify_plan_name
for Shopify Billing API integration. These fields are nullable —
only populated for merchants who subscribe via Shopify App Store.
MNEE subscribers continue using the existing flow without these fields.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String
from sqlmodel import Field, SQLModel


class SubscriptionTier(StrEnum):
    """Available subscription tiers."""

    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(StrEnum):
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

    # Plan info - use str instead of Enum to avoid PostgreSQL enum issues
    tier: str = Field(default="free", max_length=20)
    status: str = Field(default="active", max_length=20)

    # Pricing
    monthly_price: str = Field(default="0.00", max_length=20)

    # Billing period
    current_period_start: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    current_period_end: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    # Cancellation
    cancelled_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    cancel_at_period_end: bool = Field(default=False)

    # ========== Shopify Billing API Fields (2026-02-20) ==========
    # Only populated for merchants who subscribe via Shopify App Store.
    # Null for MNEE/standalone subscribers.
    shopify_charge_id: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
        description="Shopify AppSubscription GID (e.g. gid://shopify/AppSubscription/12345)",
    )
    shopify_plan_name: str | None = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
        description="Shopify plan display name (e.g. 'ActualPrice Professional')",
    )


class Subscription(SubscriptionBase, table=True):
    """User subscription record."""

    __tablename__ = "subscriptions"

    # Primary key
    id: UUID = Field(default_factory=uuid4, primary_key=True)

    # One subscription per user
    user_id: UUID = Field(foreign_key="users.id", unique=True, index=True)

    # Timestamps
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )


# =============================================================================
# Pydantic Schemas for API
# =============================================================================


class SubscriptionCreate(SQLModel):
    """Schema for creating a subscription."""

    tier: str = "free"


class SubscriptionUpdate(SQLModel):
    """Schema for updating a subscription."""

    tier: str | None = None
    status: str | None = None
    cancel_at_period_end: bool | None = None


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


# String-based tier limits for when we use str instead of Enum
TIER_LIMITS_STR = {
    "free": TIER_LIMITS[SubscriptionTier.FREE],
    "starter": TIER_LIMITS[SubscriptionTier.STARTER],
    "professional": TIER_LIMITS[SubscriptionTier.PROFESSIONAL],
    "enterprise": TIER_LIMITS[SubscriptionTier.ENTERPRISE],
}


def get_tier_limits(tier) -> dict:
    """Get limits for a subscription tier."""
    if isinstance(tier, SubscriptionTier):
        return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])
    return TIER_LIMITS_STR.get(tier, TIER_LIMITS_STR["free"])


def get_tier_price(tier) -> str:
    """Get monthly price for a tier."""
    limits = get_tier_limits(tier)
    return limits["price"]
