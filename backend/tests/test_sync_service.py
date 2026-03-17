"""
Tests for services.integration.sync_service
"""

import sys
import types
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
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
    "sqlalchemy.sql",
    "sqlalchemy.sql.functions",
    "sqlmodel",
    "models",
    "models.integration",
    "models.product",
    "core",
    "core.encryption",
    "services.integration.base",
    "services.integration.models",
    "services.integration.circuit_breaker",
    "services.integration.shopify_service",
    "services.integration.woocommerce_service",
]

for _mod_name in _needed:
    if _mod_name not in sys.modules:
        _stubs[_mod_name] = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _stubs[_mod_name]

# Provide sqlalchemy.func
_sa = sys.modules["sqlalchemy"]
_sa.func = MagicMock()

_sqlmodel = sys.modules["sqlmodel"]
_sqlmodel.select = MagicMock()

_async_mod = sys.modules["sqlalchemy.ext.asyncio"]
_async_mod.AsyncSession = MagicMock()


class _FakeIntegrationStatus:
    ACTIVE = "active"
    ERROR = "error"


class _FakeEcommercePlatform:
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"


# ---------------------------------------------------------------------------
# Column mock that supports SQLAlchemy-style comparison operators
# ---------------------------------------------------------------------------
class _ColumnMock:
    """MagicMock can't handle <, >, <=, >= with real values like datetime.
    This mock returns a MagicMock for any comparison, just like SQLAlchemy
    column objects do when building .where() expressions."""

    def __lt__(self, other):
        return MagicMock()

    def __le__(self, other):
        return MagicMock()

    def __gt__(self, other):
        return MagicMock()

    def __ge__(self, other):
        return MagicMock()

    def __eq__(self, other):
        return MagicMock()

    def __ne__(self, other):
        return MagicMock()

    def __hash__(self):
        return id(self)


class _ColumnMock:
    def __lt__(self, other):
        return MagicMock()

    def __le__(self, other):
        return MagicMock()

    def __gt__(self, other):
        return MagicMock()

    def __ge__(self, other):
        return MagicMock()

    def __eq__(self, other):
        return MagicMock()

    def __ne__(self, other):
        return MagicMock()

    def __hash__(self):
        return id(self)

    def desc(self):
        return MagicMock()

    def asc(self):
        return MagicMock()


# --- Fake model classes: class-level attrs for SQLAlchemy .where()/.join() ---
# Instance attrs set in __init__ override on instances but class-level
# MagicMock attrs remain accessible on the *class* for query building.


class _FakeIntegration:
    # class-level for SQLAlchemy queries
    id = MagicMock()
    user_id = MagicMock()
    status = MagicMock()
    platform = MagicMock()
    sync_status = MagicMock()
    updated_at = _ColumnMock()

    def __init__(self, **kw):
        self.id = kw.get("id", uuid4())
        self.user_id = kw.get("user_id", uuid4())
        self.platform = kw.get("platform", _FakeEcommercePlatform.SHOPIFY)
        self.store_url = kw.get("store_url", "myshop.myshopify.com")
        self.access_token_encrypted = kw.get("access_token_encrypted", "enc")
        self.status = kw.get("status", _FakeIntegrationStatus.ACTIVE)
        self.sync_cursor = kw.get("sync_cursor", None)
        self.sync_status = kw.get("sync_status", "idle")
        self.last_sync_at = None
        self.products_synced = 0
        self.error_message = None


class _FakeSyncLog:
    # class-level for SQLAlchemy queries
    id = MagicMock()
    integration_id = MagicMock()
    started_at = _ColumnMock()  # needs <, > comparison support
    completed_at = MagicMock()
    success = MagicMock()

    def __init__(self, **kw):
        self.id = kw.get("id", uuid4())
        self.integration_id = kw.get("integration_id", uuid4())
        self.sync_type = kw.get("sync_type", "full")
        self.started_at = kw.get("started_at", datetime.now(UTC))
        self.completed_at = kw.get("completed_at", None)
        self.success = kw.get("success", None)
        self.products_created = 0
        self.products_updated = 0
        self.products_deleted = 0
        self.error_details = None
        self.duration_seconds = None


