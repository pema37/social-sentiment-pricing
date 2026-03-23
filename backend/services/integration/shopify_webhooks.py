"""
Shopify Webhooks Mixin - Webhook lifecycle management.

Methods:
  - register_webhooks: Create webhook subscriptions via GraphQL
  - unregister_webhooks: Delete webhook subscriptions by ID
  - verify_webhook_signature: HMAC-SHA256 validation of incoming payloads

Uses from ShopifyService (via self):
  - _graphql(), _get_shop_domain(), _gid(), _numeric_id()
  - retry_config, WEBHOOK_TOPICS, WEBHOOK_TOPICS_GQL

Place at: backend/services/integration/shopify_webhooks.py
"""

import base64
import hashlib
import hmac
import logging

import httpx

from .http_client import RetryableClient
from .schemas import WebhookRegistration

logger = logging.getLogger(__name__)


class ShopifyWebhooksMixin:
    """Webhook registration and verification for ShopifyService."""

    async def register_webhooks(
        self,
        store_url: str,
        access_token: str,
        callback_url: str,
    ) -> list[WebhookRegistration]:
        shop_domain = self._get_shop_domain(store_url)
        results: list[WebhookRegistration] = []

        mutation = """
            mutation WebhookCreate($topic: WebhookSubscriptionTopic!, $url: URL!) {
                webhookSubscriptionCreate(
                    topic: $topic
                    webhookSubscription: { callbackUrl: $url, format: JSON }
                ) {
                    webhookSubscription { id }
                    userErrors { field message }
                }
            }
        """

        async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as rc:
            for gql_topic, rest_topic in zip(self.WEBHOOK_TOPICS_GQL, self.WEBHOOK_TOPICS):
                try:
                    data = await self._graphql(
                        rc,
                        shop_domain,
                        access_token,
                        mutation,
                        {"topic": gql_topic, "url": callback_url},
                    )
                    result = data.get("webhookSubscriptionCreate", {})
                    errors = result.get("userErrors", [])
                    if errors:
                        msg = "; ".join(e.get("message", "") for e in errors)
                        results.append(WebhookRegistration(success=False, topic=rest_topic, error=msg))
                    else:
                        wh = result.get("webhookSubscription", {})
                        wh_id = self._numeric_id(wh.get("id", ""))
                        results.append(WebhookRegistration(success=True, webhook_id=wh_id, topic=rest_topic))
                except (httpx.HTTPStatusError, httpx.RequestError, ValueError) as e:
                    results.append(WebhookRegistration(success=False, topic=rest_topic, error=str(e)))

        return results

    async def unregister_webhooks(
        self,
        store_url: str,
        access_token: str,
        webhook_ids: list[str],
    ) -> bool:
        shop_domain = self._get_shop_domain(store_url)
        success = True

        mutation = """
            mutation WebhookDelete($id: ID!) {
                webhookSubscriptionDelete(id: $id) {
                    deletedWebhookSubscriptionId
                    userErrors { field message }
                }
            }
        """

        async with RetryableClient(store_url, "shopify", self.retry_config, 10.0) as rc:
            for wid in webhook_ids:
                try:
                    gid = self._gid("WebhookSubscription", wid)
                    data = await self._graphql(rc, shop_domain, access_token, mutation, {"id": gid})
                    errors = (data.get("webhookSubscriptionDelete") or {}).get("userErrors", [])
                    if errors:
                        logger.warning(f"Failed to delete webhook {wid}: {errors}")
                        success = False
                except (httpx.HTTPStatusError, httpx.RequestError, ValueError):
                    success = False

        return success

    def verify_webhook_signature(self, payload: bytes, signature: str, secret: str) -> bool:
        if signature.startswith("sha256="):
            signature = signature[7:]
        computed = base64.b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()).decode()
        return hmac.compare_digest(computed, signature)
