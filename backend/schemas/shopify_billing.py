"""
Shopify Billing API Schemas

Request/response models for Shopify's appSubscriptionCreate GraphQL mutations.
These are separate from the existing MNEE payment schemas because Shopify
handles billing natively — no blockchain verification needed.

Ref: https://shopify.dev/docs/api/admin-graphql/latest/mutations/appSubscriptionCreate
"""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# SHOPIFY PLAN DEFINITIONS
# =============================================================================

class ShopifyPlanConfig(BaseModel):
    """
    Internal plan configuration mapping our tiers to Shopify billing params.
    Not exposed via API — used by ShopifyBillingService.
    """
    tier: str
    name: str
    price_amount: str  # Decimal string: "49.00"
    currency_code: str = "USD"
    interval: Literal["EVERY_30_DAYS", "ANNUAL"] = "EVERY_30_DAYS"
    trial_days: int = 14
    product_limit: int = 50
    features: List[str] = []


# Shopify-specific pricing tiers (replaces MNEE tiers for Shopify merchants)
SHOPIFY_PLANS: dict[str, ShopifyPlanConfig] = {
    "starter": ShopifyPlanConfig(
        tier="starter",
        name="ActualPrice Starter",
        price_amount="49.00",
        trial_days=14,
        product_limit=50,
        features=[
            "Up to 50 products",
            "Competitor price tracking",
            "Basic sentiment analysis",
            "Daily pricing recommendations",
            "Email alerts",
        ],
    ),
    "professional": ShopifyPlanConfig(
        tier="professional",
        name="ActualPrice Professional",
        price_amount="149.00",
        trial_days=14,
        product_limit=500,
        features=[
            "Up to 500 products",
            "Real-time competitor tracking",
            "Advanced sentiment + crisis detection",
            "Hourly pricing recommendations",
            "Slack & email alerts",
            "API access",
        ],
    ),
    "enterprise": ShopifyPlanConfig(
        tier="enterprise",
        name="ActualPrice Enterprise",
        price_amount="499.00",
        trial_days=14,
        product_limit=-1,  # Unlimited
        features=[
            "Unlimited products",
            "Real-time everything",
            "Multi-store support",
            "Custom integrations",
            "Dedicated support",
            "SLA guarantee",
        ],
    ),
}


# =============================================================================
# API REQUEST SCHEMAS
# =============================================================================

class ShopifySubscribeRequest(BaseModel):
    """Request to create a Shopify billing subscription."""
    tier: Literal["starter", "professional", "enterprise"] = Field(
        ..., description="Plan tier: starter ($49), professional ($149), enterprise ($499)"
    )
    shop_domain: Optional[str] = Field(
        default=None,
        description="Shop domain (auto-detected from integration if not provided)",
    )


class ShopifyPlanChangeRequest(BaseModel):
    """Request to upgrade or downgrade a Shopify plan."""
    new_tier: Literal["starter", "professional", "enterprise"] = Field(
        ..., description="New plan tier to switch to"
    )
    shop_domain: Optional[str] = Field(
        default=None,
        description="Shop domain (auto-detected from integration if not provided)",
    )


class ShopifyCancelRequest(BaseModel):
    """Request to cancel a Shopify subscription."""
    prorate: bool = Field(
        default=True,
        description="Issue prorated credit for unused portion of billing cycle",
    )
    shop_domain: Optional[str] = Field(
        default=None,
        description="Shop domain (auto-detected from integration if not provided)",
    )


# =============================================================================
# API RESPONSE SCHEMAS
# =============================================================================

class ShopifySubscribeResponse(BaseModel):
    """Response after creating a Shopify billing subscription."""
    success: bool
    confirmation_url: Optional[str] = None
    shopify_subscription_id: Optional[str] = None
    tier: str
    message: str


class ShopifyBillingCallbackResponse(BaseModel):
    """Response after Shopify billing callback (merchant approved/declined)."""
    success: bool
    status: str  # "active", "declined", "expired", "pending"
    tier: Optional[str] = None
    message: str


class ShopifyBillingStatusResponse(BaseModel):
    """Current Shopify billing status for a merchant."""
    has_active_subscription: bool
    tier: Optional[str] = None
    plan_name: Optional[str] = None
    status: Optional[str] = None
    shopify_subscription_id: Optional[str] = None
    trial_days: Optional[int] = None
    current_period_end: Optional[str] = None
    test: bool = False
    price: Optional[str] = None
    currency: Optional[str] = None


class ShopifyCancelResponse(BaseModel):
    """Response after cancelling a Shopify subscription."""
    success: bool
    message: str
    status: Optional[str] = None


class ShopifyPlanInfo(BaseModel):
    """Plan info for frontend display."""
    tier: str
    name: str
    price_monthly: float
    trial_days: int
    product_limit: int
    features: List[str]


class ShopifyPlansListResponse(BaseModel):
    """All available Shopify plans."""
    plans: List[ShopifyPlanInfo]


    