class _FakeLink:
    # class-level for SQLAlchemy queries
    id = MagicMock()
    integration_id = MagicMock()
    product_id = MagicMock()
    external_product_id = MagicMock()
    external_variant_id = MagicMock()
    sync_enabled = MagicMock()

    def __init__(self, **kw):
        self.id = kw.get("id", uuid4())
        self.product_id = kw.get("product_id", uuid4())
        self.integration_id = kw.get("integration_id", uuid4())
        self.external_product_id = kw.get("external_product_id", "ext-1")
        self.external_variant_id = kw.get("external_variant_id", None)
        self.external_price = kw.get("external_price", None)
        self.external_compare_at_price = kw.get("external_compare_at_price", None)
        self.sync_enabled = kw.get("sync_enabled", True)
        self.last_price_pull_at = None
        self.updated_at = None


# Save original attributes before overwriting
_SENTINEL = object()
_saved_attrs = {}
for _key, _attr in [
    ("models.integration", "Integration"),
    ("models.integration", "IntegrationSyncLog"),
    ("models.integration", "ProductIntegrationLink"),
    ("models.integration", "IntegrationStatus"),
    ("models.integration", "EcommercePlatform"),
    ("models.product", "Product"),
    ("core.encryption", "decrypt_token"),
    ("services.integration.models", "ExternalProduct"),
    ("services.integration.base", "EcommerceService"),
    ("services.integration.circuit_breaker", "CircuitOpenError"),
    ("services.integration.circuit_breaker", "circuit_breaker_registry"),
    ("services.integration.shopify_service", "ShopifyService"),
    ("services.integration.woocommerce_service", "WooCommerceService"),
]:
    if _key in sys.modules:
        _saved_attrs[(_key, _attr)] = getattr(sys.modules[_key], _attr, _SENTINEL)

_integ_mod = sys.modules["models.integration"]
_integ_mod.Integration = _FakeIntegration
_integ_mod.IntegrationSyncLog = _FakeSyncLog
_integ_mod.ProductIntegrationLink = _FakeLink
_integ_mod.IntegrationStatus = _FakeIntegrationStatus
_integ_mod.EcommercePlatform = _FakeEcommercePlatform


class _FakeProduct:
    # class-level for SQLAlchemy queries
    id = MagicMock()
    user_id = MagicMock()
    sku = MagicMock()

    def __init__(self, **kw):
        self.id = kw.get("id", uuid4())
        self.user_id = kw.get("user_id", uuid4())
        self.name = kw.get("name", "Widget")
        self.sku = kw.get("sku", "W-001")
        self.base_price = kw.get("base_price", 10.0)
        self.current_price = kw.get("current_price", 10.0)
        self.cost = None
        self.updated_at = None


sys.modules["models.product"].Product = _FakeProduct

sys.modules["core.encryption"].decrypt_token = MagicMock(return_value="test-token")


class _FakeExternalProduct:
    def __init__(self, **kw):
        self.id = kw.get("id", "ext-1")
        self.title = kw.get("title", "Widget")
        self.sku = kw.get("sku", None)
        self.price = kw.get("price", 19.99)
        self.compare_at_price = kw.get("compare_at_price", None)
        self.variants = kw.get("variants", None)


sys.modules["services.integration.models"].ExternalProduct = _FakeExternalProduct
sys.modules["services.integration.base"].EcommerceService = MagicMock

_cb_mod = sys.modules["services.integration.circuit_breaker"]
_cb_mod.CircuitOpenError = type("CircuitOpenError", (Exception,), {})
_cb_mod.circuit_breaker_registry = MagicMock()

sys.modules["services.integration.shopify_service"].ShopifyService = MagicMock
sys.modules["services.integration.woocommerce_service"].WooCommerceService = MagicMock

