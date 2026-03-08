"""Shopify App Store install flow (unauthenticated).

FIXED (2026-03-08): State token is now persisted to DB before redirecting
to Shopify OAuth. Previously state was generated but never saved, causing
the callback to miss the state match, create an orphaned integration with
user_id=None, and leave the real integration in ERROR/DISCONNECTED status.
"""

import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import settings
from db.session import get_session
from models.integration import Integration, EcommercePlatform, IntegrationStatus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/shopify/install")
async def shopify_install(
    shop: str = Query(..., description="The shop domain from Shopify"),
    db: AsyncSession = Depends(get_session),
):
    """
    Entry point for Shopify App Store installs.
    No auth required — this is the first thing Shopify hits.
    Redirects merchant to Shopify's OAuth permission screen.
    """
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

    params = urlencode({
        "client_id": settings.SHOPIFY_CLIENT_ID,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    })

    auth_url = f"https://{shop}/admin/oauth/authorize?{params}"

    logger.info(f"Shopify install initiated for shop: {shop}, integration_id: {integration.id}")

    return RedirectResponse(url=auth_url)



