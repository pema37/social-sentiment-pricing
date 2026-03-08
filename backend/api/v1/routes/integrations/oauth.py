"""OAuth flow and WooCommerce API key connection endpoints.

UPDATED (2026-02-20): After successful Shopify OAuth, redirect to billing
plan selection instead of straight to dashboard. This ensures new installs
are prompted to pick a paid plan (Shopify App Store compliance requirement).

FIXED (2026-03-08): Added claim endpoint to attach orphaned integrations
(user_id=None) to authenticated users after install flow.
"""

import logging
import secrets
from datetime import datetime, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import settings
from core.deps import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT
from db.session import get_session
from core.encryption import encrypt_token
from models.user import User
from models.integration import Integration, EcommercePlatform, IntegrationStatus
from schemas.integration import (
    OAuthInitRequest,
    OAuthInitResponse,
    IntegrationResponse,
    WooCommerceConnectRequest,
)
from services.integration import ShopifyService, WooCommerceService, WebhookRegistrationService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_ecommerce_service(platform: EcommercePlatform):
    """Factory to get the right service for the platform."""
    if platform == EcommercePlatform.SHOPIFY:
        return ShopifyService()
    elif platform == EcommercePlatform.WOOCOMMERCE:
        return WooCommerceService()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {platform}"
        )


@router.post("/oauth/init", response_model=OAuthInitResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def init_oauth(
    request: Request,
    data: OAuthInitRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Start OAuth flow for connecting a store."""
    stmt = select(Integration).where(
        Integration.user_id == current_user.id,
        Integration.platform == data.platform,
        Integration.store_url == data.store_url,
    )
    result = await db.execute(stmt)
    existing = result.scalars().first()

    if existing and existing.status == IntegrationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This store is already connected"
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
    state: str = None,
    hmac: str = None,
    host: str = None,
    timestamp: str = None,
    db: AsyncSession = Depends(get_session),
):
    """
    OAuth callback - handles both authenticated flow and fresh Shopify installs.

    UPDATED (2026-02-20): After successful Shopify OAuth, redirect to billing
    plan selection page instead of dashboard. This is required for Shopify App
    Store compliance — merchants must be able to select a plan after install.

    For reinstalls where a billing subscription already exists, Shopify
    automatically reactivates it, so the billing page will show the active plan.
    """

    integration = None

    # Try finding by state (existing authenticated flow)
    if state:
        stmt = select(Integration).where(Integration.oauth_state == state)
        result = await db.execute(stmt)
        integration = result.scalars().first()

    # Fresh Shopify install — no state match, find or create by shop
    if not integration and shop:
        stmt = select(Integration).where(
            Integration.platform == EcommercePlatform.SHOPIFY,
            Integration.store_url == shop,
        )
        result = await db.execute(stmt)
        integration = result.scalars().first()

        if not integration:
            # Create new integration for this shop (user linked later via /claim)
            integration = Integration(
                platform=EcommercePlatform.SHOPIFY,
                store_url=shop,
                store_name=shop.replace(".myshopify.com", ""),
                status=IntegrationStatus.DISCONNECTED,
                access_token_encrypted=b"pending",
            )
            db.add(integration)
            await db.flush()

    if not integration:
        error_url = f"{settings.FRONTEND_URL}/integrations?error=invalid_state&message=OAuth+session+expired+or+invalid"
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

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
            f"?error=oauth_failed&message={oauth_result.error}&platform={integration.platform.value}"
        )
        return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)

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

    logger.info(f"OAuth successful for integration {integration.id} ({integration.platform.value})")

    try:
        webhook_service = WebhookRegistrationService(db)
        results = await webhook_service.register_webhooks(integration.id)
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Registered {success_count} webhooks for integration {integration.id}")
    except Exception as e:
        logger.warning(f"Auto webhook registration failed: {e}")

    # =========================================================================
    # REDIRECT LOGIC
    # If user_id is None (installed via App Store without being logged in),
    # redirect to claim flow so frontend can attach to authenticated user.
    # Otherwise Shopify → billing, WooCommerce → dashboard.
    # =========================================================================

    if integration.user_id is None:
        success_url = (
            f"{settings.FRONTEND_URL}/integrations/claim"
            f"?integration_id={integration.id}&shop={shop}&installed=true"
        )
    elif integration.platform == EcommercePlatform.SHOPIFY:
        if host:
            success_url = (
                f"{settings.FRONTEND_URL}/settings/billing"
                f"?shop={shop}&host={host}&installed=true&integration_id={integration.id}"
            )
        else:
            success_url = (
                f"{settings.FRONTEND_URL}/settings/billing"
                f"?shop={shop}&installed=true&integration_id={integration.id}"
            )
    else:
        success_url = (
            f"{settings.FRONTEND_URL}/integrations"
            f"?connected=true&integration_id={integration.id}&platform={integration.platform.value}"
        )

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
            detail="This store is already connected"
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
            detail="Invalid API credentials. Please verify your consumer key and secret."
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

    Called after App Store installs where the merchant wasn't logged in
    during the OAuth flow. Frontend hits this after login to link the
    integration to the correct account.
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
            detail="Integration not found or already claimed"
        )

    integration.user_id = current_user.id
    integration.updated_at = datetime.now(UTC)
    db.add(integration)
    await db.commit()

    logger.info(f"Integration {integration_id} claimed by user {current_user.id}")

    return {"ok": True, "integration_id": str(integration.id)}



