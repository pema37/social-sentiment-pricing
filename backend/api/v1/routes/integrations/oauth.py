# backend/api/v1/routes/integrations/oauth.py
"""OAuth flow and WooCommerce API key connection endpoints.

UPDATED (2026-02-20): After successful Shopify OAuth, redirect to billing
plan selection instead of straight to dashboard. This ensures new installs
are prompted to pick a paid plan (Shopify App Store compliance requirement).

FIXED (2026-03-08): Permanent install flow fix:
- Embedded installs (host param present) → billing page
- Direct installs while logged in (user_id set, no host) → integrations page
- Direct installs while logged out (user_id None) → login page with claim redirect
- Added /claim endpoint to attach orphaned integrations to authenticated users

FIXED (2026-03-13): init_oauth now allows reconnect from ERROR state.
Previously only DISCONNECTED was allowed past the "already connected" guard.
A revoked token leaves status=ERROR in the DB (via the health check fix),
so the reconnect CTA must be able to re-initiate OAuth from ERROR state.
"""

import logging
import secrets
from datetime import UTC, datetime
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import settings
from core.deps import get_current_user
from core.encryption import encrypt_token
from core.rate_limit import WRITE_RATE_LIMIT, limiter
from db.session import get_session
from models.integration import EcommercePlatform, Integration, IntegrationStatus
from models.user import User
from schemas.integration import (
    IntegrationResponse,
    OAuthInitRequest,
    OAuthInitResponse,
    WooCommerceConnectRequest,
)
from services.integration import ShopifyService, WebhookRegistrationService, WooCommerceService

logger = logging.getLogger(__name__)

router = APIRouter()

# Statuses that block a new OAuth init — only a fully ACTIVE integration
# should prevent re-connection. ERROR and DISCONNECTED must be allowed
# through so the merchant can reconnect without contacting support.
_RECONNECTABLE_STATUSES = {IntegrationStatus.DISCONNECTED, IntegrationStatus.ERROR}


def get_ecommerce_service(platform: EcommercePlatform):
    """Factory to get the right service for the platform."""
    if platform == EcommercePlatform.SHOPIFY:
        return ShopifyService()
    elif platform == EcommercePlatform.WOOCOMMERCE:
        return WooCommerceService()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {platform}",
        )


