"""
Tests for services.integration.price_push_service
"""

import sys
import types
import asyncio
from enum import Enum
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
    "models", "models.integration", "models.product",
    "core", "core.encryption",
    "services.integration.models",
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


class _FakeEcommercePlatform(str, Enum):
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


class _FakePriceUpdateResult:
    SUCCESS = "success"
    FAILED = "failed"
    UNAUTHORIZED = "unauthorized"
    PRODUCT_NOT_FOUND = "product_not_found"
    RATE_LIMITED = "rate_limited"

    def __init__(self, val):
        self._val = val

    @property
    def value(self):
        return self._val


# Make enum-like constants have a .value
for attr in ("SUCCESS", "FAILED", "UNAUTHORIZED", "PRODUCT_NOT_FOUND", "RATE_LIMITED"):
    setattr(_FakePriceUpdateResult, attr, _FakePriceUpdateResult(attr.lower()))


# Fake model classes with class-level attrs for SQLAlchemy .where()/.join()
class _FakeIntegrationModel:
    id = MagicMock()
    user_id = MagicMock()
    status = MagicMock()


class _FakeProductIntegrationLink:
    integration_id = MagicMock()
    product_id = MagicMock()
    sync_enabled = MagicMock()


class _FakeProductModel:
    id = MagicMock()
    user_id = MagicMock()


# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for _key, _attr in [
    ("models.integration", "Integration"),
    ("models.integration", "ProductIntegrationLink"),
    ("models.integration", "IntegrationStatus"),
    ("models.integration", "EcommercePlatform"),
    ("models.product", "Product"),
    ("core.encryption", "decrypt_token"),
    ("services.integration.models", "PriceUpdateRequest"),
    ("services.integration.models", "PriceUpdateResult"),
    ("services.integration.models", "PriceUpdateResponse"),
    ("services.integration.sync_service", "SyncService"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)

_integ_mod = sys.modules["models.integration"]
_integ_mod.Integration = _FakeIntegrationModel
_integ_mod.ProductIntegrationLink = _FakeProductIntegrationLink
_integ_mod.IntegrationStatus = _FakeIntegrationStatus
_integ_mod.EcommercePlatform = _FakeEcommercePlatform

sys.modules["models.product"].Product = _FakeProductModel
sys.modules["core.encryption"].decrypt_token = MagicMock(return_value="decrypted-token")

_models_mod = sys.modules["services.integration.models"]
_models_mod.PriceUpdateRequest = MagicMock
_models_mod.PriceUpdateResult = _FakePriceUpdateResult
_models_mod.PriceUpdateResponse = MagicMock

_sync_mod = sys.modules["services.integration.sync_service"]
_sync_mod.SyncService = lambda *a, **kw: AsyncMock()

# --- import under test ---
from services.integration.price_push_service import PricePushService

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

def _make_service(db=None):
    db = db or AsyncMock()
    return PricePushService(db), db


def _make_integration(**kw):
    integ = MagicMock()
    integ.id = kw.get("id", uuid4())
    integ.user_id = kw.get("user_id", uuid4())
    integ.platform = kw.get("platform", _FakeEcommercePlatform.SHOPIFY)
    integ.store_url = kw.get("store_url", "myshop.myshopify.com")
    integ.access_token_encrypted = "enc-token"
    integ.status = _FakeIntegrationStatus.ACTIVE
    return integ


def _db_returns_scalars_first(db, value):
    """Configure db.execute to return value via scalars().first()"""
    scalars = MagicMock()
    scalars.first.return_value = value
    result = MagicMock()
    result.scalars.return_value = scalars
    db.execute = AsyncMock(return_value=result)
    return db


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_stores_db(self):
        svc, db = _make_service()
        assert svc.db is db

    def test_timeout_constant(self):
        assert PricePushService.PUSH_TIMEOUT_SECONDS == 30


