"""Shopify App Store install flow (unauthenticated)."""

import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/shopify/install")
async def shopify_install(
    shop: str = Query(..., description="The shop domain from Shopify"),
):
    """
    Entry point for Shopify App Store installs.
    No auth required — this is the first thing Shopify hits.
    Redirects merchant to Shopify's OAuth permission screen.
    """
    # Validate shop domain
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"

    state = secrets.token_urlsafe(32)
    
    # Store state temporarily — for now we'll pass it through
    # and validate in callback. Production should use Redis/DB.
    
    scopes = "read_inventory,read_orders,read_products,write_products"
    redirect_uri = f"{settings.BACKEND_URL}/api/v1/integrations/oauth/callback"
    client_id = settings.SHOPIFY_CLIENT_ID

    params = urlencode({
        "client_id": client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    })

    auth_url = f"https://{shop}/admin/oauth/authorize?{params}"
    
    logger.info(f"Shopify install initiated for shop: {shop}")
    
    return RedirectResponse(url=auth_url)

    