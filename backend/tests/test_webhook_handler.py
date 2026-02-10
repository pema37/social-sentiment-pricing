"""
Tests for services.integration.webhook_handler
"""

import sys
import types
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Stub heavy external deps
# ---------------------------------------------------------------------------
_stubs: dict[str, types.ModuleType] = {}

_needed = [
    "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlmodel",
    "models", "models.integration",
    "core", "core.encryption",
    "services.integration.shopify_service",
    "services.integration.woocommerce_service",
    "services.integration.sync_service",
]

for _mod_name in _needed:
    if _mod_name not in sys.modules:
        _stubs[_mod_name] = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _stubs[_mod_name]

_sqlmodel = sys.modules["sqlmodel"]
_sqlmodel.select = MagicMock()

_async_mod = sys.modules["sqlalchemy.ext.asyncio"]
_async_mod.AsyncSession = MagicMock()


class _FakeIntegrationStatus:
    ACTIVE = "active"


class _FakeEcommercePlatform:
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


_integ_mod = sys.modules["models.integration"]
_integ_mod.Integration = MagicMock
_integ_mod.IntegrationStatus = _FakeIntegrationStatus
_integ_mod.EcommercePlatform = _FakeEcommercePlatform

sys.modules["core.encryption"].decrypt_token = MagicMock(return_value="decrypted-secret")
sys.modules["services.integration.shopify_service"].ShopifyService = MagicMock
sys.modules["services.integration.woocommerce_service"].WooCommerceService = MagicMock
sys.modules["services.integration.sync_service"].SyncService = lambda *a, **kw: AsyncMock()

# --- import under test ---
from services.integration.webhook_handler import (
    WebhookHandler,
    WebhookSource,
    WebhookAction,
    WebhookEvent,
    WebhookResult,
)

# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_handler():
    db = AsyncMock()
    handler = WebhookHandler(db)
    handler.sync_service = AsyncMock()
    handler._shopify = MagicMock()
    handler._woocommerce = MagicMock()
    return handler, db


def _make_integration(**kw):
    integ = MagicMock()
    integ.id = kw.get("id", uuid4())
    integ.platform = kw.get("platform", _FakeEcommercePlatform.SHOPIFY)
    integ.store_url = kw.get("store_url", "https://myshop.myshopify.com")
    integ.access_token_encrypted = "enc"
    integ.webhook_secret = None
    return integ


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestWebhookEnums:
    def test_source_values(self):
        assert WebhookSource.SHOPIFY == "shopify"
        assert WebhookSource.WOOCOMMERCE == "woocommerce"

    def test_action_values(self):
        assert WebhookAction.PRODUCT_CREATED == "product_created"
        assert WebhookAction.PRODUCT_UPDATED == "product_updated"
        assert WebhookAction.PRODUCT_DELETED == "product_deleted"
        assert WebhookAction.UNKNOWN == "unknown"


class TestWebhookResult:
    def test_success_result(self):
        r = WebhookResult(success=True, action=WebhookAction.PRODUCT_UPDATED, external_product_id="123")
        assert r.success is True
        assert r.external_product_id == "123"

    def test_failure_result(self):
        r = WebhookResult(success=False, action=WebhookAction.UNKNOWN, error="bad sig")
        assert r.success is False
        assert r.error == "bad sig"


class TestParseShopifyTopic:
    def test_products_create(self):
        handler, _ = _make_handler()
        assert handler._parse_shopify_topic("products/create") == WebhookAction.PRODUCT_CREATED

    def test_products_update(self):
        handler, _ = _make_handler()
        assert handler._parse_shopify_topic("products/update") == WebhookAction.PRODUCT_UPDATED

    def test_products_delete(self):
        handler, _ = _make_handler()
        assert handler._parse_shopify_topic("products/delete") == WebhookAction.PRODUCT_DELETED

    def test_unknown_topic(self):
        handler, _ = _make_handler()
        assert handler._parse_shopify_topic("orders/create") == WebhookAction.UNKNOWN


