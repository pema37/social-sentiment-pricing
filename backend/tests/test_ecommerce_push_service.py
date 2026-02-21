# backend/tests/test_ecommerce_push_service.py
"""
Comprehensive tests for EcommercePushService — pushes price updates
to connected e-commerce platforms (Shopify, WooCommerce).

Tests cover:
- Initialization
- push_price (orchestration, multi-platform aggregation)
- _push_to_platform (single platform push logic)

Total: ~30 tests
"""

import sys
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# === Import isolation ===
for mod in [
    "db.session",
    "models.product",
    "models.integration",
    "core.encryption",
    "services.integration.shopify_service",
    "services.integration.woocommerce_service",
    "services.integration.base",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from services.pricing.ecommerce_push_service import EcommercePushService

SERVICE_PATH = "services.pricing.ecommerce_push_service"

# ============================================================
# Helpers
# ============================================================

PRODUCT_ID = uuid4()
INTEGRATION_ID = uuid4()
LINK_ID = uuid4()


def make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.get = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def make_product(id=None, current_price=Decimal("99.99")):
    p = MagicMock()
    p.id = id or PRODUCT_ID
    p.current_price = current_price
    return p


def make_link(
    id=None,
    integration_id=None,
    external_product_id="ext-prod-1",
    external_variant_id="ext-var-1",
):
    link = MagicMock()
    link.id = id or LINK_ID
    link.integration_id = integration_id or INTEGRATION_ID
    link.external_product_id = external_product_id
    link.external_variant_id = external_variant_id
    link.product_id = PRODUCT_ID
    link.last_price_push_at = None
    link.external_price = None
    link.updated_at = None
    return link


def make_integration(platform="shopify", active=True):
    from models.integration import IntegrationStatus

    integ = MagicMock()
    integ.id = INTEGRATION_ID
    integ.platform = MagicMock()
    integ.platform.value = platform
    integ.store_url = "https://test.myshopify.com"
    integ.access_token_encrypted = "encrypted_token"
    integ.status = IntegrationStatus.ACTIVE if active else MagicMock()
    return integ


def make_success_response(old_price=95.0):
    from services.integration.base import PriceUpdateResult
    resp = MagicMock()
    resp.result = PriceUpdateResult.SUCCESS
    resp.old_price = old_price
    resp.error = None
    return resp


def make_failure_response(error="API rate limited"):
    from services.integration.base import PriceUpdateResult
    resp = MagicMock()
    # Make result NOT equal to SUCCESS
    resp.result = MagicMock()
    resp.old_price = None
    resp.error = error
    return resp


# ============================================================
# 1. Initialization
# ============================================================

class TestEcommercePushServiceInit:

    def test_stores_db(self):
        db = make_mock_db()
        svc = EcommercePushService(db)
        assert svc.db is db


# ============================================================
# 2. push_price (orchestration)
# ============================================================

class TestPushPrice:

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_no_links_returns_failure(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.join.return_value = mock_chain
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute.return_value = mock_result

        svc = EcommercePushService(db)
        result = await svc.push_price(make_product())

        assert result["success"] is False
        assert result["error_code"] == "NO_ACTIVE_INTEGRATION_LINK"

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_single_link_success(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.join.return_value = mock_chain
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [make_link()]
        db.execute.return_value = mock_result

        svc = EcommercePushService(db)
        svc._push_to_platform = AsyncMock(return_value={
            "platform": "shopify", "success": True,
        })

        result = await svc.push_price(make_product())
        assert result["success"] is True
        assert result["platforms_pushed"] == 1

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_multi_link_all_succeed(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.join.return_value = mock_chain
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [make_link(), make_link()]
        db.execute.return_value = mock_result

        svc = EcommercePushService(db)
        svc._push_to_platform = AsyncMock(side_effect=[
            {"platform": "shopify", "success": True},
            {"platform": "woocommerce", "success": True},
        ])

        result = await svc.push_price(make_product())
        assert result["success"] is True
        assert result["platforms_pushed"] == 2
        assert result["platforms_failed"] == 0

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_partial_failure(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.join.return_value = mock_chain
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [make_link(), make_link()]
        db.execute.return_value = mock_result

        svc = EcommercePushService(db)
        svc._push_to_platform = AsyncMock(side_effect=[
            {"platform": "shopify", "success": True},
            {"platform": "woocommerce", "success": False, "error": "timeout"},
        ])

        result = await svc.push_price(make_product())
        assert result["success"] is True
        assert result["platforms_pushed"] == 1
        assert result["platforms_failed"] == 1

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_all_platforms_fail(self, mock_select):
        mock_chain = MagicMock()
        mock_chain.join.return_value = mock_chain
        mock_chain.where.return_value = mock_chain
        mock_select.return_value = mock_chain

        db = make_mock_db()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [make_link()]
        db.execute.return_value = mock_result

        svc = EcommercePushService(db)
        svc._push_to_platform = AsyncMock(return_value={
            "platform": "shopify", "success": False, "error": "API error",
        })

        result = await svc.push_price(make_product())
        assert result["success"] is False
        assert result["error_code"] == "ALL_PLATFORMS_FAILED"

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        db = make_mock_db()
        db.execute.side_effect = Exception("DB connection lost")

        svc = EcommercePushService(db)
        result = await svc.push_price(make_product())
        assert result["success"] is False
        assert result["error_code"] == "EXCEPTION"


# ============================================================
# 3. _push_to_platform
# ============================================================

class TestPushToPlatform:

    @pytest.mark.asyncio
    async def test_integration_not_found(self):
        db = make_mock_db()
        db.get.return_value = None

        svc = EcommercePushService(db)
        result = await svc._push_to_platform(make_product(), make_link())

        assert result["success"] is False
        assert result["error_code"] == "INTEGRATION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_integration_inactive(self):
        db = make_mock_db()
        db.get.return_value = make_integration(active=False)

        svc = EcommercePushService(db)
        result = await svc._push_to_platform(make_product(), make_link())

        assert result["success"] is False
        assert result["error_code"] == "INTEGRATION_INACTIVE"

    @pytest.mark.asyncio
    @patch("core.encryption.decrypt_token")
    async def test_token_decrypt_failure(self, mock_decrypt):
        mock_decrypt.side_effect = Exception("decryption failed")

        db = make_mock_db()
        db.get.return_value = make_integration()

        svc = EcommercePushService(db)
        result = await svc._push_to_platform(make_product(), make_link())

        assert result["success"] is False
        assert result["error_code"] == "TOKEN_DECRYPT_FAILED"

    @pytest.mark.asyncio
    @patch("core.encryption.decrypt_token", return_value="decrypted_token")
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_shopify_success(self, MockShopify, mock_decrypt):
        db = make_mock_db()
        db.get.return_value = make_integration(platform="shopify")

        mock_service = AsyncMock()
        mock_service.update_price.return_value = make_success_response(old_price=95.0)
        MockShopify.return_value = mock_service

        svc = EcommercePushService(db)
        product = make_product(current_price=Decimal("99.99"))
        result = await svc._push_to_platform(product, make_link())

        assert result["success"] is True
        assert result["platform"] == "shopify"
        assert result["new_price"] == float(Decimal("99.99"))

    @pytest.mark.asyncio
    @patch("core.encryption.decrypt_token", return_value="decrypted_token")
    @patch("services.integration.woocommerce_service.WooCommerceService")
    async def test_woocommerce_success(self, MockWoo, mock_decrypt):
        db = make_mock_db()
        db.get.return_value = make_integration(platform="woocommerce")

        mock_service = AsyncMock()
        mock_service.update_price.return_value = make_success_response()
        MockWoo.return_value = mock_service

        svc = EcommercePushService(db)
        result = await svc._push_to_platform(make_product(), make_link())

        assert result["success"] is True
        assert result["platform"] == "woocommerce"

    @pytest.mark.asyncio
    @patch("core.encryption.decrypt_token", return_value="decrypted_token")
    async def test_unsupported_platform(self, mock_decrypt):
        db = make_mock_db()
        db.get.return_value = make_integration(platform="bigcommerce")

        svc = EcommercePushService(db)
        result = await svc._push_to_platform(make_product(), make_link())

        assert result["success"] is False
        assert result["error_code"] == "UNSUPPORTED_PLATFORM"

    @pytest.mark.asyncio
    @patch("core.encryption.decrypt_token", return_value="decrypted_token")
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_api_error_response(self, MockShopify, mock_decrypt):
        db = make_mock_db()
        db.get.return_value = make_integration(platform="shopify")

        mock_service = AsyncMock()
        mock_service.update_price.return_value = make_failure_response("rate limited")
        MockShopify.return_value = mock_service

        svc = EcommercePushService(db)
        result = await svc._push_to_platform(make_product(), make_link())

        assert result["success"] is False
        assert result["error_code"] == "API_ERROR"
        assert result["error"] == "rate limited"

    @pytest.mark.asyncio
    @patch("core.encryption.decrypt_token", return_value="decrypted_token")
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_success_updates_link_metadata(self, MockShopify, mock_decrypt):
        db = make_mock_db()
        db.get.return_value = make_integration(platform="shopify")

        mock_service = AsyncMock()
        mock_service.update_price.return_value = make_success_response()
        MockShopify.return_value = mock_service

        link = make_link()
        product = make_product(current_price=Decimal("99.99"))

        svc = EcommercePushService(db)
        await svc._push_to_platform(product, link)

        assert link.external_price == Decimal("99.99")
        assert link.last_price_push_at is not None
        assert link.updated_at is not None
        db.add.assert_called_with(link)

    @pytest.mark.asyncio
    @patch("core.encryption.decrypt_token", return_value="token")
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_passes_correct_args_to_service(self, MockShopify, mock_decrypt):
        db = make_mock_db()
        db.get.return_value = make_integration(platform="shopify")

        mock_service = AsyncMock()
        mock_service.update_price.return_value = make_success_response()
        MockShopify.return_value = mock_service

        svc = EcommercePushService(db)
        await svc._push_to_platform(make_product(), make_link())

        mock_service.update_price.assert_awaited_once()
        call_kwargs = mock_service.update_price.call_args
        assert call_kwargs.kwargs["store_url"] == "https://test.myshopify.com"
        assert call_kwargs.kwargs["access_token"] == "token"

    @pytest.mark.asyncio
    @patch("core.encryption.decrypt_token", return_value="token")
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_success_returns_old_price(self, MockShopify, mock_decrypt):
        db = make_mock_db()
        db.get.return_value = make_integration(platform="shopify")

        mock_service = AsyncMock()
        mock_service.update_price.return_value = make_success_response(old_price=85.0)
        MockShopify.return_value = mock_service

        svc = EcommercePushService(db)
        result = await svc._push_to_platform(make_product(), make_link())

        assert result["old_price"] == 85.0

    @pytest.mark.asyncio
    async def test_exception_returns_error(self):
        db = make_mock_db()
        db.get.side_effect = Exception("unexpected error")

        svc = EcommercePushService(db)
        result = await svc._push_to_platform(make_product(), make_link())

        assert result["success"] is False
        assert result["error_code"] == "EXCEPTION"


        