# backend/api/v1/routes/webhooks.py

"""
Webhook Routes

Handles incoming webhooks from Shopify and WooCommerce
for real-time product updates.

Updated to use modular integration services with circuit breaker support.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_session
from core.config import settings
from core.encryption import decrypt_token
from models.integration import Integration, EcommercePlatform, IntegrationStatus

# Use modular imports
from services.integration import (
    ShopifyService,
    WooCommerceService,
    SyncService,
    SyncTemporarilyUnavailable,
    CircuitOpenError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


# ==================== Shopify Webhooks ====================

@router.post("/shopify/{integration_id}")
async def shopify_webhook(
    integration_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
    x_shopify_topic: Optional[str] = Header(None),
    x_shopify_hmac_sha256: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None),
):
    """
    Handle incoming Shopify webhooks.
    
    Headers:
    - X-Shopify-Topic: e.g., "products/create", "products/update"
    - X-Shopify-Hmac-Sha256: HMAC signature for verification
    - X-Shopify-Shop-Domain: The shop domain
    """
    body = await request.body()
    
    # Find integration
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.platform == EcommercePlatform.SHOPIFY,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        logger.warning(f"Shopify webhook for unknown integration: {integration_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    if integration.status != IntegrationStatus.ACTIVE:
        logger.warning(f"Shopify webhook for inactive integration: {integration_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integration is not active")
    
    # Verify signature (skip if no secret configured)
    if x_shopify_hmac_sha256:
        webhook_secret = _get_shopify_webhook_secret(integration)
        if webhook_secret:
            service = ShopifyService()
            if not service.verify_webhook_signature(body, x_shopify_hmac_sha256, webhook_secret):
                logger.warning(f"Invalid Shopify webhook signature for integration: {integration_id}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")
        else:
            logger.warning(f"Skipping signature verification - no secret configured for {integration_id}")
    
    # Parse payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Shopify webhook payload: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")
    
    product_id = str(payload.get("id", ""))
    if not product_id:
        return {"status": "ignored", "reason": "No product ID"}
    
    # Determine action
    action = "update"
    if x_shopify_topic:
        if "create" in x_shopify_topic:
            action = "create"
        elif "delete" in x_shopify_topic:
            action = "delete"
    
    # Process with circuit breaker awareness
    try:
        sync_service = SyncService(db)
        link = await sync_service.sync_single_product(
            integration_id=integration.id,
            external_product_id=product_id,
            action=action,
        )
        
        logger.info(f"Shopify webhook processed: {x_shopify_topic} for product {product_id}")
        
        return {
            "status": "success",
            "action": action,
            "product_id": product_id,
            "link_id": str(link.id) if link else None,
        }
        
    except (CircuitOpenError, SyncTemporarilyUnavailable) as e:
        # Service temporarily unavailable - tell Shopify to retry later
        logger.warning(f"Shopify webhook deferred (circuit open): {product_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable, please retry"
        )
    except Exception as e:
        logger.exception(f"Failed to process Shopify webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )


def _get_shopify_webhook_secret(integration: Integration) -> Optional[str]:
    """Get webhook secret for Shopify signature verification."""
    if integration.webhook_secret_encrypted:
        return decrypt_token(integration.webhook_secret_encrypted)
    # Fallback to client secret (may not be configured)
    return getattr(settings, 'SHOPIFY_CLIENT_SECRET', None)


# ==================== WooCommerce Webhooks ====================

@router.post("/woocommerce/{integration_id}")
async def woocommerce_webhook(
    integration_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
    x_wc_webhook_topic: Optional[str] = Header(None),
    x_wc_webhook_signature: Optional[str] = Header(None),
    x_wc_webhook_source: Optional[str] = Header(None),
):
    """
    Handle incoming WooCommerce webhooks.
    
    Headers:
    - X-WC-Webhook-Topic: e.g., "product.created", "product.updated"
    - X-WC-Webhook-Signature: HMAC signature for verification
    - X-WC-Webhook-Source: The store URL
    """
    body = await request.body()
    
    # Find integration
    stmt = select(Integration).where(
        Integration.id == integration_id,
        Integration.platform == EcommercePlatform.WOOCOMMERCE,
    )
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        logger.warning(f"WooCommerce webhook for unknown integration: {integration_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    if integration.status != IntegrationStatus.ACTIVE:
        logger.warning(f"WooCommerce webhook for inactive integration: {integration_id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integration is not active")
    
    # Verify signature (skip if no secret available)
    if x_wc_webhook_signature:
        webhook_secret = _get_woocommerce_webhook_secret(integration)
        if webhook_secret:
            service = WooCommerceService()
            if not service.verify_webhook_signature(body, x_wc_webhook_signature, webhook_secret):
                logger.warning(f"Invalid WooCommerce webhook signature for integration: {integration_id}")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")
        else:
            logger.warning(f"Skipping signature verification - no secret available for {integration_id}")
    
    # Parse payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse WooCommerce webhook payload: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload")
    
    product_id = str(payload.get("id", ""))
    if not product_id:
        return {"status": "ignored", "reason": "No product ID"}
    
    # Determine action
    action = "update"
    if x_wc_webhook_topic:
        if "created" in x_wc_webhook_topic:
            action = "create"
        elif "deleted" in x_wc_webhook_topic:
            action = "delete"
    
    # Process with circuit breaker awareness
    try:
        sync_service = SyncService(db)
        link = await sync_service.sync_single_product(
            integration_id=integration.id,
            external_product_id=product_id,
            action=action,
        )
        
        logger.info(f"WooCommerce webhook processed: {x_wc_webhook_topic} for product {product_id}")
        
        return {
            "status": "success",
            "action": action,
            "product_id": product_id,
            "link_id": str(link.id) if link else None,
        }
        
    except (CircuitOpenError, SyncTemporarilyUnavailable) as e:
        logger.warning(f"WooCommerce webhook deferred (circuit open): {product_id}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable, please retry"
        )
    except Exception as e:
        logger.exception(f"Failed to process WooCommerce webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )


def _get_woocommerce_webhook_secret(integration: Integration) -> Optional[str]:
    """Get webhook secret for WooCommerce signature verification."""
    if integration.webhook_secret_encrypted:
        return decrypt_token(integration.webhook_secret_encrypted)
    # Fallback: use consumer secret from stored credentials
    try:
        access_token = decrypt_token(integration.access_token_encrypted)
        if ":" in access_token:
            return access_token.split(":", 1)[1]
    except Exception:
        pass
    return None


# ==================== Webhook Registration ====================

@router.post("/{integration_id}/register")
async def register_webhooks(
    integration_id: str,
    db: AsyncSession = Depends(get_session),
):
    """
    Register webhooks with the e-commerce platform.
    Called after OAuth is complete to set up automatic product sync.
    """
    stmt = select(Integration).where(Integration.id == integration_id)
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    if integration.status != IntegrationStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integration is not active")
    
    # Get service and build callback URL
    if integration.platform == EcommercePlatform.SHOPIFY:
        service = ShopifyService()
        callback_url = f"{settings.BACKEND_URL}/api/v1/webhooks/shopify/{integration_id}"
    elif integration.platform == EcommercePlatform.WOOCOMMERCE:
        service = WooCommerceService()
        callback_url = f"{settings.BACKEND_URL}/api/v1/webhooks/woocommerce/{integration_id}"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported platform")
    
    access_token = decrypt_token(integration.access_token_encrypted)
    
    # Register webhooks
    try:
        results = await service.register_webhooks(
            store_url=integration.store_url,
            access_token=access_token,
            callback_url=callback_url,
        )
    except CircuitOpenError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Platform temporarily unavailable"
        )
    
    # Store webhook IDs for later cleanup
    webhook_ids = [r.webhook_id for r in results if r.success and r.webhook_id]
    if webhook_ids and hasattr(integration, 'webhook_ids'):
        integration.webhook_ids = webhook_ids
        db.add(integration)
        await db.commit()
    
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    
    logger.info(f"Registered {len(successes)}/{len(results)} webhooks for integration {integration_id}")
    
    return {
        "status": "completed",
        "registered": len(successes),
        "failed": len(failures),
        "callback_url": callback_url,
        "details": [
            {"topic": r.topic, "success": r.success, "webhook_id": r.webhook_id, "error": r.error}
            for r in results
        ],
    }


@router.delete("/{integration_id}/unregister")
async def unregister_webhooks(
    integration_id: str,
    db: AsyncSession = Depends(get_session),
):
    """
    Unregister all webhooks for an integration.
    Called when disconnecting an integration.
    """
    stmt = select(Integration).where(Integration.id == integration_id)
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    
    # Get stored webhook IDs
    webhook_ids = getattr(integration, 'webhook_ids', None) or []
    if not webhook_ids:
        return {"status": "ok", "message": "No webhooks to unregister"}
    
    # Get service
    if integration.platform == EcommercePlatform.SHOPIFY:
        service = ShopifyService()
    elif integration.platform == EcommercePlatform.WOOCOMMERCE:
        service = WooCommerceService()
    else:
        return {"status": "error", "message": "Unsupported platform"}
    
    try:
        access_token = decrypt_token(integration.access_token_encrypted)
        success = await service.unregister_webhooks(
            store_url=integration.store_url,
            access_token=access_token,
            webhook_ids=webhook_ids,
        )
    except Exception as e:
        logger.warning(f"Failed to unregister webhooks: {e}")
        success = False
    
    # Clear stored webhook IDs
    if hasattr(integration, 'webhook_ids'):
        integration.webhook_ids = []
        db.add(integration)
        await db.commit()
    
    return {
        "status": "ok" if success else "partial",
        "message": "Webhooks unregistered" if success else "Some webhooks may not have been unregistered",
    }


# ==================== Health Check ====================

@router.get("/status")
async def webhook_status():
    """Webhook endpoint health check."""
    return {
        "status": "active",
        "endpoints": {
            "shopify": "/api/v1/webhooks/shopify/{integration_id}",
            "woocommerce": "/api/v1/webhooks/woocommerce/{integration_id}",
        },
    }