class TestParseWooCommerceTopic:
    def test_product_created(self):
        handler, _ = _make_handler()
        assert handler._parse_woocommerce_topic("product.created") == WebhookAction.PRODUCT_CREATED

    def test_product_updated(self):
        handler, _ = _make_handler()
        assert handler._parse_woocommerce_topic("product.updated") == WebhookAction.PRODUCT_UPDATED

    def test_product_deleted(self):
        handler, _ = _make_handler()
        assert handler._parse_woocommerce_topic("product.deleted") == WebhookAction.PRODUCT_DELETED

    def test_unknown(self):
        handler, _ = _make_handler()
        assert handler._parse_woocommerce_topic("order.created") == WebhookAction.UNKNOWN


class TestNormalizeWooSource:
    def test_strips_and_lowercases(self):
        handler, _ = _make_handler()
        assert handler._normalize_woo_source("  MyStore.com/  ") == "https://mystore.com"

    def test_adds_https(self):
        handler, _ = _make_handler()
        assert handler._normalize_woo_source("shop.example.com") == "https://shop.example.com"

    def test_preserves_existing_https(self):
        handler, _ = _make_handler()
        assert handler._normalize_woo_source("https://shop.example.com") == "https://shop.example.com"


class TestActionToSyncAction:
    def test_created(self):
        handler, _ = _make_handler()
        assert handler._action_to_sync_action(WebhookAction.PRODUCT_CREATED) == "create"

    def test_updated(self):
        handler, _ = _make_handler()
        assert handler._action_to_sync_action(WebhookAction.PRODUCT_UPDATED) == "update"

    def test_deleted(self):
        handler, _ = _make_handler()
        assert handler._action_to_sync_action(WebhookAction.PRODUCT_DELETED) == "delete"

    def test_unknown_defaults_update(self):
        handler, _ = _make_handler()
        assert handler._action_to_sync_action(WebhookAction.UNKNOWN) == "update"


class TestHandleShopifyWebhook:
    @pytest.mark.asyncio
    async def test_integration_not_found(self):
        handler, db = _make_handler()
        handler._find_integration = AsyncMock(return_value=None)

        result = await handler.handle_shopify_webhook(
            payload=b'{}', signature="sig", shop_domain="unknown.myshopify.com", topic="products/update"
        )
        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_signature(self):
        handler, db = _make_handler()
        integration = _make_integration()
        handler._find_integration = AsyncMock(return_value=integration)
        handler._get_webhook_secret = MagicMock(return_value="secret")
        handler._shopify.verify_webhook_signature.return_value = False

        result = await handler.handle_shopify_webhook(
            payload=b'{}', signature="bad-sig", shop_domain="myshop.myshopify.com", topic="products/update"
        )
        assert result.success is False
        assert "signature" in result.error.lower()

    @pytest.mark.asyncio
    async def test_no_product_id_in_payload(self):
        handler, db = _make_handler()
        integration = _make_integration()
        handler._find_integration = AsyncMock(return_value=integration)
        handler._get_webhook_secret = MagicMock(return_value="secret")
        handler._shopify.verify_webhook_signature.return_value = True

        payload = json.dumps({}).encode()
        result = await handler.handle_shopify_webhook(
            payload=payload, signature="sig", shop_domain="myshop.myshopify.com", topic="products/update"
        )
        assert result.success is False
        assert "product ID" in result.error

    @pytest.mark.asyncio
    async def test_successful_processing(self):
        handler, db = _make_handler()
        integration = _make_integration()
        handler._find_integration = AsyncMock(return_value=integration)
        handler._get_webhook_secret = MagicMock(return_value="secret")
        handler._shopify.verify_webhook_signature.return_value = True
        handler.sync_service.sync_single_product = AsyncMock()

        payload = json.dumps({"id": 12345}).encode()
        result = await handler.handle_shopify_webhook(
            payload=payload, signature="sig", shop_domain="myshop.myshopify.com", topic="products/update"
        )
        assert result.success is True
        assert result.action == WebhookAction.PRODUCT_UPDATED
        assert result.external_product_id == "12345"
        assert result.processing_time_ms is not None

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        handler, db = _make_handler()
        handler._find_integration = AsyncMock(side_effect=RuntimeError("db down"))

        result = await handler.handle_shopify_webhook(
            payload=b'{}', signature="sig", shop_domain="x.myshopify.com", topic="products/update"
        )
        assert result.success is False
        assert "db down" in result.error


