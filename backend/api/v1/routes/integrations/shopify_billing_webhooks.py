# backend/api/v1/routes/integrations/shopify_billing_webhooks.py
"""
Shopify Billing Webhooks

Handles Shopify-initiated subscription state changes.

Without this handler, a Shopify-side cancellation (payment failure,
merchant cancels from Shopify Admin, app uninstall) never reaches our
backend — the local Subscription record stays 'active' on a paid tier
indefinitely.

Topics handled:
  - app/subscriptions_update  → sync subscription status to local DB
  - app/uninstalled           → mark integration DISCONNECTED, downgrade to free

Registration:
  Add these topics to ShopifyService.WEBHOOK_TOPICS_GQL in shopify_service.py:
    "APP_SUBSCRIPTIONS_UPDATE"
    "APP_UNINSTALLED"

  And to WEBHOOK_TOPICS (REST-style names, used for logging):
    "app/subscriptions_update"
    "app/uninstalled"

Verification:
  Uses the same _verify_webhook() pattern as shopify_gdpr.py —
  HMAC-SHA256 with SHOPIFY_CLIENT_SECRET, must return 200 within 5s.
"""

import base64
import hashlib
import hmac as hmac_lib
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import settings
from db.session import get_session
from models.integration import EcommercePlatform, Integration, IntegrationStatus
from models.subscription import Subscription

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shopify/billing", tags=["shopify-billing-webhooks"])


# =============================================================================
# HMAC Verification (same pattern as shopify_gdpr.py)
# =============================================================================


def _verify_shopify_hmac(payload: bytes, hmac_header: str, secret: str) -> bool:
    """Verify Shopify webhook HMAC-SHA256 signature."""
    if not hmac_header or not secret:
        return False
    computed = base64.b64encode(hmac_lib.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()).decode("utf-8")
    return hmac_lib.compare_digest(computed, hmac_header)


async def _verify_webhook(request: Request, hmac_sha256: str | None) -> bytes:
    """Read body and verify HMAC. Raises 401 on failure."""
    body = await request.body()

    secret = settings.SHOPIFY_CLIENT_SECRET
    if not secret:
        logger.error("SHOPIFY_CLIENT_SECRET not configured — cannot verify billing webhook")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook verification not configured",
        )

    if not hmac_sha256:
        logger.warning(f"Missing HMAC header on billing webhook from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing HMAC signature",
        )

    if not _verify_shopify_hmac(body, hmac_sha256, secret):
        logger.warning(f"Invalid HMAC on billing webhook from {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature",
        )

    return body


# =============================================================================
# HELPERS
# =============================================================================


async def _get_integration_by_shop(db: AsyncSession, shop_domain: str) -> Integration | None:
    """Find a Shopify integration by shop domain regardless of status."""
    stmt = select(Integration).where(
        Integration.platform == EcommercePlatform.SHOPIFY,
        Integration.store_url == shop_domain,
    )
    result = await db.execute(stmt)
    return result.scalars().first()


async def _downgrade_subscription(db: AsyncSession, user_id) -> None:
    """Downgrade a user's local subscription to free."""
    result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
    subscription = result.scalar_one_or_none()

    now = datetime.now(UTC)

    if subscription:
        subscription.tier = "free"
        subscription.status = "active"
        subscription.monthly_price = "0.00"
        subscription.shopify_charge_id = None
        subscription.shopify_plan_name = None
        subscription.cancelled_at = now
        subscription.updated_at = now
        db.add(subscription)
    else:
        # No subscription record — create a free one so the user
        # never ends up in an undefined billing state
        subscription = Subscription(
            user_id=user_id,
            tier="free",
            status="active",
            monthly_price="0.00",
        )
        db.add(subscription)


# =============================================================================
# WEBHOOK: app/subscriptions_update
# =============================================================================


