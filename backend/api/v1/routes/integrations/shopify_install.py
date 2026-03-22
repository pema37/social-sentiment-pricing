"""Shopify App Store install flow (unauthenticated).

FIXED (2026-03-08): State token is now persisted to DB before redirecting
to Shopify OAuth. Previously state was generated but never saved, causing
the callback to miss the state match, create an orphaned integration with
user_id=None, and leave the real integration in ERROR/DISCONNECTED status.
"""

import hashlib
import hmac as hmac_lib
import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import settings
from db.session import get_session
from models.integration import EcommercePlatform, Integration, IntegrationStatus

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_shopify_install_hmac(
    query_params: dict[str, str],
    secret: str,
) -> bool:
    """
    Verify the HMAC on a Shopify install/auth request.

    Shopify signs the query string: sort all params except 'hmac',
    join as key=value with '&', HMAC-SHA256 with the client secret.
    """
    hmac_value = query_params.get("hmac", "")
    if not hmac_value or not secret:
        return False

    # Build the message: sorted params excluding 'hmac'
    filtered = {k: v for k, v in query_params.items() if k != "hmac"}
    message = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))

    computed = hmac_lib.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac_lib.compare_digest(computed, hmac_value)


@router.get("/shopify/install")
async def shopify_install(
    request: Request,
    shop: str = Query(..., description="The shop domain from Shopify"),
    hmac: str | None = Query(None),
    timestamp: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
):
    """
    Entry point for Shopify App Store installs.
    No auth required — this is the first thing Shopify hits.
    Redirects merchant to Shopify's OAuth permission screen.
    """
    # Verify Shopify HMAC signature on the install request
    query_params = dict(request.query_params)
    if not _verify_shopify_install_hmac(query_params, settings.SHOPIFY_CLIENT_SECRET):
        logger.warning(f"Shopify install HMAC verification failed for shop={shop}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HMAC signature",
        )

    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"

    state = secrets.token_urlsafe(32)

    # Persist state to DB so the OAuth callback can match it.
    # Without this, callback falls back to find-by-shop and creates
    # an orphaned integration with user_id=None.
    stmt = select(Integration).where(
        Integration.platform == EcommercePlatform.SHOPIFY,
        Integration.store_url == shop,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()

    if integration:
        integration.oauth_state = state
        db.add(integration)
    else:
        integration = Integration(
            platform=EcommercePlatform.SHOPIFY,
            store_url=shop,
            store_name=shop.replace(".myshopify.com", ""),
            status=IntegrationStatus.DISCONNECTED,
            oauth_state=state,
            access_token_encrypted=b"pending",
        )
        db.add(integration)

    await db.commit()

    scopes = "read_inventory,read_orders,read_products,write_products"
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/integrations/oauth/callback"

    params = urlencode(
        {
            "client_id": settings.SHOPIFY_CLIENT_ID,
            "scope": scopes,
            "redirect_uri": redirect_uri,
            "state": state,
        }
    )

    auth_url = f"https://{shop}/admin/oauth/authorize?{params}"

    logger.info(f"Shopify install initiated for shop: {shop}, integration_id: {integration.id}")

    return RedirectResponse(url=auth_url)
