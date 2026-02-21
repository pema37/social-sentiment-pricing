"""
Shopify Billing API Routes

Endpoints for Shopify-native billing via the Billing API.
These are separate from the MNEE payment routes and only apply
to merchants who installed via the Shopify App Store.

Endpoints:
  POST /shopify/billing/subscribe     — Create subscription, get confirmationUrl
  GET  /shopify/billing/callback      — Shopify redirects here after approval
  GET  /shopify/billing/status        — Check current billing status
  POST /shopify/billing/change-plan   — Upgrade/downgrade (creates new subscription)
  POST /shopify/billing/cancel        — Cancel active subscription
  GET  /shopify/billing/plans         — List available Shopify plans
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.deps import get_current_user
from db.session import get_session
from models.user import User
from services.integration.shopify_billing import ShopifyBillingService
from schemas.shopify_billing import (
    SHOPIFY_PLANS,
    ShopifySubscribeRequest,
    ShopifySubscribeResponse,
    ShopifyBillingCallbackResponse,
    ShopifyBillingStatusResponse,
    ShopifyPlanChangeRequest,
    ShopifyCancelRequest,
    ShopifyCancelResponse,
    ShopifyPlanInfo,
    ShopifyPlansListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shopify/billing", tags=["shopify-billing"])


# =============================================================================
# DEPENDENCY
# =============================================================================

def get_billing_service(
    session: AsyncSession = Depends(get_session),
) -> ShopifyBillingService:
    """Dependency injection for Shopify billing service."""
    return ShopifyBillingService(session)


# =============================================================================
# LIST PLANS
# =============================================================================

@router.get("/plans", response_model=ShopifyPlansListResponse)
async def list_shopify_plans():
    """
    List all available Shopify billing plans.
    No authentication required — used by the embedded app for plan display.
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
# CREATE SUBSCRIPTION
# =============================================================================

@router.post("/subscribe", response_model=ShopifySubscribeResponse)
async def create_shopify_subscription(
    data: ShopifySubscribeRequest,
    current_user: User = Depends(get_current_user),
    service: ShopifyBillingService = Depends(get_billing_service),
):
    """
    Create a Shopify recurring subscription.

    Returns a confirmationUrl — redirect the merchant there to approve the charge.
    After approval, Shopify redirects to /shopify/billing/callback with charge_id.
    """
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


# =============================================================================
# BILLING CALLBACK (Shopify redirects here after merchant approves/declines)
# =============================================================================

@router.get("/callback")
async def shopify_billing_callback(
    charge_id: str = Query(..., description="Shopify charge ID from redirect"),
    shop: str = Query(None, description="Shop domain"),
    session: AsyncSession = Depends(get_session),
):
    """
    Shopify billing callback — merchant was redirected here after approving
    or declining the charge.

    Shopify appends ?charge_id=<numeric_id> to our returnUrl.
    We verify the subscription status and activate if ACTIVE.

    Then redirect the merchant back into the app.
    """
    service = ShopifyBillingService(session)

    is_active, tier, shopify_sub_id = await service.verify_subscription(
        charge_id=charge_id,
        shop_domain=shop or "",
    )

    if is_active:
        logger.info(
            f"Billing approved for {shop}: tier={tier}, charge_id={charge_id}"
        )
        # Redirect back to the app billing page with success
        redirect_url = (
            f"{settings.FRONTEND_URL}/settings/billing"
            f"?billing=approved&tier={tier or 'starter'}&shop={shop or ''}"
        )
    else:
        logger.warning(
            f"Billing not approved for {shop}: charge_id={charge_id}"
        )
        # Redirect back with declined status
        redirect_url = (
            f"{settings.FRONTEND_URL}/settings/billing"
            f"?billing=declined&shop={shop or ''}"
        )

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


# =============================================================================
# CHECK BILLING STATUS
# =============================================================================

@router.get("/status", response_model=ShopifyBillingStatusResponse)
async def get_shopify_billing_status(
    shop_domain: str = Query(None, description="Shop domain (optional)"),
    current_user: User = Depends(get_current_user),
    service: ShopifyBillingService = Depends(get_billing_service),
):
    """
    Check the current Shopify billing status.
    Queries Shopify's activeSubscriptions to get authoritative status.
    """
    return await service.get_subscription_status(
        user_id=current_user.id,
        shop_domain=shop_domain,
    )


# =============================================================================
# CHANGE PLAN (Upgrade / Downgrade)
# =============================================================================

@router.post("/change-plan", response_model=ShopifySubscribeResponse)
async def change_shopify_plan(
    data: ShopifyPlanChangeRequest,
    current_user: User = Depends(get_current_user),
    service: ShopifyBillingService = Depends(get_billing_service),
):
    """
    Upgrade or downgrade the Shopify plan.

    Creates a new subscription with APPLY_IMMEDIATELY replacement behavior.
    Shopify automatically cancels the old subscription and prorates the charge.
    Returns a new confirmationUrl for the merchant to approve.
    """
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


# =============================================================================
# CANCEL SUBSCRIPTION
# =============================================================================

@router.post("/cancel", response_model=ShopifyCancelResponse)
async def cancel_shopify_subscription(
    data: ShopifyCancelRequest,
    current_user: User = Depends(get_current_user),
    service: ShopifyBillingService = Depends(get_billing_service),
):
    """
    Cancel the active Shopify subscription.
    Optionally prorates the remaining billing period.
    Downgrades the local subscription to free.
    """
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