@router.post("/webhook/subscriptions-update", status_code=200)
async def handle_subscription_update(
    request: Request,
    db: AsyncSession = Depends(get_session),
    x_shopify_hmac_sha256: str | None = Header(None, alias="X-Shopify-Hmac-Sha256"),
    x_shopify_shop_domain: str | None = Header(None, alias="X-Shopify-Shop-Domain"),
):
    """
    Handle APP_SUBSCRIPTIONS_UPDATE webhook from Shopify.

    Fired when a subscription status changes on Shopify's side:
      - ACTIVE      → merchant approved a new subscription
      - CANCELLED   → merchant cancelled from Shopify Admin
      - DECLINED    → payment failed or charge rejected
      - EXPIRED     → trial ended without approval
      - FROZEN      → store payment on hold (Shopify paused the store)
      - PENDING     → charge created, awaiting approval

    Shopify requires a 200 response within 5 seconds — all DB work
    must be fast. No external API calls here.

    Payload shape (relevant fields):
      {
        "app_subscription": {
          "admin_graphql_api_id": "gid://shopify/AppSubscription/123",
          "name": "Professional",
          "status": "CANCELLED",
          "test": false,
          "created_at": "...",
          "updated_at": "..."
        }
      }
    """
    body = await _verify_webhook(request, x_shopify_hmac_sha256)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in subscriptions_update webhook")
        # Still return 200 — Shopify will retry on non-2xx responses
        return {"status": "acknowledged", "message": "Invalid payload"}

    shop_domain = x_shopify_shop_domain
    app_sub = payload.get("app_subscription", {})
    shopify_sub_id = app_sub.get("admin_graphql_api_id", "")
    new_status = app_sub.get("status", "").upper()
    plan_name = app_sub.get("name", "")

    logger.info(f"Billing webhook: subscriptions_update shop={shop_domain} status={new_status} plan={plan_name}")

    if not shop_domain:
        logger.warning("subscriptions_update webhook missing X-Shopify-Shop-Domain")
        return {"status": "acknowledged", "message": "No shop domain"}

    integration = await _get_integration_by_shop(db, shop_domain)
    if not integration:
        logger.warning(f"subscriptions_update: no integration found for {shop_domain}")
        return {"status": "acknowledged", "message": "Integration not found"}

    user_id = integration.user_id
    now = datetime.now(UTC)

    # ── Statuses that mean billing is active ──────────────────────────────
    if new_status == "ACTIVE":
        # Subscription is active — make sure local DB reflects this.
        # The /verify endpoint handles full activation after merchant approval,
        # but this webhook is the safety net for cases where the verify call
        # was missed (e.g., browser closed before redirect completed).
        if integration.user_id:
            result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalar_one_or_none()

            if subscription and subscription.status != "active":
                subscription.status = "active"
                subscription.updated_at = now
                db.add(subscription)
                logger.info(
                    f"Billing webhook: re-activated subscription for user {user_id} "
                    f"via webhook (verify endpoint may have been missed)"
                )

    # ── Statuses that mean billing ended ─────────────────────────────────
    elif new_status in ("CANCELLED", "DECLINED", "EXPIRED"):
        if user_id:
            await _downgrade_subscription(db, user_id)
            logger.info(
                f"Billing webhook: downgraded user {user_id} to free (Shopify status={new_status}, shop={shop_domain})"
            )

    # ── FROZEN — store's own billing is paused by Shopify ─────────────────
    elif new_status == "FROZEN":
        # Store is frozen — don't downgrade yet, but mark locally so we
        # know not to push prices or run syncs for this store.
        # Shopify will send ACTIVE or CANCELLED when resolved.
        if user_id:
            result = await db.execute(select(Subscription).where(Subscription.user_id == user_id))
            subscription = result.scalar_one_or_none()
            if subscription:
                subscription.status = "frozen"
                subscription.updated_at = now
                db.add(subscription)
                logger.info(f"Billing webhook: subscription frozen for user {user_id} (shop={shop_domain})")

    # ── PENDING — charge created, waiting for approval ────────────────────
    # No local action needed — /subscribe already set pending state.
    else:
        logger.info(f"Billing webhook: unhandled status {new_status} for {shop_domain} — no action")

    await db.commit()

    return {"status": "acknowledged"}


# =============================================================================
# WEBHOOK: app/uninstalled
# =============================================================================


@router.post("/webhook/app-uninstalled", status_code=200)
async def handle_app_uninstalled(
    request: Request,
    db: AsyncSession = Depends(get_session),
    x_shopify_hmac_sha256: str | None = Header(None, alias="X-Shopify-Hmac-Sha256"),
    x_shopify_shop_domain: str | None = Header(None, alias="X-Shopify-Shop-Domain"),
):
    """
    Handle APP_UNINSTALLED webhook from Shopify.

    Fired immediately when a merchant uninstalls the app.

    Actions:
      1. Mark integration as DISCONNECTED
      2. Downgrade local subscription to free
      3. Clear the stored access token (token is now invalid)

    Note: Full data deletion (GDPR shop/redact) fires 48 hours later
    and is handled in shopify_gdpr.py.

    Payload shape:
      {
        "id": 12345678,
        "myshopify_domain": "cool-store.myshopify.com",
        ...
      }
    """
    body = await _verify_webhook(request, x_shopify_hmac_sha256)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in app/uninstalled webhook")
        return {"status": "acknowledged", "message": "Invalid payload"}

    shop_domain = x_shopify_shop_domain or payload.get("myshopify_domain") or payload.get("domain")

    logger.info(f"Billing webhook: app/uninstalled for shop={shop_domain}")

    if not shop_domain:
        logger.warning("app/uninstalled webhook — could not determine shop domain")
        return {"status": "acknowledged", "message": "No shop domain"}

    integration = await _get_integration_by_shop(db, shop_domain)
    if not integration:
        logger.info(f"app/uninstalled: no integration found for {shop_domain} — already removed")
        return {"status": "acknowledged"}

    now = datetime.now(UTC)

    # Mark integration disconnected and invalidate the token
    integration.status = IntegrationStatus.DISCONNECTED
    integration.error_message = "App was uninstalled by the merchant."
    integration.access_token_encrypted = b"revoked"
    integration.updated_at = now
    db.add(integration)

    # Downgrade subscription
    if integration.user_id:
        await _downgrade_subscription(db, integration.user_id)
        logger.info(
            f"app/uninstalled: downgraded user {integration.user_id} to free "
            f"and marked integration DISCONNECTED (shop={shop_domain})"
        )

    await db.commit()

    return {"status": "acknowledged"}
