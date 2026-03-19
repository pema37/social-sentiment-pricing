"""
Tests for services.integration.product_sync_service
"""

import sys
import types
from decimal import Decimal
from enum import StrEnum
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Stub heavy external deps
# ---------------------------------------------------------------------------
_stubs: dict[str, types.ModuleType] = {}

_needed = [
    "sqlalchemy",
    "sqlalchemy.ext",
    "sqlalchemy.ext.asyncio",
    "sqlmodel",
    "models",
    "models.product",
    "models.integration",
    "core",
    "core.encryption",
]

for _mod_name in _needed:
    if _mod_name not in sys.modules:
        _stubs[_mod_name] = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _stubs[_mod_name]

_sqlmodel = sys.modules["sqlmodel"]
_sqlmodel.select = MagicMock()

_async_mod = sys.modules["sqlalchemy.ext.asyncio"]
_async_mod.AsyncSession = MagicMock()


# Fake model classes with class-level attrs for SQLAlchemy .where()/.join()
class _FakeProduct:
    id = MagicMock()
    user_id = MagicMock()
    is_active = MagicMock()


sys.modules["models.product"].Product = _FakeProduct


class _FakeIntegrationStatus:
    ACTIVE = "active"
    ERROR = "error"


class _FakeEcommercePlatform(StrEnum):
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


class _FakeIntegrationModel:
    id = MagicMock()
    user_id = MagicMock()
    status = MagicMock()
    platform = MagicMock()


class _FakeProductIntegrationLink:
    id = MagicMock()
    integration_id = MagicMock()
    product_id = MagicMock()
    sync_enabled = MagicMock()
    external_product_id = MagicMock()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


_integ_mod = sys.modules["models.integration"]
_integ_mod.Integration = _FakeIntegrationModel
_integ_mod.ProductIntegrationLink = _FakeProductIntegrationLink
_integ_mod.IntegrationStatus = _FakeIntegrationStatus
_integ_mod.EcommercePlatform = _FakeEcommercePlatform

sys.modules["core.encryption"].decrypt_token = MagicMock(return_value="key|secret")

# --- import under test ---
from services.integration.product_sync_service import ProductSyncService

# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_service(db=None):
    db = db or AsyncMock()
    return ProductSyncService(db), db


def _make_integration(**kw):
    integ = MagicMock()
    integ.id = kw.get("id", uuid4())
    integ.user_id = kw.get("user_id", uuid4())
    integ.platform = kw.get("platform", _FakeEcommercePlatform.WOOCOMMERCE)
    integ.store_url = kw.get("store_url", "https://mystore.com")
    integ.access_token_encrypted = "enc"
    integ.refresh_token_encrypted = None
    integ.status = _FakeIntegrationStatus.ACTIVE
    return integ


def _make_product(**kw):
    p = MagicMock()
    p.id = kw.get("id", uuid4())
    p.name = kw.get("name", "Widget")
    p.sku = kw.get("sku", "W-001")
    p.current_price = kw.get("current_price", Decimal("19.99"))
    p.description = kw.get("description", "A widget")
    p.category = kw.get("category", "Gadgets")
    p.is_active = kw.get("is_active", True)
    p.user_id = kw.get("user_id", uuid4())
    return p


def _db_scalars_first(db, value):
    scalars = MagicMock()
    scalars.first.return_value = value
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars
    db.execute = AsyncMock(return_value=result_mock)


def _db_scalars_all(db, values):
    scalars = MagicMock()
    scalars.all.return_value = values
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars
    db.execute = AsyncMock(return_value=result_mock)


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_stores_db(self):
        svc, db = _make_service()
        assert svc.db is db


class TestGetUserActiveIntegration:
    @pytest.mark.asyncio
    async def test_returns_integration(self):
        svc, db = _make_service()
        integ = _make_integration()
        _db_scalars_first(db, integ)

        result = await svc.get_user_active_integration(uuid4())
        assert result is integ

    @pytest.mark.asyncio
    async def test_returns_none(self):
        svc, db = _make_service()
        _db_scalars_first(db, None)

        result = await svc.get_user_active_integration(uuid4())
        assert result is None


class TestGetAllUserIntegrations:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        svc, db = _make_service()
        integrations = [_make_integration(), _make_integration()]
        _db_scalars_all(db, integrations)

        result = await svc.get_all_user_integrations(uuid4())
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty(self):
        svc, db = _make_service()
        _db_scalars_all(db, [])

        result = await svc.get_all_user_integrations(uuid4())
        assert result == []


