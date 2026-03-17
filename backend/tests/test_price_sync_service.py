# backend/tests/test_price_sync_service.py
"""
Comprehensive tests for PriceSyncService — fetches and syncs live prices
from connected e-commerce platforms (Shopify, WooCommerce).

Tests cover:
- Initialization
- get_live_price (orchestration, error handling)
- sync_product_price (update logic, no-op paths)
- _get_active_link (DB query for active integration)
- _fetch_from_platform (platform routing)
- _fetch_shopify_price (Shopify service delegation)
- _fetch_woocommerce_price (WooCommerce service delegation)

Total: ~45 tests
"""

import sys
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# === Import isolation ===
for mod in [
    "db.session",
    "models.product",
    "models.integration",
    "models.product_link",
    "services.integration.shopify_service",
    "services.integration.woocommerce_service",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


# Fake model classes with class-level attrs for SQLAlchemy .join()/.where()
class _FakeIntegration:
    id = MagicMock()
    user_id = MagicMock()
    status = MagicMock()


class _FakeProductLink:
    integration_id = MagicMock()
    product_id = MagicMock()
    sync_enabled = MagicMock()


# Force-set UNCONDITIONALLY — even if another test already loaded the module
sys.modules["models.integration"].Integration = _FakeIntegration
sys.modules["models.integration"].ProductIntegrationLink = _FakeProductLink
sys.modules["models.product_link"].ProductLink = _FakeProductLink

import pytest

from services.pricing.price_sync_service import PriceSyncService

SERVICE_PATH = "services.pricing.price_sync_service"

# ============================================================
# Helpers
# ============================================================

PRODUCT_ID = uuid4()
USER_ID = uuid4()


def make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def make_product(
    id=None,
    name="Test Product",
    current_price=Decimal("100.00"),
):
    p = MagicMock()
    p.id = id or PRODUCT_ID
    p.name = name
    p.current_price = current_price
    return p


def make_link(
    external_product_id="ext-123",
    external_variant_id="var-456",
    integration_id=None,
):
    link = MagicMock()
    link.external_product_id = external_product_id
    link.external_variant_id = external_variant_id
    link.integration_id = integration_id or uuid4()
    return link


def make_integration(platform="shopify", status="active"):
    integ = MagicMock()
    integ.platform = platform
    integ.status = status
    integ.id = uuid4()
    return integ


# ============================================================
# 1. Initialization
# ============================================================


class TestPriceSyncServiceInit:
    def test_stores_db(self):
        db = make_mock_db()
        svc = PriceSyncService(db)
        assert svc.db is db


# ============================================================
# 2. get_live_price
# ============================================================


class TestGetLivePrice:
    @pytest.mark.asyncio
    async def test_returns_live_price(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        link = make_link()
        integ = make_integration(platform="shopify")
        svc._get_active_link = AsyncMock(return_value=(link, integ))
        svc._fetch_from_platform = AsyncMock(return_value=Decimal("99.99"))

        result = await svc.get_live_price(make_product(), USER_ID)
        assert result == Decimal("99.99")

    @pytest.mark.asyncio
    async def test_returns_none_when_no_link(self):
        db = make_mock_db()
        svc = PriceSyncService(db)
        svc._get_active_link = AsyncMock(return_value=(None, None))

        result = await svc.get_live_price(make_product(), USER_ID)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_fetch_returns_none(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        link = make_link()
        integ = make_integration()
        svc._get_active_link = AsyncMock(return_value=(link, integ))
        svc._fetch_from_platform = AsyncMock(return_value=None)

        result = await svc.get_live_price(make_product(), USER_ID)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        db = make_mock_db()
        svc = PriceSyncService(db)
        svc._get_active_link = AsyncMock(side_effect=Exception("connection failed"))

        result = await svc.get_live_price(make_product(), USER_ID)
        assert result is None

    @pytest.mark.asyncio
    async def test_calls_get_active_link_with_correct_args(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        product = make_product()
        svc._get_active_link = AsyncMock(return_value=(None, None))

        await svc.get_live_price(product, USER_ID)
        svc._get_active_link.assert_awaited_once_with(product.id, USER_ID)

    @pytest.mark.asyncio
    async def test_calls_fetch_from_platform(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        link = make_link()
        integ = make_integration()
        svc._get_active_link = AsyncMock(return_value=(link, integ))
        svc._fetch_from_platform = AsyncMock(return_value=Decimal("50"))

        await svc.get_live_price(make_product(), USER_ID)
        svc._fetch_from_platform.assert_awaited_once_with(link, integ)


# ============================================================
# 3. sync_product_price
# ============================================================


class TestSyncProductPrice:
    @pytest.mark.asyncio
    async def test_updates_when_price_differs(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        product = make_product(current_price=Decimal("100"))
        svc.get_live_price = AsyncMock(return_value=Decimal("110"))

        result = await svc.sync_product_price(product, USER_ID)
        assert result is True
        assert product.current_price == Decimal("110")
        db.add.assert_called_once_with(product)
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(product)

    @pytest.mark.asyncio
    async def test_no_update_when_prices_match(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        product = make_product(current_price=Decimal("100"))
        svc.get_live_price = AsyncMock(return_value=Decimal("100"))

        result = await svc.sync_product_price(product, USER_ID)
        assert result is False
        db.add.assert_not_called()
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_false_when_no_live_price(self):
        db = make_mock_db()
        svc = PriceSyncService(db)
        svc.get_live_price = AsyncMock(return_value=None)

        result = await svc.sync_product_price(make_product(), USER_ID)
        assert result is False

    @pytest.mark.asyncio
    async def test_updates_product_object_in_place(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        product = make_product(current_price=Decimal("50"))
        svc.get_live_price = AsyncMock(return_value=Decimal("75"))

        await svc.sync_product_price(product, USER_ID)
        assert product.current_price == Decimal("75")

    @pytest.mark.asyncio
    async def test_commits_and_refreshes(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        product = make_product(current_price=Decimal("100"))
        svc.get_live_price = AsyncMock(return_value=Decimal("95"))

        await svc.sync_product_price(product, USER_ID)
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(product)


# ============================================================
# 4. _get_active_link
# ============================================================


class TestGetActiveLink:
    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_link_and_integration(self, mock_select):
        import types

        _im = types.ModuleType("models.integration")
        _im.Integration = _FakeIntegration
        _im.ProductIntegrationLink = _FakeProductLink
        _plm = types.ModuleType("models.product_link")
        _plm.ProductLink = _FakeProductLink

        with patch.dict(
            sys.modules,
            {
                "models.integration": _im,
                "models.product_link": _plm,
            },
        ):
            mock_chain = MagicMock()
            mock_chain.join.return_value = mock_chain
            mock_chain.where.return_value = mock_chain
            mock_select.return_value = mock_chain

            db = make_mock_db()
            link = make_link()
            integ = make_integration()
            mock_result = MagicMock()
            mock_result.first.return_value = (link, integ)
            db.execute.return_value = mock_result

            svc = PriceSyncService(db)
            result = await svc._get_active_link(PRODUCT_ID, USER_ID)
            assert result == (link, integ)

    @pytest.mark.asyncio
    @patch(f"{SERVICE_PATH}.select")
    async def test_returns_none_none_when_not_found(self, mock_select):
        import types

        _im = types.ModuleType("models.integration")
        _im.Integration = _FakeIntegration
        _im.ProductIntegrationLink = _FakeProductLink
        _plm = types.ModuleType("models.product_link")
        _plm.ProductLink = _FakeProductLink

        with patch.dict(
            sys.modules,
            {
                "models.integration": _im,
                "models.product_link": _plm,
            },
        ):
            mock_chain = MagicMock()
            mock_chain.join.return_value = mock_chain
            mock_chain.where.return_value = mock_chain
            mock_select.return_value = mock_chain

            db = make_mock_db()
            mock_result = MagicMock()
            mock_result.first.return_value = None
            db.execute.return_value = mock_result

            svc = PriceSyncService(db)
            result = await svc._get_active_link(PRODUCT_ID, USER_ID)
            assert result == (None, None)


# ============================================================
# 5. _fetch_from_platform
# ============================================================


class TestFetchFromPlatform:
    @pytest.mark.asyncio
    async def test_routes_to_shopify(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        link = make_link()
        integ = make_integration(platform="shopify")
        svc._fetch_shopify_price = AsyncMock(return_value=Decimal("99"))

        result = await svc._fetch_from_platform(link, integ)
        assert result == Decimal("99")
        svc._fetch_shopify_price.assert_awaited_once_with(link, integ)

    @pytest.mark.asyncio
    async def test_routes_to_woocommerce(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        link = make_link()
        integ = make_integration(platform="woocommerce")
        svc._fetch_woocommerce_price = AsyncMock(return_value=Decimal("89"))

        result = await svc._fetch_from_platform(link, integ)
        assert result == Decimal("89")
        svc._fetch_woocommerce_price.assert_awaited_once_with(link, integ)

    @pytest.mark.asyncio
    async def test_unknown_platform_returns_none(self):
        db = make_mock_db()
        svc = PriceSyncService(db)

        link = make_link()
        integ = make_integration(platform="bigcommerce")

        result = await svc._fetch_from_platform(link, integ)
        assert result is None


# ============================================================
# 6. _fetch_shopify_price
# ============================================================


class TestFetchShopifyPrice:
    @pytest.mark.asyncio
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_returns_price(self, MockShopify):
        db = make_mock_db()
        svc = PriceSyncService(db)

        mock_service = AsyncMock()
        mock_service.get_product_price.return_value = {"price": "49.99"}
        MockShopify.return_value = mock_service

        link = make_link(external_product_id="prod-1", external_variant_id="var-1")
        integ = make_integration(platform="shopify")

        result = await svc._fetch_shopify_price(link, integ)
        assert result == Decimal("49.99")

    @pytest.mark.asyncio
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_returns_none_when_no_data(self, MockShopify):
        db = make_mock_db()
        svc = PriceSyncService(db)

        mock_service = AsyncMock()
        mock_service.get_product_price.return_value = None
        MockShopify.return_value = mock_service

        link = make_link()
        integ = make_integration()

        result = await svc._fetch_shopify_price(link, integ)
        assert result is None

    @pytest.mark.asyncio
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_returns_none_when_price_key_missing(self, MockShopify):
        db = make_mock_db()
        svc = PriceSyncService(db)

        mock_service = AsyncMock()
        mock_service.get_product_price.return_value = {"status": "ok"}
        MockShopify.return_value = mock_service

        link = make_link()
        integ = make_integration()

        result = await svc._fetch_shopify_price(link, integ)
        assert result is None

    @pytest.mark.asyncio
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_returns_none_when_price_is_none(self, MockShopify):
        db = make_mock_db()
        svc = PriceSyncService(db)

        mock_service = AsyncMock()
        mock_service.get_product_price.return_value = {"price": None}
        MockShopify.return_value = mock_service

        link = make_link()
        integ = make_integration()

        result = await svc._fetch_shopify_price(link, integ)
        assert result is None

    @pytest.mark.asyncio
    @patch("services.integration.shopify_service.ShopifyService")
    async def test_passes_variant_id(self, MockShopify):
        db = make_mock_db()
        svc = PriceSyncService(db)

        mock_service = AsyncMock()
        mock_service.get_product_price.return_value = {"price": "10"}
        MockShopify.return_value = mock_service

        link = make_link(external_product_id="p-abc", external_variant_id="v-xyz")
        integ = make_integration()

        await svc._fetch_shopify_price(link, integ)
        mock_service.get_product_price.assert_awaited_once_with("p-abc", "v-xyz")


# ============================================================
# 7. _fetch_woocommerce_price
# ============================================================


class TestFetchWooCommercePrice:
    @pytest.mark.asyncio
    @patch("services.integration.woocommerce_service.WooCommerceService")
    async def test_returns_price(self, MockWoo):
        db = make_mock_db()
        svc = PriceSyncService(db)

        mock_service = AsyncMock()
        mock_service.get_product_price.return_value = {"price": "39.99"}
        MockWoo.return_value = mock_service

        link = make_link(external_product_id="woo-123")
        integ = make_integration(platform="woocommerce")

        result = await svc._fetch_woocommerce_price(link, integ)
        assert result == Decimal("39.99")

    @pytest.mark.asyncio
    @patch("services.integration.woocommerce_service.WooCommerceService")
    async def test_returns_none_when_no_data(self, MockWoo):
        db = make_mock_db()
        svc = PriceSyncService(db)

        mock_service = AsyncMock()
        mock_service.get_product_price.return_value = None
        MockWoo.return_value = mock_service

        link = make_link()
        integ = make_integration()

        result = await svc._fetch_woocommerce_price(link, integ)
        assert result is None

    @pytest.mark.asyncio
    @patch("services.integration.woocommerce_service.WooCommerceService")
    async def test_returns_none_when_price_is_none(self, MockWoo):
        db = make_mock_db()
        svc = PriceSyncService(db)

        mock_service = AsyncMock()
        mock_service.get_product_price.return_value = {"price": None}
        MockWoo.return_value = mock_service

        link = make_link()
        integ = make_integration()

        result = await svc._fetch_woocommerce_price(link, integ)
        assert result is None

    @pytest.mark.asyncio
    @patch("services.integration.woocommerce_service.WooCommerceService")
    async def test_passes_product_id_only(self, MockWoo):
        """WooCommerce doesn't use variant ID."""
        db = make_mock_db()
        svc = PriceSyncService(db)

        mock_service = AsyncMock()
        mock_service.get_product_price.return_value = {"price": "10"}
        MockWoo.return_value = mock_service

        link = make_link(external_product_id="woo-999")
        integ = make_integration()

        await svc._fetch_woocommerce_price(link, integ)
        mock_service.get_product_price.assert_awaited_once_with("woo-999")