class TestGetIntegration:
    @pytest.mark.asyncio
    async def test_returns_integration(self):
        svc, db = _make_service()
        integ = _make_integration()
        _db_returns_scalars_first(db, integ)

        result = await svc._get_integration(integ.id, integ.user_id)
        assert result is integ

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        svc, db = _make_service()
        _db_returns_scalars_first(db, None)

        with pytest.raises(ValueError, match="not found"):
            await svc._get_integration(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_inactive_raises(self):
        svc, db = _make_service()
        integ = _make_integration()
        integ.status = "inactive"
        _db_returns_scalars_first(db, integ)

        with pytest.raises(ValueError, match="not active"):
            await svc._get_integration(integ.id, None)


class TestPushPriceToPlatform:
    @pytest.mark.asyncio
    async def test_integration_not_found_returns_error(self):
        svc, db = _make_service()
        svc._get_integration = AsyncMock(side_effect=ValueError("Integration not found"))

        result = await svc.push_price_to_platform(uuid4(), uuid4(), 19.99)
        assert result["success"] is False
        assert result["error_code"] == "INTEGRATION_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_integration_not_active_returns_error(self):
        svc, db = _make_service()
        svc._get_integration = AsyncMock(side_effect=ValueError("Integration is not active"))

        result = await svc.push_price_to_platform(uuid4(), uuid4(), 19.99)
        assert result["success"] is False
        assert result["error_code"] == "INTEGRATION_INACTIVE"

    @pytest.mark.asyncio
    async def test_missing_link_returns_error(self):
        svc, db = _make_service()
        integ = _make_integration()
        svc._get_integration = AsyncMock(return_value=integ)

        # First execute returns no enabled link, second returns no disabled link
        calls = [MagicMock(), MagicMock()]
        calls[0].scalars.return_value.first.return_value = None  # enabled
        calls[1].scalars.return_value.first.return_value = None  # disabled check
        db.execute = AsyncMock(side_effect=calls)

        result = await svc.push_price_to_platform(integ.id, uuid4(), 19.99)
        assert result["success"] is False
        assert result["error_code"] == "MISSING_INTEGRATION_LINK"

    @pytest.mark.asyncio
    async def test_sync_disabled_returns_error(self):
        svc, db = _make_service()
        integ = _make_integration()
        svc._get_integration = AsyncMock(return_value=integ)

        # First: no enabled link; second: disabled link exists
        disabled_link = MagicMock(sync_enabled=False)
        calls = [MagicMock(), MagicMock()]
        calls[0].scalars.return_value.first.return_value = None
        calls[1].scalars.return_value.first.return_value = disabled_link
        db.execute = AsyncMock(side_effect=calls)

        result = await svc.push_price_to_platform(integ.id, uuid4(), 19.99)
        assert result["success"] is False
        assert result["error_code"] == "SYNC_DISABLED"

    @pytest.mark.asyncio
    async def test_credential_error(self):
        svc, db = _make_service()
        integ = _make_integration()
        svc._get_integration = AsyncMock(return_value=integ)

        link = MagicMock(external_product_id="ext-1", external_variant_id="var-1", sync_enabled=True)
        _db_returns_scalars_first(db, link)

        with patch("services.integration.price_push_service.decrypt_token", side_effect=RuntimeError("bad key")):
            with patch("services.integration.price_push_service.SyncService") as mock_sync:
                mock_sync.get_service = MagicMock()
                result = await svc.push_price_to_platform(integ.id, uuid4(), 19.99)

        assert result["success"] is False
        assert result["error_code"] == "CREDENTIAL_ERROR"


class TestCheckProductCanPush:
    @pytest.mark.asyncio
    async def test_no_active_integration(self):
        svc, db = _make_service()
        scalars = MagicMock()
        scalars.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        result = await svc.check_product_can_push(uuid4(), uuid4())
        assert result["ready"] is False
        assert result["error_code"] == "NO_ACTIVE_INTEGRATION"

    @pytest.mark.asyncio
    async def test_missing_link(self):
        svc, db = _make_service()
        integ = _make_integration()

        # First call: integrations; second call: no link
        calls = [MagicMock(), MagicMock()]
        calls[0].scalars.return_value.all.return_value = [integ]
        calls[1].scalars.return_value.first.return_value = None
        db.execute = AsyncMock(side_effect=calls)

        result = await svc.check_product_can_push(uuid4(), uuid4())
        assert result["ready"] is False
        assert result["error_code"] == "MISSING_INTEGRATION_LINK"

    @pytest.mark.asyncio
    async def test_sync_disabled(self):
        svc, db = _make_service()
        integ = _make_integration()
        link = MagicMock(sync_enabled=False, integration_id=integ.id)

        calls = [MagicMock(), MagicMock()]
        calls[0].scalars.return_value.all.return_value = [integ]
        calls[1].scalars.return_value.first.return_value = link
        db.execute = AsyncMock(side_effect=calls)

        result = await svc.check_product_can_push(uuid4(), uuid4())
        assert result["ready"] is False
        assert result["error_code"] == "SYNC_DISABLED"

    @pytest.mark.asyncio
    async def test_ready(self):
        svc, db = _make_service()
        integ = _make_integration()
        link = MagicMock(
            sync_enabled=True,
            integration_id=integ.id,
            external_product_id="ext-1",
            last_price_push_at=None,
            external_price=19.99,
        )

        calls = [MagicMock(), MagicMock()]
        calls[0].scalars.return_value.all.return_value = [integ]
        calls[1].scalars.return_value.first.return_value = link
        db.execute = AsyncMock(side_effect=calls)

        result = await svc.check_product_can_push(uuid4(), uuid4())
        assert result["ready"] is True
        assert "integration_id" in result


