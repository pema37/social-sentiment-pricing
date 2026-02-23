"""
Tests for services.integration.repositories.link_repo
"""

import sys
import types
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ---------------------------------------------------------------------------
# Stub heavy external deps
# ---------------------------------------------------------------------------
_stubs: dict[str, types.ModuleType] = {}

for _mod_name in (
    "sqlalchemy", "sqlalchemy.ext", "sqlalchemy.ext.asyncio",
    "sqlmodel",
    "models", "models.integration",
):
    if _mod_name not in sys.modules:
        _stubs[_mod_name] = types.ModuleType(_mod_name)
        sys.modules[_mod_name] = _stubs[_mod_name]

_sqlmodel = sys.modules["sqlmodel"]
_sqlmodel.select = MagicMock()

_async_mod = sys.modules["sqlalchemy.ext.asyncio"]
_async_mod.AsyncSession = MagicMock()


class _FakeLink:
    # Class-level attrs for SQLAlchemy-style column comparisons
    id = MagicMock()
    integration_id = MagicMock()
    external_product_id = MagicMock()
    external_variant_id = MagicMock()
    sync_enabled = MagicMock()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


sys.modules["models.integration"].ProductIntegrationLink = _FakeLink

# --- import under test ---
from services.integration.repositories.link_repo import LinkRepository, utc_now

# Restore
for _name, _mod in _stubs.items():
    if _name in sys.modules and sys.modules[_name] is _mod:
        del sys.modules[_name]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_repo(db=None):
    db = db or AsyncMock()
    return LinkRepository(db), db


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInit:
    def test_stores_db(self):
        repo, db = _make_repo()
        assert repo.db is db


class TestUtcNow:
    def test_returns_datetime(self):
        assert isinstance(utc_now(), datetime)


class TestFindByExternalId:
    @pytest.mark.asyncio
    async def test_returns_link(self):
        repo, db = _make_repo()
        link = _FakeLink(id=uuid4(), external_product_id="ext-1")
        scalars = MagicMock()
        scalars.first.return_value = link
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        result = await repo.find_by_external_id(uuid4(), "ext-1")
        assert result is link

    @pytest.mark.asyncio
    async def test_returns_none(self):
        repo, db = _make_repo()
        scalars = MagicMock()
        scalars.first.return_value = None
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        result = await repo.find_by_external_id(uuid4(), "nope")
        assert result is None


class TestFindActiveByIntegration:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        repo, db = _make_repo()
        links = [_FakeLink(id=uuid4()), _FakeLink(id=uuid4())]
        scalars = MagicMock()
        scalars.all.return_value = links
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        result = await repo.find_active_by_integration(uuid4())
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list(self):
        repo, db = _make_repo()
        scalars = MagicMock()
        scalars.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        result = await repo.find_active_by_integration(uuid4())
        assert result == []


class TestCountActive:
    @pytest.mark.asyncio
    async def test_counts_active_links(self):
        repo, db = _make_repo()
        result_mock = MagicMock()
        result_mock.scalar.return_value = 3
        db.execute = AsyncMock(return_value=result_mock)

        result = await repo.count_active(uuid4())
        assert result == 3

    @pytest.mark.asyncio
    async def test_zero_when_none(self):
        repo, db = _make_repo()
        result_mock = MagicMock()
        result_mock.scalar.return_value = 0
        db.execute = AsyncMock(return_value=result_mock)

        result = await repo.count_active(uuid4())
        assert result == 0


class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_link(self):
        repo, db = _make_repo()

        result = await repo.create(
            product_id=uuid4(),
            integration_id=uuid4(),
            external_product_id="ext-1",
            external_variant_id="var-1",
            external_price=19.99,
            external_compare_at_price=24.99,
        )

        db.add.assert_called_once()
        db.commit.assert_not_awaited()
        db.refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_with_none_variant(self):
        repo, db = _make_repo()

        await repo.create(
            product_id=uuid4(),
            integration_id=uuid4(),
            external_product_id="ext-2",
            external_variant_id=None,
            external_price=None,
            external_compare_at_price=None,
        )
        db.add.assert_called_once()


class TestUpdatePrices:
    @pytest.mark.asyncio
    async def test_updates_prices(self):
        repo, db = _make_repo()
        link = _FakeLink(
            id=uuid4(),
            external_price=10.0,
            external_compare_at_price=None,
            last_price_pull_at=None,
            updated_at=None,
        )

        result = await repo.update_prices(link, external_price=15.0, external_compare_at_price=20.0)
        assert link.external_price == 15.0
        assert link.external_compare_at_price == 20.0
        assert link.last_price_pull_at is not None
        assert link.updated_at is not None
        db.add.assert_called_once()
        db.commit.assert_not_awaited()
        db.refresh.assert_not_awaited()


class TestDisableSync:
    @pytest.mark.asyncio
    async def test_disables_sync(self):
        repo, db = _make_repo()
        link = _FakeLink(id=uuid4(), sync_enabled=True, updated_at=None)

        result = await repo.disable_sync(link)
        assert link.sync_enabled is False
        assert link.updated_at is not None
        db.add.assert_called_once()
        db.commit.assert_awaited_once()


class TestDisableMissing:
    @pytest.mark.asyncio
    async def test_disables_missing_links(self):
        repo, db = _make_repo()
        int_id = uuid4()

        link_a = _FakeLink(id=uuid4(), external_product_id="ext-1", external_variant_id=None, sync_enabled=True, updated_at=None)
        link_b = _FakeLink(id=uuid4(), external_product_id="ext-2", external_variant_id=None, sync_enabled=True, updated_at=None)
        link_c = _FakeLink(id=uuid4(), external_product_id="ext-3", external_variant_id=None, sync_enabled=True, updated_at=None)

        scalars = MagicMock()
        scalars.all.return_value = [link_a, link_b, link_c]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        # Only ext-1 was seen — ext-2 and ext-3 should be disabled
        # Now uses (external_product_id, external_variant_id) tuples
        count = await repo.disable_missing(int_id, {("ext-1", None)})
        assert count == 2
        assert link_a.sync_enabled is True
        assert link_b.sync_enabled is False
        assert link_c.sync_enabled is False
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_zero_when_all_seen(self):
        repo, db = _make_repo()
        link = _FakeLink(id=uuid4(), external_product_id="ext-1", external_variant_id=None, sync_enabled=True, updated_at=None)

        scalars = MagicMock()
        scalars.all.return_value = [link]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        count = await repo.disable_missing(uuid4(), {("ext-1", None)})
        assert count == 0
        # No commit needed when nothing changed
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_zero_when_no_links(self):
        repo, db = _make_repo()
        scalars = MagicMock()
        scalars.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars
        db.execute = AsyncMock(return_value=result_mock)

        count = await repo.disable_missing(uuid4(), {"ext-1"})
        assert count == 0



        