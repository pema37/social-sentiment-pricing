# backend/api/v1/routes/integrations/shopify_gdpr.py
"""
Shopify GDPR Compliance Webhooks.

Shopify REQUIRES these 3 endpoints for App Store submission:
1. customers/data_request - Customer requests their data
2. customers/redact - Customer requests data deletion
3. shop/redact - Store uninstalls, delete all store data

See: https://shopify.dev/docs/apps/build/privacy-law-compliance
"""

import base64
import hashlib
import hmac as hmac_lib
import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.config import settings
from db.session import get_session
from models.integration import (
    EcommercePlatform,
    Integration,
    IntegrationSyncLog,
    ProductIntegrationLink,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shopify/gdpr", tags=["Shopify GDPR"])


def verify_shopify_hmac(payload: bytes, hmac_header: str, secret: str) -> bool:
    """Verify Shopify webhook HMAC-SHA256 signature."""
    if not hmac_header or not secret:
        return False
    computed = base64.b64encode(hmac_lib.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()).decode("utf-8")
    return hmac_lib.compare_digest(computed, hmac_header)


async def _verify_webhook(request: Request, hmac_sha256: str | None) -> bytes:
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
    x_shopify_hmac_sha256: str | None = Header(None, alias="X-Shopify-Hmac-Sha256"),
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
    x_shopify_hmac_sha256: str | None = Header(None, alias="X-Shopify-Hmac-Sha256"),
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
    x_shopify_hmac_sha256: str | None = Header(None, alias="X-Shopify-Hmac-Sha256"),
    db: AsyncSession = Depends(get_session),
):
    """
    Handle shop data deletion (48 hours after uninstall).

    Deletes all data associated with the shop:
    - IntegrationSyncLog records
    - ProductIntegrationLink records
    - Integration record itself
    """
    body = await _verify_webhook(request, x_shopify_hmac_sha256)

    try:
        payload = json.loads(body)
        shop_domain = payload.get("shop_domain", "")
    except Exception:
        logger.warning("GDPR shop redact: could not parse payload")
        return {"status": "acknowledged", "message": "Shop data redacted"}

    if not shop_domain:
        logger.warning("GDPR shop redact: missing shop_domain in payload")
        return {"status": "acknowledged", "message": "No shop_domain provided"}

    logger.info(f"GDPR shop redact: starting cleanup for shop={shop_domain}")

    # Find all integrations for this shop
    stmt = select(Integration).where(
        Integration.platform == EcommercePlatform.SHOPIFY,
        Integration.store_url == shop_domain,
    )
    result = await db.execute(stmt)
    integrations = list(result.scalars().all())

    if not integrations:
        logger.info(f"GDPR shop redact: no integrations found for shop={shop_domain}")
        return {"status": "acknowledged", "message": "No data found for shop"}

    total_logs = 0
    total_links = 0

    for integration in integrations:
        # Delete sync logs
        logs_stmt = select(IntegrationSyncLog).where(
            IntegrationSyncLog.integration_id == integration.id
        )
        logs_result = await db.execute(logs_stmt)
        logs = list(logs_result.scalars().all())
        for log in logs:
            db.delete(log)
        total_logs += len(logs)

        # Delete product links
        links_stmt = select(ProductIntegrationLink).where(
            ProductIntegrationLink.integration_id == integration.id
        )
        links_result = await db.execute(links_stmt)
        links = list(links_result.scalars().all())
        for link in links:
            db.delete(link)
        total_links += len(links)

        # Delete the integration record
        db.delete(integration)

    await db.commit()

    logger.info(
        f"GDPR shop redact complete: shop={shop_domain}, "
        f"deleted {len(integrations)} integrations, "
        f"{total_logs} sync logs, {total_links} product links"
    )

    return {"status": "acknowledged", "message": "Shop data redacted"}
