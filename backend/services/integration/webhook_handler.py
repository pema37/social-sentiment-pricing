# backend/services/integration/webhook_handler.py

"""
Webhook Handler Service

Receives and processes webhooks from e-commerce platforms.
Verifies signatures, parses payloads, and triggers sync.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.encryption import decrypt_token
from models.integration import (
    EcommercePlatform,
    Integration,
    IntegrationStatus,
)

from .shopify_service import ShopifyService
from .sync_service import SyncService
from .woocommerce_service import WooCommerceService

logger = logging.getLogger(__name__)


class WebhookSource(StrEnum):
    """Webhook source platform"""

    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


class WebhookAction(StrEnum):
    """Webhook action type"""

    PRODUCT_CREATED = "product_created"
    PRODUCT_UPDATED = "product_updated"
    PRODUCT_DELETED = "product_deleted"
    UNKNOWN = "unknown"


@dataclass
class WebhookEvent:
    """Parsed webhook event"""

    source: WebhookSource
    action: WebhookAction
    external_product_id: str
    store_url: str
    raw_payload: dict
    received_at: datetime


@dataclass
class WebhookResult:
    """Result of webhook processing"""

    success: bool
    action: WebhookAction
    external_product_id: str | None = None
    error: str | None = None
    processing_time_ms: float | None = None


class WebhookHandler:
    """
    Handles incoming webhooks from e-commerce platforms.

    Flow:
    1. Verify signature (security)
    2. Parse payload to determine action
    3. Find matching integration
    4. Trigger appropriate sync action
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.sync_service = SyncService(db)
        self._shopify = ShopifyService()
        self._woocommerce = WooCommerceService()

    # ==================== Shopify Webhooks ====================

    async def handle_shopify_webhook(
        self,
        payload: bytes,
        signature: str,
        shop_domain: str,
        topic: str,
    ) -> WebhookResult:
        """
        Handle incoming Shopify webhook.

        Args:
            payload: Raw request body
            signature: X-Shopify-Hmac-Sha256 header
            shop_domain: X-Shopify-Shop-Domain header
            topic: X-Shopify-Topic header (e.g., "products/update")

        Returns:
            WebhookResult with processing outcome
        """
        start_time = datetime.now(UTC)

        try:
            # Find integration by store URL
            integration = await self._find_integration(shop_domain, EcommercePlatform.SHOPIFY)

            if not integration:
                logger.warning(f"No integration found for Shopify store: {shop_domain}")
                return WebhookResult(success=False, action=WebhookAction.UNKNOWN, error="Integration not found")

            # Verify signature
            webhook_secret = self._get_webhook_secret(integration)
            if not self._shopify.verify_webhook_signature(payload, signature, webhook_secret):
                logger.warning(f"Invalid Shopify webhook signature for {shop_domain}")
                return WebhookResult(success=False, action=WebhookAction.UNKNOWN, error="Invalid signature")

            # Parse payload
            import json

            data = json.loads(payload)

            # Determine action
            action = self._parse_shopify_topic(topic)
            external_product_id = str(data.get("id", ""))

            if not external_product_id:
                return WebhookResult(success=False, action=action, error="No product ID in payload")

            # Process the webhook
            sync_action = self._action_to_sync_action(action)
            await self.sync_service.sync_single_product(
                integration_id=integration.id,
                external_product_id=external_product_id,
                action=sync_action,
            )

            processing_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            logger.info(
                f"Shopify webhook processed: {action.value} for product {external_product_id} "
                f"from {shop_domain} in {processing_time:.0f}ms"
            )

            return WebhookResult(
                success=True,
                action=action,
                external_product_id=external_product_id,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.exception(f"Error processing Shopify webhook from {shop_domain}")
            return WebhookResult(success=False, action=WebhookAction.UNKNOWN, error=str(e))

    def _parse_shopify_topic(self, topic: str) -> WebhookAction:
        """Parse Shopify webhook topic to action."""
        topic_map = {
            "products/create": WebhookAction.PRODUCT_CREATED,
            "products/update": WebhookAction.PRODUCT_UPDATED,
            "products/delete": WebhookAction.PRODUCT_DELETED,
        }
        return topic_map.get(topic, WebhookAction.UNKNOWN)

    # ==================== WooCommerce Webhooks ====================

    async def handle_woocommerce_webhook(
        self,
        payload: bytes,
        signature: str,
        webhook_source: str,
        webhook_topic: str,
    ) -> WebhookResult:
        """
        Handle incoming WooCommerce webhook.

        Args:
            payload: Raw request body
            signature: X-WC-Webhook-Signature header
            webhook_source: X-WC-Webhook-Source header (store URL)
            webhook_topic: X-WC-Webhook-Topic header

        Returns:
            WebhookResult with processing outcome
        """
        start_time = datetime.now(UTC)

        try:
            # Normalize store URL
            store_url = self._normalize_woo_source(webhook_source)

            # Find integration
            integration = await self._find_integration(store_url, EcommercePlatform.WOOCOMMERCE)

            if not integration:
                logger.warning(f"No integration found for WooCommerce store: {store_url}")
                return WebhookResult(success=False, action=WebhookAction.UNKNOWN, error="Integration not found")

            # Verify signature
            webhook_secret = self._get_webhook_secret(integration)
            if not self._woocommerce.verify_webhook_signature(payload, signature, webhook_secret):
                logger.warning(f"Invalid WooCommerce webhook signature for {store_url}")
                return WebhookResult(success=False, action=WebhookAction.UNKNOWN, error="Invalid signature")

            # Parse payload
            import json

            data = json.loads(payload)

            # Determine action
            action = self._parse_woocommerce_topic(webhook_topic)
            external_product_id = str(data.get("id", ""))

            if not external_product_id:
                return WebhookResult(success=False, action=action, error="No product ID in payload")

            # Process the webhook
            sync_action = self._action_to_sync_action(action)
            await self.sync_service.sync_single_product(
                integration_id=integration.id,
                external_product_id=external_product_id,
                action=sync_action,
            )

            processing_time = (datetime.now(UTC) - start_time).total_seconds() * 1000

            logger.info(
                f"WooCommerce webhook processed: {action.value} for product {external_product_id} "
                f"from {store_url} in {processing_time:.0f}ms"
            )

            return WebhookResult(
                success=True,
                action=action,
                external_product_id=external_product_id,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.exception("Error processing WooCommerce webhook")
            return WebhookResult(success=False, action=WebhookAction.UNKNOWN, error=str(e))

    def _parse_woocommerce_topic(self, topic: str) -> WebhookAction:
        """Parse WooCommerce webhook topic to action."""
        topic_map = {
            "product.created": WebhookAction.PRODUCT_CREATED,
            "product.updated": WebhookAction.PRODUCT_UPDATED,
            "product.deleted": WebhookAction.PRODUCT_DELETED,
        }
        return topic_map.get(topic, WebhookAction.UNKNOWN)

    def _normalize_woo_source(self, source: str) -> str:
        """Normalize WooCommerce source URL."""
        url = source.strip().lower().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        return url

    # ==================== Helpers ====================

    async def _find_integration(
        self,
        store_identifier: str,
        platform: EcommercePlatform,
    ) -> Integration | None:
        """Find active integration by store URL/domain."""
        # Normalize the identifier
        normalized = store_identifier.strip().lower()

        # For Shopify, it might be just the domain
        if platform == EcommercePlatform.SHOPIFY and not normalized.endswith(".myshopify.com"):
            normalized = f"{normalized}.myshopify.com"

        # Query for matching integration
        stmt = select(Integration).where(
            Integration.platform == platform,
            Integration.status == IntegrationStatus.ACTIVE,
        )
        result = await self.db.execute(stmt)
        integrations = result.scalars().all()

        # Find matching store URL
        for integration in integrations:
            stored_url = integration.store_url.strip().lower()

            if platform == EcommercePlatform.SHOPIFY:
                # Extract domain from stored URL
                stored_domain = stored_url.replace("https://", "").replace("http://", "").rstrip("/")
                if stored_domain == normalized or normalized in stored_domain:
                    return integration
            else:
                # WooCommerce - compare normalized URLs
                stored_normalized = stored_url.rstrip("/")
                if not stored_normalized.startswith(("http://", "https://")):
                    stored_normalized = f"https://{stored_normalized}"
                if stored_normalized == normalized:
                    return integration

        return None

    def _get_webhook_secret(self, integration: Integration) -> str:
        """Get webhook secret for signature verification."""
        # Option 1: Use a stored webhook secret
        if hasattr(integration, "webhook_secret") and integration.webhook_secret:
            return decrypt_token(integration.webhook_secret)

        # Option 2: For Shopify, use the client secret
        if integration.platform == EcommercePlatform.SHOPIFY:
            from core.config import settings

            return settings.SHOPIFY_CLIENT_SECRET

        # Option 3: For WooCommerce, use the consumer secret
        if integration.platform == EcommercePlatform.WOOCOMMERCE:
            access_token = decrypt_token(integration.access_token_encrypted)
            # WooCommerce stores consumer_key:consumer_secret
            if ":" in access_token:
                return access_token.split(":", 1)[1]

        raise ValueError("No webhook secret available")

    def _action_to_sync_action(self, action: WebhookAction) -> str:
        """Convert webhook action to sync action string."""
        action_map = {
            WebhookAction.PRODUCT_CREATED: "create",
            WebhookAction.PRODUCT_UPDATED: "update",
            WebhookAction.PRODUCT_DELETED: "delete",
        }
        return action_map.get(action, "update")
