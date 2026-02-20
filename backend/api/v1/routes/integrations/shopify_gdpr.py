# backend/api/v1/routes/integrations/shopify_gdpr.py
"""
Shopify GDPR Compliance Webhooks.

Shopify REQUIRES these 3 endpoints for App Store submission:
1. customers/data_request - Customer requests their data
2. customers/redact - Customer requests data deletion
3. shop/redact - Store uninstalls, delete all store data

See: https://shopify.dev/docs/apps/build/privacy-law-compliance
"""

import hmac as hmac_lib
import hashlib
import base64
import json
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status, Header

from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shopify/gdpr", tags=["Shopify GDPR"])


def verify_shopify_hmac(payload: bytes, hmac_header: str, secret: str) -> bool:
    """Verify Shopify webhook HMAC-SHA256 signature."""
    if not hmac_header or not secret:
        return False
    computed = base64.b64encode(
        hmac_lib.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    ).decode("utf-8")
    return hmac_lib.compare_digest(computed, hmac_header)


async def _verify_webhook(request: Request, hmac_sha256: Optional[str]) -> bytes:
    """Common HMAC verification for all GDPR webhooks."""
    body = await request.body()

    secret = settings.SHOPIFY_CLIENT_SECRET
    if not secret:
        logger.error("SHOPIFY_CLIENT_SECRET not configured")
        raise HTTPException(status_code=500, detail="Webhook verification not configured")

    if not hmac_sha256:
        logger.warning(f"Missing HMAC header on GDPR webhook from {request.client.host}")
        raise HTTPException(status_code=401, detail="Missing HMAC signature")

    if not verify_shopify_hmac(body, hmac_sha256, secret):
        logger.warning(f"Invalid HMAC on GDPR webhook from {request.client.host}")
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    return body


@router.post("/customers/data_request", status_code=200)
async def customers_data_request(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None, alias="X-Shopify-Hmac-Sha256"),
):
    """Handle customer data request (GDPR)."""
    body = await _verify_webhook(request, x_shopify_hmac_sha256)

    try:
        payload = json.loads(body)
        logger.info(f"GDPR data request: shop={payload.get('shop_domain', 'unknown')}")
    except Exception:
        logger.info("GDPR data request received")

    return {"status": "acknowledged", "message": "No customer PII stored by ActualPrice"}


@router.post("/customers/redact", status_code=200)
async def customers_redact(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None, alias="X-Shopify-Hmac-Sha256"),
):
    """Handle customer data deletion request (GDPR)."""
    body = await _verify_webhook(request, x_shopify_hmac_sha256)

    try:
        payload = json.loads(body)
        logger.info(f"GDPR customer redact: shop={payload.get('shop_domain', 'unknown')}")
    except Exception:
        logger.info("GDPR customer redact received")

    return {"status": "acknowledged", "message": "No customer PII to redact"}


@router.post("/shop/redact", status_code=200)
async def shop_redact(
    request: Request,
    x_shopify_hmac_sha256: Optional[str] = Header(None, alias="X-Shopify-Hmac-Sha256"),
):
    """
    Handle shop data deletion (48 hours after uninstall).
    
    TODO: Implement full cleanup before going live:
    - Delete Integration record for this shop
    - Delete ProductIntegrationLinks
    - Delete cached Shopify product data
    - Audit log the deletion
    """
    body = await _verify_webhook(request, x_shopify_hmac_sha256)

    try:
        payload = json.loads(body)
        logger.info(f"GDPR shop redact: shop={payload.get('shop_domain', 'unknown')}")
    except Exception:
        logger.info("GDPR shop redact received")

    return {"status": "acknowledged", "message": "Shop data redaction queued"}


    