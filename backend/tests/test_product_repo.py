"""
Tests for services.integration.repositories.product_repo
"""

import sys
import types
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Stub heavy external deps before importing the module under test
# ---------------------------------------------------------------------------
_stubs: dict[str, types.ModuleType] = {}

for _mod_name in (
    "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlmodel",
    "models", "models.product",
):
    if _mod_name not in sys.modules:
        _stubs[_mod_name] = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _stubs[_mod_name]

# Provide select & AsyncSession
_sqlmodel = sys.modules["sqlmodel"]
_sqlmodel.select = MagicMock()

_async_mod = sys.modules["sqlalchemy.ext.asyncio"]
_async_mod.AsyncSession = MagicMock()

# Provide Product model
class _FakeProduct:
    # Class-level attrs for SQLAlchemy-style column comparisons
    # (e.g. Product.user_id == some_value in .where() clauses)
    user_id = MagicMock()
    sku = MagicMock()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

sys.modules["models.product"].Product = _FakeProduct

# --- import under test ---
from services.integration.repositories.product_repo import ProductRepository, utc_now

# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_db():
    db = AsyncMock()
    return db


def _make_repo(db=None):
    db = db or _make_db()
    return ProductRepository(db), db


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_stores_db(self):
        repo, db = _make_repo()
        assert repo.db is db


class TestUtcNow:
    def test_returns_datetime(self):
        result = utc_now()
        assert isinstance(result, datetime)


class TestFindById:
    @pytest.mark.asyncio
    async def test_returns_product(self):
        repo, db = _make_repo()
        product = _FakeProduct(id=uuid4(), name="Widget")
        db.get = AsyncMock(return_value=product)

        result = await repo.find_by_id(product.id)
        assert result is product
        db.get.assert_awaited_once_with(_FakeProduct, product.id)

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        repo, db = _make_repo()
        db.get = AsyncMock(return_value=None)

        result = await repo.find_by_id(uuid4())
        assert result is None


class TestFindBySku:
    @pytest.mark.asyncio
    async def test_returns_product(self):
        repo, db = _make_repo()
        product = _FakeProduct(id=uuid4(), sku="ABC-123")
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = product
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        db.execute = AsyncMock(return_value=result_mock)

        result = await repo.find_by_sku(uuid4(), "ABC-123")
        assert result is product

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        repo, db = _make_repo()
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = None
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        db.execute = AsyncMock(return_value=result_mock)

        result = await repo.find_by_sku(uuid4(), "NOPE")
        assert result is None


class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_and_returns_product(self):
        repo, db = _make_repo()
        uid = uuid4()

        result = await repo.create(
            user_id=uid,
            name="Widget",
            sku="W-001",
            base_price=10.0,
            current_price=12.0,
            description="Nice",
            category="Gadgets",
            image_url="https://img.png",
        )

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_creates_with_defaults(self):
        repo, db = _make_repo()

        result = await repo.create(
            user_id=uuid4(),
            name="Basic",
            sku="B-001",
            base_price=5.0,
            current_price=5.0,
        )
        # Should still call add/commit/refresh
        db.add.assert_called_once()
        db.commit.assert_awaited_once()


class TestUpdate:
    @pytest.mark.asyncio
    async def test_updates_name(self):
        repo, db = _make_repo()
        product = _FakeProduct(id=uuid4(), name="Old", sku="S", current_price=10.0, updated_at=None)

        result = await repo.update(product, name="New")
        assert product.name == "New"
        assert product.sku == "S"  # unchanged
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_updates_sku(self):
        repo, db = _make_repo()
        product = _FakeProduct(id=uuid4(), name="W", sku="OLD", current_price=10.0, updated_at=None)

        await repo.update(product, sku="NEW")
        assert product.sku == "NEW"

    @pytest.mark.asyncio
    async def test_updates_current_price(self):
        repo, db = _make_repo()
        product = _FakeProduct(id=uuid4(), name="W", sku="S", current_price=10.0, updated_at=None)

        await repo.update(product, current_price=20.0)
        assert product.current_price == 20.0

    @pytest.mark.asyncio
    async def test_sets_updated_at(self):
        repo, db = _make_repo()
        product = _FakeProduct(id=uuid4(), name="W", sku="S", current_price=10.0, updated_at=None)

        await repo.update(product, name="X")
        assert product.updated_at is not None
        assert isinstance(product.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_skips_none_fields(self):
        repo, db = _make_repo()
        product = _FakeProduct(id=uuid4(), name="W", sku="S", current_price=10.0, updated_at=None)

        await repo.update(product)
        assert product.name == "W"
        assert product.sku == "S"
        assert product.current_price == 10.0


        