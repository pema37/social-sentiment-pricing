"""
Tests for services.integration.handlers.product_sync_handler
"""

import sys
import types
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
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
    "services", "services.integration",
    "services.integration.models",
    "services.integration.base",
    "services.integration.shopify_service",
    "services.integration.woocommerce_service",
    "services.integration.repositories",
    "services.integration.handlers",
]

# Package stubs need __path__ pointing to real dirs for submodule resolution
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PACKAGES = {
    "sqlalchemy": [],
    "sqlalchemy.ext": [],
    "models": [],
    "core": [],
    "services": [os.path.join(_backend_dir, "services")],
    "services.integration": [os.path.join(_backend_dir, "services", "integration")],
    "services.integration.handlers": [os.path.join(_backend_dir, "services", "integration", "handlers")],
}

for _mod_name in _needed:
    if _mod_name not in sys.modules:
        _stubs[_mod_name] = types.ModuleType(_mod_name)
        if _mod_name in _PACKAGES:
            _stubs[_mod_name].__path__ = _PACKAGES[_mod_name]
        sys.modules[_mod_name] = _stubs[_mod_name]

# Provide minimal objects
_sqlmodel = sys.modules["sqlmodel"]
_sqlmodel.select = MagicMock()

_async_mod = sys.modules["sqlalchemy.ext.asyncio"]
_async_mod.AsyncSession = MagicMock()


from enum import Enum