# --- import under test ---
from services.integration.sync_service import (
    SyncError,
    SyncService,
    SyncTemporarilyUnavailable,
    SyncTimeoutError,
    recover_stuck_syncs_async,
    run_product_sync,
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


def _make_service(db=None):
    db = db or AsyncMock()
    return SyncService(db), db


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_stores_db(self):
        svc, db = _make_service()
        assert svc.db is db

    def test_timeout_constant(self):
        assert SyncService.SYNC_TIMEOUT_SECONDS == 300

    def test_stuck_sync_timeout(self):
        assert SyncService.STUCK_SYNC_TIMEOUT_MINUTES == 15


class TestExceptions:
    def test_sync_error_is_exception(self):
        assert issubclass(SyncError, Exception)

    def test_sync_temporarily_unavailable(self):
        assert issubclass(SyncTemporarilyUnavailable, SyncError)

    def test_sync_timeout_error(self):
        assert issubclass(SyncTimeoutError, SyncError)


class TestGetService:
    def test_shopify(self):
        SyncService._services = {}
        service = SyncService.get_service(_FakeEcommercePlatform.SHOPIFY)
        assert service is not None

    def test_woocommerce(self):
        SyncService._services = {}
        service = SyncService.get_service(_FakeEcommercePlatform.WOOCOMMERCE)
        assert service is not None

    def test_unsupported_raises(self):
        SyncService._services = {}
        with pytest.raises(ValueError, match="Unsupported"):
            SyncService.get_service("unknown")

    def test_caches(self):
        SyncService._services = {}
        s1 = SyncService.get_service(_FakeEcommercePlatform.SHOPIFY)
        s2 = SyncService.get_service(_FakeEcommercePlatform.SHOPIFY)
        assert s1 is s2


class TestGetIntegration:
    @pytest.mark.asyncio
    async def test_returns_integration(self):
        svc, db = _make_service()
        integ = _FakeIntegration()
        scalars = MagicMock()
        scalars.first.return_value = integ
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        result = await svc._get_integration(integ.id, None)
        assert result is integ

    @pytest.mark.asyncio
    async def test_not_found_raises(self):
        svc, db = _make_service()
        scalars = MagicMock()
        scalars.first.return_value = None
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(ValueError, match="not found"):
            await svc._get_integration(uuid4(), None)

    @pytest.mark.asyncio
    async def test_inactive_raises(self):
        svc, db = _make_service()
        integ = _FakeIntegration(status="inactive")
        scalars = MagicMock()
        scalars.first.return_value = integ
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(ValueError, match="not active"):
            await svc._get_integration(integ.id, None)


class TestCreateSyncLog:
    @pytest.mark.asyncio
    async def test_creates_log(self):
        svc, db = _make_service()
        integ = _FakeIntegration()

        log = await svc._create_sync_log(integ, "full")
        assert log.sync_type == "full"
        assert integ.sync_status == "syncing"
        db.add.assert_called()
        db.commit.assert_awaited_once()


class TestFinalizeSuccess:
    @pytest.mark.asyncio
    async def test_updates_log_and_integration(self):
        svc, db = _make_service()
        integ = _FakeIntegration()
        log = _FakeSyncLog(started_at=datetime.now(UTC))

        # Mock _count_linked_products
        svc._count_linked_products = AsyncMock(return_value=5)

        await svc._finalize_success(integ, log, (3, 2, 1))
        assert log.success is True
        assert log.products_created == 3
        assert log.products_updated == 2
        assert log.products_deleted == 1
        assert integ.sync_status == "idle"
        assert integ.products_synced == 5
        assert integ.error_message is None
        db.commit.assert_awaited()


class TestFinalizeFailure:
    @pytest.mark.asyncio
    async def test_updates_log_and_integration(self):
        svc, db = _make_service()
        integ = _FakeIntegration()
        log = _FakeSyncLog(started_at=datetime.now(UTC))

        await svc._finalize_failure(integ, log, "Something broke")
        assert log.success is False
        assert log.error_details == "Something broke"
        assert integ.sync_status == "error"
        assert integ.error_message == "Something broke"
        db.commit.assert_awaited()


class TestUpsertProduct:
    @pytest.mark.asyncio
    async def test_updates_existing(self):
        svc, db = _make_service()
        integ = _FakeIntegration()
        link = _FakeLink(product_id=uuid4())
        product = _FakeProduct(id=link.product_id)

        # Find existing link
        scalars1 = MagicMock()
        scalars1.first.return_value = link
        result1 = MagicMock()
        result1.scalars.return_value = scalars1

        # Find product
        scalars2 = MagicMock()
        scalars2.first.return_value = product
        result2 = MagicMock()
        result2.scalars.return_value = scalars2

        db.execute = AsyncMock(side_effect=[result1, result2])

        ext = _FakeExternalProduct(title="Updated", price=25.0)
        c, u = await svc._upsert_product(integ, ext)
        assert c == 0
        assert u == 1

    @pytest.mark.asyncio
    async def test_creates_new(self):
        svc, db = _make_service()
        integ = _FakeIntegration()

        # No existing link
        scalars1 = MagicMock()
        scalars1.first.return_value = None
        result1 = MagicMock()
        result1.scalars.return_value = scalars1

        # No existing product by SKU
        scalars2 = MagicMock()
        scalars2.first.return_value = None
        result2 = MagicMock()
        result2.scalars.return_value = scalars2

        db.execute = AsyncMock(side_effect=[result1, result2])

        ext = _FakeExternalProduct(sku="NEW-SKU", price=15.0)
        c, u = await svc._upsert_product(integ, ext)
        assert c == 1
        assert u == 0


class TestHandleDeletions:
    @pytest.mark.asyncio
    async def test_disables_missing_links(self):
        svc, db = _make_service()
        integ = _FakeIntegration()

        link_a = _FakeLink(external_product_id="ext-1")
        link_b = _FakeLink(external_product_id="ext-2")
        link_c = _FakeLink(external_product_id="ext-3")

        scalars = MagicMock()
        scalars.all.return_value = [link_a, link_b, link_c]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        deleted = await svc._handle_deletions(integ, {("ext-1", None)})
        assert deleted == 2
        assert link_a.sync_enabled is True
        assert link_b.sync_enabled is False
        assert link_c.sync_enabled is False

    @pytest.mark.asyncio
    async def test_zero_when_all_seen(self):
        svc, db = _make_service()
        integ = _FakeIntegration()
        link = _FakeLink(external_product_id="ext-1")

        scalars = MagicMock()
        scalars.all.return_value = [link]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        deleted = await svc._handle_deletions(integ, {("ext-1", None)})
        assert deleted == 0


class TestCountLinkedProducts:
    @pytest.mark.asyncio
    async def test_counts(self):
        svc, db = _make_service()
        result_mock = MagicMock()
        result_mock.scalar.return_value = 2
        db.execute = AsyncMock(return_value=result_mock)

        count = await svc._count_linked_products(uuid4())
        assert count == 2


class TestRecoverStuckSyncs:
    @pytest.mark.asyncio
    async def test_recovers_stuck_sync(self):
        svc, db = _make_service()
        integ = _FakeIntegration(sync_status="syncing")
        stuck_log = _FakeSyncLog(
            integration_id=integ.id,
            started_at=datetime.now(UTC) - timedelta(minutes=30),
            completed_at=None,
        )

        # First query: integrations in syncing
        scalars1 = MagicMock()
        scalars1.all.return_value = [integ]
        result1 = MagicMock()
        result1.scalars.return_value = scalars1

        # Second query: stuck log
        scalars2 = MagicMock()
        scalars2.first.return_value = stuck_log
        result2 = MagicMock()
        result2.scalars.return_value = scalars2

        db.execute = AsyncMock(side_effect=[result1, result2])

        recovered = await svc.recover_stuck_syncs()
        assert recovered == 1
        assert integ.sync_status == "error"
        assert stuck_log.success is False
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_zero_when_none_stuck(self):
        svc, db = _make_service()
        scalars = MagicMock()
        scalars.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        recovered = await svc.recover_stuck_syncs()
        assert recovered == 0


class TestBackgroundFunctions:
    @pytest.mark.asyncio
    async def test_run_product_sync(self):
        db = AsyncMock()
        with patch.object(SyncService, "run_sync", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _FakeSyncLog()
            result = await run_product_sync(db, uuid4(), "full")
            mock_run.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_recover_stuck_syncs_async(self):
        db = AsyncMock()
        with patch.object(SyncService, "recover_stuck_syncs", new_callable=AsyncMock) as mock_recover:
            mock_recover.return_value = 2
            result = await recover_stuck_syncs_async(db)
            assert result == 2