class TestPushProductToStore:
    @pytest.mark.asyncio
    async def test_already_linked(self):
        svc, _db = _make_service()
        existing_link = MagicMock(id=uuid4(), external_product_id="ext-1")
        svc._get_existing_link = AsyncMock(return_value=existing_link)

        product = _make_product()
        integ = _make_integration()

        result = await svc.push_product_to_store(product, integ)
        assert result["success"] is True
        assert result["message"] == "Product already linked"

    @pytest.mark.asyncio
    async def test_unsupported_platform(self):
        svc, _db = _make_service()
        svc._get_existing_link = AsyncMock(return_value=None)

        product = _make_product()
        # Create a mock platform that has .value like a real enum
        fake_platform = MagicMock()
        fake_platform.value = "etsy"
        integ = _make_integration(platform=fake_platform)

        result = await svc.push_product_to_store(product, integ)
        assert result["success"] is False
        assert "Unsupported" in result["error"]

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        svc, _db = _make_service()
        svc._get_existing_link = AsyncMock(side_effect=RuntimeError("crash"))

        product = _make_product()
        integ = _make_integration()

        result = await svc.push_product_to_store(product, integ)
        assert result["success"] is False
        assert result["error_code"] == "PUSH_FAILED"


class TestGetExistingLink:
    @pytest.mark.asyncio
    async def test_returns_link(self):
        svc, db = _make_service()
        link = MagicMock()
        _db_scalars_first(db, link)

        result = await svc._get_existing_link(uuid4(), uuid4())
        assert result is link

    @pytest.mark.asyncio
    async def test_returns_none(self):
        svc, db = _make_service()
        _db_scalars_first(db, None)

        result = await svc._get_existing_link(uuid4(), uuid4())
        assert result is None


class TestCreateIntegrationLink:
    @pytest.mark.asyncio
    async def test_creates_link(self):
        svc, db = _make_service()

        await svc._create_integration_link(
            product_id=uuid4(),
            integration_id=uuid4(),
            external_product_id="ext-1",
            external_variant_id="var-1",
            external_price=19.99,
        )

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()


class TestSyncProductOnCreate:
    @pytest.mark.asyncio
    async def test_auto_push_disabled(self):
        svc, _db = _make_service()
        product = _make_product()

        result = await svc.sync_product_on_create(product, uuid4(), auto_push=False)
        assert result["synced"] is False
        assert result["reason"] == "auto_push disabled"

    @pytest.mark.asyncio
    async def test_no_integrations(self):
        svc, _db = _make_service()
        svc.get_all_user_integrations = AsyncMock(return_value=[])
        product = _make_product()

        result = await svc.sync_product_on_create(product, uuid4())
        assert result["synced"] is False
        assert result["reason"] == "no_active_integrations"

    @pytest.mark.asyncio
    async def test_pushes_to_all_integrations(self):
        svc, _db = _make_service()
        i1 = _make_integration()
        i2 = _make_integration()
        svc.get_all_user_integrations = AsyncMock(return_value=[i1, i2])
        svc.push_product_to_store = AsyncMock(return_value={"success": True, "external_product_id": "ext"})

        product = _make_product()
        result = await svc.sync_product_on_create(product, uuid4())
        assert result["synced"] is True
        assert result["integrations_count"] == 2
        assert len(result["results"]) == 2


class TestLinkExistingProduct:
    @pytest.mark.asyncio
    async def test_product_not_found(self):
        svc, db = _make_service()
        _db_scalars_first(db, None)

        result = await svc.link_existing_product(uuid4(), uuid4(), "ext-1")
        assert result["success"] is False
        assert "Product not found" in result["error"]

    @pytest.mark.asyncio
    async def test_integration_not_found(self):
        svc, db = _make_service()
        product = _make_product()
        # First call: product found; second call: integration not found
        calls = [MagicMock(), MagicMock()]
        calls[0].scalars.return_value.first.return_value = product
        calls[1].scalars.return_value.first.return_value = None
        db.execute = AsyncMock(side_effect=calls)

        result = await svc.link_existing_product(product.id, uuid4(), "ext-1")
        assert result["success"] is False
        assert "Integration not found" in result["error"]

    @pytest.mark.asyncio
    async def test_updates_existing_link(self):
        svc, db = _make_service()
        product = _make_product()
        integ = _make_integration()
        existing_link = MagicMock(id=uuid4())

        # First: product; second: integration; then _get_existing_link
        calls = [MagicMock(), MagicMock()]
        calls[0].scalars.return_value.first.return_value = product
        calls[1].scalars.return_value.first.return_value = integ
        db.execute = AsyncMock(side_effect=calls)
        svc._get_existing_link = AsyncMock(return_value=existing_link)

        result = await svc.link_existing_product(product.id, integ.id, "ext-1")
        assert result["success"] is True
        assert "Updated" in result["message"]


class TestBulkPushProducts:
    @pytest.mark.asyncio
    async def test_no_integrations(self):
        svc, _db = _make_service()
        svc.get_all_user_integrations = AsyncMock(return_value=[])

        result = await svc.bulk_push_products(uuid4())
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_no_products(self):
        svc, db = _make_service()
        integ = _make_integration()
        svc.get_all_user_integrations = AsyncMock(return_value=[integ])

        scalars = MagicMock()
        scalars.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        result = await svc.bulk_push_products(uuid4())
        assert result["pushed"] == 0
