# backend/api/v1/routes/webhooks.py

"""
Webhook Routes

Handles incoming webhooks from Shopify and WooCommerce
for real-time product updates.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, status, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.db.session import get_session
from backend.core.encryption import decrypt_token
from backend.models.integration import Integration, EcommercePlatform, IntegrationStatus
from backend.services.integration.shopify_service import ShopifyService
from backend.services.integration.woocommerce_service import WooCommerceService
from backend.services.integration.sync_service import SyncService

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
    
    Shopify sends these headers:
    - X-Shopify-Topic: e.g., "products/create", "products/update"
    - X-Shopify-Hmac-Sha256: HMAC signature for verification
    - X-Shopify-Shop-Domain: The shop domain
    """
    # Get raw body for signature verification
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    if integration.status != IntegrationStatus.ACTIVE:
        logger.warning(f"Shopify webhook for inactive integration: {integration_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration is not active"
        )
    
    # Verify webhook signature
    if integration.webhook_secret_encrypted and x_shopify_hmac_sha256:
        webhook_secret = decrypt_token(integration.webhook_secret_encrypted)
        service = ShopifyService()
        
        if not service.verify_webhook_signature(body, x_shopify_hmac_sha256, webhook_secret):
            logger.warning(f"Invalid Shopify webhook signature for integration: {integration_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
    
    # Parse the webhook payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse Shopify webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    # Extract product ID and action
    product_id = str(payload.get("id", ""))
    
    if not product_id:
        logger.warning("Shopify webhook missing product ID")
        return {"status": "ignored", "reason": "No product ID"}
    
    # Determine action from topic
    action = "update"
    if x_shopify_topic:
        if "create" in x_shopify_topic:
            action = "create"
        elif "delete" in x_shopify_topic:
            action = "delete"
    
    # Process the webhook
    try:
        sync_service = SyncService(db)
        link = await sync_service.sync_single_product(
            integration_id=integration.id,
            external_product_id=product_id,
            action=action,
        )
        
        logger.info(f"Processed Shopify webhook: {x_shopify_topic} for product {product_id}")
        
        return {
            "status": "success",
            "action": action,
            "product_id": product_id,
            "link_id": str(link.id) if link else None,
        }
        
    except Exception as e:
        logger.exception(f"Failed to process Shopify webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )


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
    
    WooCommerce sends these headers:
    - X-WC-Webhook-Topic: e.g., "product.created", "product.updated"
    - X-WC-Webhook-Signature: HMAC signature for verification
    - X-WC-Webhook-Source: The store URL
    """
    # Get raw body for signature verification
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    if integration.status != IntegrationStatus.ACTIVE:
        logger.warning(f"WooCommerce webhook for inactive integration: {integration_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration is not active"
        )
    
    # Verify webhook signature
    if integration.webhook_secret_encrypted and x_wc_webhook_signature:
        webhook_secret = decrypt_token(integration.webhook_secret_encrypted)
        service = WooCommerceService()
        
        if not service.verify_webhook_signature(body, x_wc_webhook_signature, webhook_secret):
            logger.warning(f"Invalid WooCommerce webhook signature for integration: {integration_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
    
    # Parse the webhook payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse WooCommerce webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    
    # Extract product ID
    product_id = str(payload.get("id", ""))
    
    if not product_id:
        logger.warning("WooCommerce webhook missing product ID")
        return {"status": "ignored", "reason": "No product ID"}
    
    # Determine action from topic
    action = "update"
    if x_wc_webhook_topic:
        if "created" in x_wc_webhook_topic:
            action = "create"
        elif "deleted" in x_wc_webhook_topic:
            action = "delete"
    
    # Process the webhook
    try:
        sync_service = SyncService(db)
        link = await sync_service.sync_single_product(
            integration_id=integration.id,
            external_product_id=product_id,
            action=action,
        )
        
        logger.info(f"Processed WooCommerce webhook: {x_wc_webhook_topic} for product {product_id}")
        
        return {
            "status": "success",
            "action": action,
            "product_id": product_id,
            "link_id": str(link.id) if link else None,
        }
        
    except Exception as e:
        logger.exception(f"Failed to process WooCommerce webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}"
        )


# ==================== Webhook Registration Endpoint ====================

@router.post("/{integration_id}/register")
async def register_webhooks(
    integration_id: str,
    db: AsyncSession = Depends(get_session),
):
    """
    Register webhooks with the e-commerce platform.
    
    This should be called after OAuth is complete to set up
    automatic product sync via webhooks.
    """
    stmt = select(Integration).where(Integration.id == integration_id)
    result = await db.execute(stmt)
    integration = result.scalars().first()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found"
        )
    
    if integration.status != IntegrationStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration is not active"
        )
    
    # Get service
    if integration.platform == EcommercePlatform.SHOPIFY:
        service = ShopifyService()
        callback_url = f"https://your-domain.com/api/v1/webhooks/shopify/{integration_id}"
    elif integration.platform == EcommercePlatform.WOOCOMMERCE:
        service = WooCommerceService()
        callback_url = f"https://your-domain.com/api/v1/webhooks/woocommerce/{integration_id}"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform: {integration.platform}"
        )
    
    # Decrypt access token
    access_token = decrypt_token(integration.access_token_encrypted)
    
    # Register webhooks
    results = await service.register_webhooks(
        store_url=integration.store_url,
        access_token=access_token,
        callback_url=callback_url,
    )
    
    # Count successes and failures
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]
    
    return {
        "status": "completed",
        "registered": len(successes),
        "failed": len(failures),
        "details": [
            {
                "topic": r.topic,
                "success": r.success,
                "webhook_id": r.webhook_id,
                "error": r.error,
            }
            for r in results
        ],
    }