class TestHandleWooCommerceWebhook:
    @pytest.mark.asyncio
    async def test_integration_not_found(self):
        handler, db = _make_handler()
        handler._find_integration = AsyncMock(return_value=None)

        result = await handler.handle_woocommerce_webhook(
            payload=b'{}', signature="sig", webhook_source="unknown.com", webhook_topic="product.updated"
        )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_invalid_signature(self):
        handler, db = _make_handler()
        integration = _make_integration(platform=_FakeEcommercePlatform.WOOCOMMERCE)
        handler._find_integration = AsyncMock(return_value=integration)
        handler._get_webhook_secret = MagicMock(return_value="secret")
        handler._woocommerce.verify_webhook_signature.return_value = False

        result = await handler.handle_woocommerce_webhook(
            payload=b'{}', signature="bad", webhook_source="shop.com", webhook_topic="product.updated"
        )
        assert result.success is False
        assert "signature" in result.error.lower()

    @pytest.mark.asyncio
    async def test_successful_processing(self):
        handler, db = _make_handler()
        integration = _make_integration(platform=_FakeEcommercePlatform.WOOCOMMERCE)
        handler._find_integration = AsyncMock(return_value=integration)
        handler._get_webhook_secret = MagicMock(return_value="secret")
        handler._woocommerce.verify_webhook_signature.return_value = True
        handler.sync_service.sync_single_product = AsyncMock()

        payload = json.dumps({"id": 999}).encode()
        result = await handler.handle_woocommerce_webhook(
            payload=payload, signature="sig", webhook_source="shop.com", webhook_topic="product.created"
        )
        assert result.success is True
        assert result.action == WebhookAction.PRODUCT_CREATED
        assert result.external_product_id == "999"

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        handler, db = _make_handler()
        handler._find_integration = AsyncMock(side_effect=RuntimeError("crash"))

        result = await handler.handle_woocommerce_webhook(
            payload=b'{}', signature="sig", webhook_source="shop.com", webhook_topic="product.updated"
        )
        assert result.success is False


class TestGetWebhookSecret:
    def test_uses_stored_webhook_secret(self):
        handler, _ = _make_handler()
        integ = MagicMock()
        integ.webhook_secret = "enc-secret"
        integ.platform = _FakeEcommercePlatform.SHOPIFY

        with patch("services.integration.webhook_handler.decrypt_token", return_value="decrypted"):
            result = handler._get_webhook_secret(integ)
        assert result == "decrypted"

    def test_woocommerce_extracts_from_access_token(self):
        handler, _ = _make_handler()
        integ = MagicMock()
        integ.webhook_secret = None
        # hasattr returns False for webhook_secret
        del integ.webhook_secret
        integ.platform = _FakeEcommercePlatform.WOOCOMMERCE
        integ.access_token_encrypted = "enc"

        with patch("services.integration.webhook_handler.decrypt_token", return_value="key:secret123"):
            result = handler._get_webhook_secret(integ)
        assert result == "secret123"

    def test_raises_when_no_secret_available(self):
        handler, _ = _make_handler()
        integ = MagicMock()
        integ.webhook_secret = None
        del integ.webhook_secret
        integ.platform = "unknown"
        integ.access_token_encrypted = "enc"

        # Not shopify, not woo — should raise
        with patch("services.integration.webhook_handler.decrypt_token", return_value="no-colon"):
            with pytest.raises(ValueError, match="No webhook secret"):
                handler._get_webhook_secret(integ)


                