class _FakeEcommercePlatform(str, Enum):
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for _key, _attr in [
    ("models.integration", "Integration"),
    ("models.integration", "EcommercePlatform"),
    ("core.encryption", "decrypt_token"),
    ("services.integration.models", "ExternalProduct"),
    ("services.integration.base", "EcommerceService"),
    ("services.integration.shopify_service", "ShopifyService"),
    ("services.integration.woocommerce_service", "WooCommerceService"),
    ("services.integration.repositories", "ProductRepository"),
    ("services.integration.repositories", "LinkRepository"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)

sys.modules["models.integration"].Integration = MagicMock
sys.modules["models.integration"].EcommercePlatform = _FakeEcommercePlatform
sys.modules["core.encryption"].decrypt_token = MagicMock(return_value="test-token")

# Provide ExternalProduct
class _FakeExternalProduct:
    def __init__(self, **kw):
        self.id = kw.get("id", "ext-1")
        self.title = kw.get("title", "Widget")
        self.sku = kw.get("sku", None)
        self.price = kw.get("price", 19.99)
        self.compare_at_price = kw.get("compare_at_price", None)
        self.variants = kw.get("variants", None)


sys.modules["services.integration.models"].ExternalProduct = _FakeExternalProduct

# Provide EcommerceService, ShopifyService, WooCommerceService
sys.modules["services.integration.base"].EcommerceService = MagicMock
sys.modules["services.integration.shopify_service"].ShopifyService = MagicMock
sys.modules["services.integration.woocommerce_service"].WooCommerceService = MagicMock

# Provide repositories
sys.modules["services.integration.repositories"].ProductRepository = MagicMock
sys.modules["services.integration.repositories"].LinkRepository = MagicMock

# --- import under test ---
from services.integration.handlers.product_sync_handler import (
    ProductSyncHandler,
    SyncError,
)

# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]
# Restore overwritten attributes on pre-existing modules
for (_mod_key, _attr_name), _orig_val in _saved_attrs.items():
    if _mod_key in sys.modules:
        if _orig_val is _SENTINEL:
            try:
                delattr(sys.modules[_mod_key], _attr_name)
            except AttributeError:
                pass
        else:
            setattr(sys.modules[_mod_key], _attr_name, _orig_val)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_handler():
    db = AsyncMock()
    product_repo = AsyncMock()
    link_repo = AsyncMock()
    handler = ProductSyncHandler(db, product_repo, link_repo)
    return handler, db, product_repo, link_repo


def _make_integration(**kw):
    integ = MagicMock()
    integ.id = kw.get("id", uuid4())
    integ.user_id = kw.get("user_id", uuid4())
    integ.platform = kw.get("platform", _FakeEcommercePlatform.SHOPIFY)
    integ.store_url = kw.get("store_url", "myshop.myshopify.com")
    integ.access_token_encrypted = kw.get("access_token_encrypted", "enc-token")
    integ.sync_cursor = kw.get("sync_cursor", None)
    return integ


def _make_sync_result(products=None, has_more=False, next_cursor=None, success=True, error=None):
    r = MagicMock()
    r.success = success
    r.error = error
    r.products = products or []
    r.has_more = has_more
    r.next_cursor = next_cursor
    return r


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_stores_deps(self):
        handler, db, prod_repo, link_repo = _make_handler()
        assert handler.db is db
        assert handler.product_repo is prod_repo
        assert handler.link_repo is link_repo


class TestGetService:
    def test_shopify(self):
        # Clear cache
        ProductSyncHandler._services = {}
        with patch.dict("sys.modules", {"services.integration.shopify_service": MagicMock()}):
            service = ProductSyncHandler.get_service(_FakeEcommercePlatform.SHOPIFY)
            assert service is not None

    def test_unsupported_platform_raises(self):
        ProductSyncHandler._services = {}
        with pytest.raises(ValueError, match="Unsupported"):
            ProductSyncHandler.get_service("unknown_platform")

    def test_caches_service(self):
        ProductSyncHandler._services = {}
        s1 = ProductSyncHandler.get_service(_FakeEcommercePlatform.SHOPIFY)
        s2 = ProductSyncHandler.get_service(_FakeEcommercePlatform.SHOPIFY)
        assert s1 is s2


class TestGenerateSku:
    def test_uses_external_sku_when_present(self):
        handler, *_ = _make_handler()
        ext = _FakeExternalProduct(sku="EXT-SKU-1")
        result = handler._generate_sku(_FakeEcommercePlatform.SHOPIFY, ext)
        assert result == "EXT-SKU-1"

    def test_generates_default_when_no_sku(self):
        handler, *_ = _make_handler()
        ext = _FakeExternalProduct(id="12345", sku=None)
        result = handler._generate_sku(_FakeEcommercePlatform.SHOPIFY, ext)
        assert "12345" in result
        assert "SHOPIFY" in result


class TestUpsertProduct:
    @pytest.mark.asyncio
    async def test_updates_when_link_exists(self):
        handler, db, prod_repo, link_repo = _make_handler()
        existing_link = MagicMock(product_id=uuid4())
        link_repo.find_by_external_id = AsyncMock(return_value=existing_link)
        
        product = MagicMock()
        prod_repo.find_by_id = AsyncMock(return_value=product)
        prod_repo.update = AsyncMock(return_value=product)
        link_repo.update_prices = AsyncMock()

        integration = _make_integration()
        ext = _FakeExternalProduct()

        c, u = await handler.upsert_product(integration, ext)
        assert c == 0
        assert u == 1

    @pytest.mark.asyncio
    async def test_creates_when_no_link(self):
        handler, db, prod_repo, link_repo = _make_handler()
        link_repo.find_by_external_id = AsyncMock(return_value=None)
        prod_repo.find_by_sku = AsyncMock(return_value=None)
        new_product = MagicMock(id=uuid4())
        prod_repo.create = AsyncMock(return_value=new_product)
        link_repo.create = AsyncMock()

        integration = _make_integration()
        ext = _FakeExternalProduct()

        c, u = await handler.upsert_product(integration, ext)
        assert c == 1
        assert u == 0


class TestUpdateExisting:
    @pytest.mark.asyncio
    async def test_updates_product_and_link(self):
        handler, db, prod_repo, link_repo = _make_handler()
        product = MagicMock(sku="OLD", current_price=10.0)
        prod_repo.find_by_id = AsyncMock(return_value=product)
        prod_repo.update = AsyncMock(return_value=product)
        link_repo.update_prices = AsyncMock()

        link = MagicMock(product_id=uuid4())
        ext = _FakeExternalProduct(title="New Name", price=25.0)

        c, u = await handler._update_existing(link, ext)
        assert c == 0
        assert u == 1
        prod_repo.update.assert_awaited_once()
        link_repo.update_prices.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_product_not_found(self):
        handler, db, prod_repo, link_repo = _make_handler()
        prod_repo.find_by_id = AsyncMock(return_value=None)

        link = MagicMock(product_id=uuid4())
        ext = _FakeExternalProduct()

        c, u = await handler._update_existing(link, ext)
        assert c == 0
        assert u == 0


class TestCreateOrLink:
    @pytest.mark.asyncio
    async def test_links_to_existing_product_by_sku(self):
        handler, db, prod_repo, link_repo = _make_handler()
        existing = MagicMock(id=uuid4())
        prod_repo.find_by_sku = AsyncMock(return_value=existing)
        link_repo.create = AsyncMock()

        integration = _make_integration()
        ext = _FakeExternalProduct(sku="EXISTING-SKU")

        c, u = await handler._create_or_link(integration, ext)
        assert c == 0
        assert u == 1  # counted as update since product existed
        link_repo.create.assert_awaited_once()
        prod_repo.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_new_product_and_link(self):
        handler, db, prod_repo, link_repo = _make_handler()
        prod_repo.find_by_sku = AsyncMock(return_value=None)
        new_product = MagicMock(id=uuid4())
        prod_repo.create = AsyncMock(return_value=new_product)
        link_repo.create = AsyncMock()

        integration = _make_integration()
        ext = _FakeExternalProduct(price=30.0)

        c, u = await handler._create_or_link(integration, ext)
        assert c == 1
        assert u == 0
        prod_repo.create.assert_awaited_once()
        link_repo.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_uses_variant_id_when_available(self):
        handler, db, prod_repo, link_repo = _make_handler()
        prod_repo.find_by_sku = AsyncMock(return_value=None)
        new_product = MagicMock(id=uuid4())
        prod_repo.create = AsyncMock(return_value=new_product)
        link_repo.create = AsyncMock()

        integration = _make_integration()
        variant = MagicMock(id="var-1")
        ext = _FakeExternalProduct(variants=[variant])

        await handler._create_or_link(integration, ext)
        call_kw = link_repo.create.call_args[1]
        assert call_kw["external_variant_id"] == "var-1"


class TestSyncAllProducts:
    @pytest.mark.asyncio
    async def test_single_page_sync(self):
        handler, db, prod_repo, link_repo = _make_handler()
        ext = _FakeExternalProduct(id="ext-1")
        sync_result = _make_sync_result(products=[ext], has_more=False)

        mock_service = AsyncMock()
        mock_service.fetch_products = AsyncMock(return_value=sync_result)

        # Mock upsert
        handler.upsert_product = AsyncMock(return_value=(1, 0))

        with patch.object(ProductSyncHandler, "get_service", return_value=mock_service):
            with patch("services.integration.handlers.product_sync_handler.decrypt_token", return_value="token"):
                integration = _make_integration()
                c, u, d = await handler.sync_all_products(integration, "full")

        assert c == 1
        assert u == 0

    @pytest.mark.asyncio
    async def test_raises_on_fetch_failure(self):
        handler, db, prod_repo, link_repo = _make_handler()
        sync_result = _make_sync_result(success=False, error="Network error")

        mock_service = AsyncMock()
        mock_service.fetch_products = AsyncMock(return_value=sync_result)

        with patch.object(ProductSyncHandler, "get_service", return_value=mock_service):
            with patch("services.integration.handlers.product_sync_handler.decrypt_token", return_value="token"):
                integration = _make_integration()
                with pytest.raises(SyncError, match="Failed to fetch"):
                    await handler.sync_all_products(integration, "full")

    @pytest.mark.asyncio
    async def test_incremental_uses_cursor(self):
        handler, db, prod_repo, link_repo = _make_handler()
        sync_result = _make_sync_result(products=[], has_more=False)

        mock_service = AsyncMock()
        mock_service.fetch_products = AsyncMock(return_value=sync_result)

        with patch.object(ProductSyncHandler, "get_service", return_value=mock_service):
            with patch("services.integration.handlers.product_sync_handler.decrypt_token", return_value="token"):
                integration = _make_integration(sync_cursor="page-2")
                await handler.sync_all_products(integration, "incremental")

        # Verify cursor was passed
        call_kw = mock_service.fetch_products.call_args[1]
        assert call_kw["cursor"] == "page-2"

    @pytest.mark.asyncio
    async def test_full_sync_handles_deletions(self):
        handler, db, prod_repo, link_repo = _make_handler()
        ext = _FakeExternalProduct(id="ext-1")
        sync_result = _make_sync_result(products=[ext], has_more=False)

        mock_service = AsyncMock()
        mock_service.fetch_products = AsyncMock(return_value=sync_result)
        handler.upsert_product = AsyncMock(return_value=(1, 0))
        link_repo.disable_missing = AsyncMock(return_value=2)

        with patch.object(ProductSyncHandler, "get_service", return_value=mock_service):
            with patch("services.integration.handlers.product_sync_handler.decrypt_token", return_value="token"):
                integration = _make_integration()
                c, u, d = await handler.sync_all_products(integration, "full")

        assert d == 2
        link_repo.disable_missing.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_incremental_skips_deletions(self):
        handler, db, prod_repo, link_repo = _make_handler()
        sync_result = _make_sync_result(products=[], has_more=False)

        mock_service = AsyncMock()
        mock_service.fetch_products = AsyncMock(return_value=sync_result)

        with patch.object(ProductSyncHandler, "get_service", return_value=mock_service):
            with patch("services.integration.handlers.product_sync_handler.decrypt_token", return_value="token"):
                integration = _make_integration()
                c, u, d = await handler.sync_all_products(integration, "incremental")

        assert d == 0
        link_repo.disable_missing.assert_not_awaited()


        