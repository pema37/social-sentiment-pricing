"""
Shopify Billing API Routes

Endpoints for Shopify-native app subscription billing.
Separate from MNEE payment routes — these handle Shopify App Store billing.

Flow:
  1. GET  /plans         → list available plans (public)
  2. POST /subscribe     → create subscription → returns confirmationUrl
  3. [Merchant approves on Shopify → redirected back to frontend with charge_id]
  4. POST /verify        → frontend calls this with charge_id to confirm activation
  5. GET  /status        → check active billing status
  6. POST /change-plan   → upgrade/downgrade
  7. POST /cancel        → cancel subscription
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.deps import get_current_user
from core.rate_limit import READ_RATE_LIMIT, WRITE_RATE_LIMIT, limiter
from db.session import get_session
from models.user import User
from schemas.shopify_billing import (
    SHOPIFY_PLANS,
    ShopifyBillingCallbackResponse,
    ShopifyBillingStatusResponse,
    ShopifyCancelRequest,
    ShopifyCancelResponse,
    ShopifyPlanChangeRequest,
    ShopifyPlanInfo,
    ShopifyPlansListResponse,
    ShopifySubscribeRequest,
    ShopifySubscribeResponse,
)
from services.integration.shopify_billing import ShopifyBillingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shopify/billing", tags=["shopify-billing"])


# =============================================================================
# Verify Request Schema (inline — only used by this route)
# =============================================================================


class ShopifyVerifyRequest(BaseModel):
    """Request to verify a charge after Shopify approval redirect."""

    charge_id: str = Field(..., description="Numeric charge ID from Shopify callback URL")
    shop_domain: str | None = Field(
        default=None,
        description="Shop domain (auto-detected if not provided)",
    )


# =============================================================================
# PUBLIC ENDPOINTS (no auth required)
# =============================================================================


@router.get("/plans", response_model=ShopifyPlansListResponse)
async def list_shopify_plans():
    """
    List available Shopify billing plans.

    No auth required — this can be called from the embedded app
    before the merchant has logged in, to display pricing.
    """
    plans = [
        ShopifyPlanInfo(
            tier=plan.tier,
            name=plan.name,
            price_monthly=float(plan.price_amount),
            trial_days=plan.trial_days,
            product_limit=plan.product_limit,
            features=plan.features,
        )
        for plan in SHOPIFY_PLANS.values()
    ]
    return ShopifyPlansListResponse(plans=plans)


# =============================================================================
# AUTHENTICATED ENDPOINTS
# =============================================================================


@router.post("/subscribe", response_model=ShopifySubscribeResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def create_shopify_subscription(
    request: Request,
    data: ShopifySubscribeRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Create a Shopify recurring subscription.

    Returns a confirmation_url to redirect the merchant to Shopify's
    billing approval page. After approval, Shopify redirects back to
    the frontend with a charge_id param.
    """
    service = ShopifyBillingService(db)
    result = await service.create_subscription(
        tier=data.tier,
        user_id=current_user.id,
        shop_domain=data.shop_domain,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message,
        )

    return result


@router.post("/verify", response_model=ShopifyBillingCallbackResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def verify_shopify_charge(
    request: Request,
    data: ShopifyVerifyRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Verify a Shopify charge after the merchant approves it.

    Called by the frontend when the billing page loads with a charge_id
    query param (Shopify redirects back to the app URL after approval).
    Confirms the subscription is ACTIVE via GraphQL and updates
    the local Subscription record.
    """
    shop_domain = data.shop_domain
    service = ShopifyBillingService(db)

    # If no shop_domain provided, find it from the user's integration
    if not shop_domain:
        integration = await service._get_shopify_integration(user_id=current_user.id)
        if integration:
            shop_domain = integration.store_url

    if not shop_domain:
        return ShopifyBillingCallbackResponse(
            success=False,
            status="error",
            message="No shop domain found. Please provide shop_domain.",
        )

    is_active, tier, _gid = await service.verify_subscription(
        charge_id=data.charge_id,
        shop_domain=shop_domain,
    )

    if is_active:
        return ShopifyBillingCallbackResponse(
            success=True,
            status="active",
            tier=tier,
            message=f"Subscription activated: {tier} plan",
        )
    else:
        return ShopifyBillingCallbackResponse(
            success=False,
            status="declined",
            tier=tier,
            message="Subscription was not approved or is not yet active.",
        )


@router.get("/callback")
async def shopify_billing_callback(
    charge_id: str,
    shop: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    """
    Legacy billing callback (GET redirect).

    For embedded apps, Shopify redirects to the app URL (frontend) instead
    of this endpoint. This is a fallback that forwards to the frontend.
    """
    redirect_url = f"{settings.FRONTEND_URL}/settings/billing?charge_id={charge_id}"
    if shop:
        redirect_url += f"&shop={shop}"

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@router.get("/status", response_model=ShopifyBillingStatusResponse)
@limiter.limit(READ_RATE_LIMIT)
async def get_shopify_billing_status(
    request: Request,
    shop_domain: str | None = None,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Check the current Shopify billing status.

    Queries Shopify's activeSubscriptions for the authoritative
    subscription state (not our local DB copy).
    """
    service = ShopifyBillingService(db)
    return await service.get_subscription_status(
        user_id=current_user.id,
        shop_domain=shop_domain,
    )


@router.post("/change-plan", response_model=ShopifySubscribeResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def change_shopify_plan(
    request: Request,
    data: ShopifyPlanChangeRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Change Shopify plan (upgrade or downgrade).

    Creates a new subscription with APPLY_IMMEDIATELY replacement
    behavior. Merchant must approve the new charge via Shopify.
    """
    service = ShopifyBillingService(db)
    result = await service.create_subscription(
        tier=data.new_tier,
        user_id=current_user.id,
        shop_domain=data.shop_domain,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message,
        )

    return result


@router.post("/cancel", response_model=ShopifyCancelResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def cancel_shopify_subscription(
    request: Request,
    data: ShopifyCancelRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel the active Shopify subscription.

    Calls Shopify's appSubscriptionCancel mutation and downgrades
    the local subscription to free tier.
    """
    service = ShopifyBillingService(db)
    result = await service.cancel_subscription(
        prorate=data.prorate,
        user_id=current_user.id,
        shop_domain=data.shop_domain,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.message,
        )

    return result