@router.post("/oauth/init", response_model=OAuthInitResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def init_oauth(
    request: Request,
    data: OAuthInitRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Start OAuth flow for connecting a store.

    Allows reconnect when the existing integration is in ERROR or
    DISCONNECTED state. Only blocks if status is ACTIVE (healthy token).
    """
    stmt = select(Integration).where(
        Integration.user_id == current_user.id,
        Integration.platform == data.platform,
        Integration.store_url == data.store_url,
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()

    # FIXED (2026-03-13): was `existing.status == IntegrationStatus.ACTIVE`
    # which blocked reconnect when token was revoked (status stays ACTIVE
    # until health check runs and writes ERROR to DB).
    # Now: only block if ACTIVE — ERROR and DISCONNECTED proceed to re-auth.
    if existing and existing.status not in _RECONNECTABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This store is already connected",
        )

    state = secrets.token_urlsafe(32)
    service = get_ecommerce_service(data.platform)
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/integrations/oauth/callback"

    auth_url = service.generate_oauth_url(
        store_url=data.store_url,
        state=state,
        redirect_uri=redirect_uri,
    )

    if existing:
        existing.oauth_state = state
        existing.status = IntegrationStatus.DISCONNECTED
        existing.error_message = None
        existing.store_url = data.store_url
        db.add(existing)
    else:
        integration = Integration(
            user_id=current_user.id,
            platform=data.platform,
            store_url=data.store_url,
            status=IntegrationStatus.DISCONNECTED,
            oauth_state=state,
            access_token_encrypted=b"pending",
        )
        db.add(integration)

    await db.commit()

    return OAuthInitResponse(authorization_url=auth_url, state=state)


@router.get("/oauth/callback")
async def oauth_callback(
    code: str,
    shop: str,
    state: str | None = None,
    hmac: str | None = None,
    host: str | None = None,
    timestamp: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    """
    OAuth callback — three install paths:

    1. Embedded App Store install (host param present):
       → billing page (Shopify compliance requirement)

    2. Direct install URL, merchant was logged in (user_id set, no host):
       → /integrations?connected=true (integration is fully linked)

    3. Direct install URL, merchant was NOT logged in (user_id=None, no host):
       → /login?redirect=/integrations/claim?integration_id=xxx
       Frontend login page redirects after auth, claim page links the integration.
    """

    integration = None

    # 1. Try state match first (most reliable — set by shopify_install.py)
    if state:
        stmt = select(Integration).where(Integration.oauth_state == state)
        result = await db.execute(stmt)
        integration = result.scalars().first()

    # 2. Fall back to shop URL lookup
    if not integration and shop:
        stmt = select(Integration).where(
            Integration.platform == EcommercePlatform.SHOPIFY,
            Integration.store_url == shop,
        )
        result = await db.execute(stmt)
        integration = result.scalars().first()

    # 3. Create stub for brand-new installs with no prior record
    if not integration:
        integration = Integration(
            platform=EcommercePlatform.SHOPIFY,
            store_url=shop,
            store_name=shop.replace(".myshopify.com", ""),
            status=IntegrationStatus.DISCONNECTED,
            access_token_encrypted=b"pending",
        )
        db.add(integration)
        await db.flush()

    service = get_ecommerce_service(integration.platform)
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/integrations/oauth/callback"

    oauth_result = await service.exchange_oauth_code(
        store_url=integration.store_url,
        code=code,
        redirect_uri=redirect_uri,
    )

    if not oauth_result.success:
        integration.status = IntegrationStatus.ERROR
        integration.error_message = oauth_result.error
        integration.oauth_state = None
        db.add(integration)
        await db.commit()

        error_url = (
            f"{settings.FRONTEND_URL}/integrations"
            f"?error=oauth_failed&message={quote(oauth_result.error)}"
            f"&platform={integration.platform.value}"
        )
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

    # OAuth succeeded — store token and activate
    integration.access_token_encrypted = encrypt_token(oauth_result.access_token)
    if oauth_result.refresh_token:
        integration.refresh_token_encrypted = encrypt_token(oauth_result.refresh_token)
    if oauth_result.scope:
        integration.scopes = oauth_result.scope.split(",")

    integration.status = IntegrationStatus.ACTIVE
    integration.oauth_state = None
    integration.error_message = None
    integration.updated_at = datetime.now(UTC)

    db.add(integration)
    await db.commit()

    logger.info(
        f"OAuth successful for integration {integration.id} "
        f"({integration.platform.value}) user_id={integration.user_id}"
    )

    # Register webhooks (non-blocking)
    try:
        webhook_service = WebhookRegistrationService(db)
        results = await webhook_service.register_webhooks(integration.id)
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Registered {success_count} webhooks for integration {integration.id}")
    except Exception as e:
        logger.warning(f"Auto webhook registration failed: {e}")

    # =========================================================================
    # REDIRECT LOGIC — permanent, covers all three install paths
    # =========================================================================

    if host:
        # Path 1: Embedded App Store install — billing required by Shopify
        success_url = (
            f"{settings.FRONTEND_URL}/settings/billing"
            f"?shop={shop}&host={host}&installed=true&integration_id={integration.id}"
        )

    elif integration.user_id is not None:
        # Path 2: Direct install, merchant was already logged in — fully linked
        success_url = (
            f"{settings.FRONTEND_URL}/integrations"
            f"?connected=true&integration_id={integration.id}"
            f"&platform={integration.platform.value}"
        )

    else:
        # Path 3: Direct install, merchant was NOT logged in — needs to claim
        claim_path = f"/integrations/claim?integration_id={integration.id}&platform={integration.platform.value}"
        success_url = f"{settings.FRONTEND_URL}/login?redirect={quote(claim_path)}"

    return RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)


@router.post("/woocommerce/connect", response_model=IntegrationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def connect_woocommerce(
    request: Request,
    data: WooCommerceConnectRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Connect a WooCommerce store using API keys."""
    stmt = select(Integration).where(
        Integration.user_id == current_user.id,
        Integration.platform == EcommercePlatform.WOOCOMMERCE,
        Integration.store_url == data.store_url,
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()

    if existing and existing.status == IntegrationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This store is already connected",
        )

    service = WooCommerceService()
    credentials = f"{data.consumer_key}:{data.consumer_secret}"

    is_valid = await service.verify_credentials(
        store_url=data.store_url,
        access_token=credentials,
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid API credentials. Please verify your consumer key and secret.",
        )

    if existing:
        existing.access_token_encrypted = encrypt_token(credentials)
        existing.status = IntegrationStatus.ACTIVE
        existing.error_message = None
        existing.store_name = data.store_name
        existing.updated_at = datetime.now(UTC)
        db.add(existing)
        integration = existing
    else:
        integration = Integration(
            user_id=current_user.id,
            platform=EcommercePlatform.WOOCOMMERCE,
            store_url=data.store_url,
            store_name=data.store_name,
            status=IntegrationStatus.ACTIVE,
            access_token_encrypted=encrypt_token(credentials),
            scopes=["read_products", "write_products"],
        )
        db.add(integration)

    await db.commit()
    await db.refresh(integration)

    logger.info(f"WooCommerce connected for user {current_user.id}: {data.store_url}")

    try:
        webhook_service = WebhookRegistrationService(db)
        results = await webhook_service.register_webhooks(integration.id)
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Registered {success_count} webhooks for integration {integration.id}")
    except Exception as e:
        logger.warning(f"Auto webhook registration failed: {e}")

    return IntegrationResponse.model_validate(integration)


@router.post("/{integration_id}/claim")
async def claim_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Attach an orphaned integration (user_id=None) to the authenticated user.

    Called after App Store installs where the merchant was not logged in
    during the OAuth flow. The login page redirects here after auth.
    """
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.user_id.is_(None),
        Integration.status == IntegrationStatus.ACTIVE,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found or already claimed",
        )

    integration.user_id = current_user.id
    integration.updated_at = datetime.now(UTC)
    db.add(integration)
    await db.commit()

    logger.info(f"Integration {integration_id} claimed by user {current_user.id}")

    return {"ok": True, "integration_id": str(integration.id)}
