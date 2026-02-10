# backend/services/integration/webhook_registration.py

"""
Webhook Registration Service

Manages webhook registration/unregistration for integrations.
Called when integrations are connected or disconnected.
"""

import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.integration import Integration, IntegrationStatus, EcommercePlatform
from core.config import settings
from core.encryption import decrypt_token

from .schemas import WebhookRegistration
from .shopify_service import ShopifyService
from .woocommerce_service import WooCommerceService

logger = logging.getLogger(__name__)


class WebhookRegistrationService:
    """
    Manages webhook lifecycle for integrations.
    
    - Registers webhooks when integration is connected
    - Unregisters webhooks when integration is disconnected
    - Stores webhook IDs for later cleanup
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._shopify = ShopifyService()
        self._woocommerce = WooCommerceService()
    
    def _get_callback_url(self, platform: EcommercePlatform, integration_id: UUID) -> str:
        """Get the webhook callback URL for a platform."""
        base_url = settings.BACKEND_URL.rstrip("/")
        
        if platform == EcommercePlatform.SHOPIFY:
            return f"{base_url}/api/v1/webhooks/shopify/{integration_id}"
        elif platform == EcommercePlatform.WOOCOMMERCE:
            return f"{base_url}/api/v1/webhooks/woocommerce/{integration_id}"
        else:
            raise ValueError(f"Unsupported platform: {platform}")
    
    async def register_webhooks(
        self,
        integration_id: UUID,
    ) -> List[WebhookRegistration]:
        """
        Register webhooks for an integration.
        
        Called after successful OAuth/connection.
        
        Args:
            integration_id: The integration to register webhooks for
            
        Returns:
            List of WebhookRegistration results
        """
        # Get integration
        stmt = select(Integration).where(Integration.id == integration_id)
        result = await self.db.execute(stmt)
        integration = result.scalars().first()
        
        if not integration:
            raise ValueError("Integration not found")
        
        if integration.status != IntegrationStatus.ACTIVE:
            raise ValueError("Integration is not active")
        
        # Get service and decrypt token
        service = self._get_service(integration.platform)
        access_token = decrypt_token(integration.access_token_encrypted)
        callback_url = self._get_callback_url(integration.platform, integration_id)
        
        logger.info(f"Registering webhooks for {integration.store_url}")
        
        # Register webhooks
        results = await service.register_webhooks(
            store_url=integration.store_url,
            access_token=access_token,
            callback_url=callback_url,
        )
        
        # Store webhook IDs on the integration
        webhook_ids = [r.webhook_id for r in results if r.success and r.webhook_id]
        if webhook_ids:
            integration.webhook_ids = webhook_ids
            self.db.add(integration)
            await self.db.commit()
        
        # Log results
        success_count = sum(1 for r in results if r.success)
        logger.info(
            f"Registered {success_count}/{len(results)} webhooks for {integration.store_url}"
        )
        
        for r in results:
            if not r.success:
                logger.warning(f"Failed to register webhook {r.topic}: {r.error}")
        
        return results
    
    async def unregister_webhooks(
        self,
        integration_id: UUID,
    ) -> bool:
        """
        Unregister all webhooks for an integration.
        
        Called when integration is disconnected.
        
        Args:
            integration_id: The integration to unregister webhooks for
            
        Returns:
            True if all webhooks were unregistered successfully
        """
        # Get integration
        stmt = select(Integration).where(Integration.id == integration_id)
        result = await self.db.execute(stmt)
        integration = result.scalars().first()
        
        if not integration:
            logger.warning(f"Integration {integration_id} not found for webhook cleanup")
            return False
        
        # Check if we have webhook IDs stored
        webhook_ids = getattr(integration, 'webhook_ids', None) or []
        if not webhook_ids:
            logger.info(f"No webhooks to unregister for {integration.store_url}")
            return True
        
        # Get service and decrypt token
        service = self._get_service(integration.platform)
        
        # Token might be invalid if disconnecting due to auth failure
        try:
            access_token = decrypt_token(integration.access_token_encrypted)
        except Exception:
            logger.warning(f"Could not decrypt token for webhook cleanup: {integration.store_url}")
            return False
        
        logger.info(f"Unregistering {len(webhook_ids)} webhooks for {integration.store_url}")
        
        # Unregister webhooks
        success = await service.unregister_webhooks(
            store_url=integration.store_url,
            access_token=access_token,
            webhook_ids=webhook_ids,
        )
        
        # Clear stored webhook IDs
        integration.webhook_ids = []
        self.db.add(integration)
        await self.db.commit()
        
        if success:
            logger.info(f"All webhooks unregistered for {integration.store_url}")
        else:
            logger.warning(f"Some webhooks failed to unregister for {integration.store_url}")
        
        return success
    
    async def verify_webhooks(
        self,
        integration_id: UUID,
    ) -> dict:
        """
        Verify webhooks are properly registered.
        
        Useful for health checks and debugging.
        
        Returns:
            Status dict with webhook details
        """
        stmt = select(Integration).where(Integration.id == integration_id)
        result = await self.db.execute(stmt)
        integration = result.scalars().first()
        
        if not integration:
            return {"status": "error", "error": "Integration not found"}
        
        webhook_ids = getattr(integration, 'webhook_ids', None) or []
        
        return {
            "status": "ok",
            "integration_id": str(integration_id),
            "store_url": integration.store_url,
            "platform": integration.platform.value,
            "webhook_count": len(webhook_ids),
            "webhook_ids": webhook_ids,
            "callback_url": self._get_callback_url(integration.platform, integration_id),
        }
    
    def _get_service(self, platform: EcommercePlatform):
        """Get service for platform."""
        if platform == EcommercePlatform.SHOPIFY:
            return self._shopify
        elif platform == EcommercePlatform.WOOCOMMERCE:
            return self._woocommerce
        raise ValueError(f"Unsupported platform: {platform}")


# ==================== Helper Functions ====================

async def register_webhooks_for_integration(
    db: AsyncSession,
    integration_id: UUID,
) -> List[WebhookRegistration]:
    """
    Helper function to register webhooks.
    Can be called from routes or background tasks.
    """
    service = WebhookRegistrationService(db)
    return await service.register_webhooks(integration_id)


async def unregister_webhooks_for_integration(
    db: AsyncSession,
    integration_id: UUID,
) -> bool:
    """
    Helper function to unregister webhooks.
    Can be called from routes or background tasks.
    """
    service = WebhookRegistrationService(db)
    return await service.unregister_webhooks(integration_id)
