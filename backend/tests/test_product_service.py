"""
Tests for services/products/product_service.py — ProductService

Covers:
- __init__: session stored
- create: builds Product, commits, refreshes, returns
- get_by_id: found, not found, ownership check
- list: pagination, filters (is_active, category), total count
- update: partial update, not found, sets updated_at
- delete: cascade delete, rollback on error, not found
- _fetch_competitor_prices: joins, skips invalid/high prices, maps to CompetitorPriceData
- get_price_suggestion: sentiment aggregation, competitor fetch, pricing engine call,
  data_source flags (both, competitor_only, sentiment_only, none)
"""

import sys
import os
from types import ModuleType
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session",
    "models.product", "models.user", "models.sentiment",
    "models.competitor_product", "models.competitor",
    "schemas.product",
    "services.pricing_engine",
    "services.products.cascade_delete",
    "sqlmodel",
]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

# Ensure db.session stub
for _m in ("db.session"):
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

# Compute real filesystem paths
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ensure parent packages with real paths
for _pkg, _subdir in [
    ("services", "services"),
    ("services.products", "services/products"),
    ("models", "models"),
    ("schemas", "schemas"),
]:
    if _pkg not in sys.modules:
        _mod = ModuleType(_pkg)
        _mod.__path__ = [os.path.join(_backend_dir, _subdir)]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod


# --- Stub models ---

class _ColumnMock:
    def __lt__(self, other): return MagicMock()
    def __le__(self, other): return MagicMock()
    def __gt__(self, other): return MagicMock()
    def __ge__(self, other): return MagicMock()
    def __eq__(self, other): return MagicMock()
    def __ne__(self, other): return MagicMock()
    def __hash__(self): return id(self)
    def desc(self): return MagicMock()
    def asc(self): return MagicMock()


class _FakeProduct:
    id = MagicMock()
    user_id = MagicMock()
    name = MagicMock()
    sku = MagicMock()
    category = MagicMock()
    is_active = MagicMock()
    created_at = _ColumnMock()

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeUser:
    id = MagicMock()
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeSentiment:
    product_id = MagicMock()
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeCompetitorProduct:
    product_id = MagicMock()
    competitor_id = MagicMock()
    is_active = MagicMock()
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeCompetitor:
    id = MagicMock()
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


_product_mod = ModuleType("models.product")
_product_mod.Product = _FakeProduct
sys.modules["models.product"] = _product_mod

_user_mod = ModuleType("models.user")
_user_mod.User = _FakeUser
sys.modules["models.user"] = _user_mod

_sentiment_mod = ModuleType("models.sentiment")
_sentiment_mod.Sentiment = _FakeSentiment
sys.modules["models.sentiment"] = _sentiment_mod

_cp_mod = ModuleType("models.competitor_product")
_cp_mod.CompetitorProduct = _FakeCompetitorProduct
sys.modules["models.competitor_product"] = _cp_mod

_comp_mod = ModuleType("models.competitor")
_comp_mod.Competitor = _FakeCompetitor
sys.modules["models.competitor"] = _comp_mod

# --- Stub schemas ---
_schema_stub = ModuleType("schemas.product")


class _FakeProductCreate:
    def __init__(self, **kw):
        self.name = kw.get("name", "Test")
        self.sku = kw.get("sku", None)
        self.description = kw.get("description", None)
        self.category = kw.get("category", None)
        self.image_url = kw.get("image_url", None)
        self.is_active = kw.get("is_active", True)
        self.base_price = kw.get("base_price", Decimal("19.99"))
        self.cost = kw.get("cost", None)
        self.min_price = kw.get("min_price", None)
        self.max_price = kw.get("max_price", None)
        self.sentiment_multiplier = kw.get("sentiment_multiplier", Decimal("1.0"))
        self.auto_pricing_enabled = kw.get("auto_pricing_enabled", False)
        self.keywords = kw.get("keywords", [])


class _FakeProductUpdate:
    def __init__(self, **kw):
        self._data = kw
        for k, v in kw.items():
            setattr(self, k, v)

    def model_dump(self, exclude_unset=False):
        return self._data


_schema_stub.ProductCreate = _FakeProductCreate
_schema_stub.ProductUpdate = _FakeProductUpdate
sys.modules["schemas.product"] = _schema_stub

# --- Stub pricing_engine ---
_pricing_stub = ModuleType("services.pricing_engine")
_fake_pricing_engine = MagicMock()
_pricing_stub.pricing_engine = _fake_pricing_engine
_pricing_stub.CompetitorPriceData = type("CompetitorPriceData", (), {
    "__init__": lambda self, **kw: [setattr(self, k, v) for k, v in kw.items()] and None
})
sys.modules["services.pricing_engine"] = _pricing_stub

# --- Stub cascade_delete ---
_cascade_stub = ModuleType("services.products.cascade_delete")
_cascade_stub.cascade_delete_product = AsyncMock(return_value={"sentiments": 5, "alerts": 2})
sys.modules["services.products.cascade_delete"] = _cascade_stub

# --- Stub sqlmodel ---
_sqlmodel_stub = ModuleType("sqlmodel")
_sqlmodel_stub.select = MagicMock()
_sqlmodel_stub.func = MagicMock()
sys.modules["sqlmodel"] = _sqlmodel_stub

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.products.product_service import ProductService

# ---------------------------------------------------------------------------
# 3. Restore sys.modules
# ---------------------------------------------------------------------------
for _m in _MOCKED:
    if _originals[_m] is None:
        sys.modules.pop(_m, None)
    else:
        sys.modules[_m] = _originals[_m]
del _m


# ===========================================================================
# Helpers
# ===========================================================================

def _make_session():
    s = AsyncMock()
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.rollback = AsyncMock()
    s.refresh = AsyncMock()
    s.delete = AsyncMock()
    s.execute = AsyncMock()
    s.get = AsyncMock()
    return s


def _make_service(session=None):
    return ProductService(session or _make_session())


def _make_product(**overrides):
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "name": "Test Widget",
        "sku": "WDG-001",
        "base_price": Decimal("19.99"),
        "current_price": Decimal("19.99"),
        "is_active": True,
        "category": "Gadgets",
    }
    defaults.update(overrides)
    return _FakeProduct(**defaults)


# ===========================================================================
# Tests
# ===========================================================================

class TestProductServiceInit:
    def test_stores_session(self):
        session = AsyncMock()
        svc = ProductService(session)
        assert svc.session is session


class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_product(self):
        session = _make_session()
        svc = ProductService(session)
        uid = uuid4()
        data = _FakeProductCreate(name="Widget", base_price=Decimal("29.99"))

        # refresh sets the id
        async def fake_refresh(p):
            p.id = uuid4()
        session.refresh = fake_refresh

        product = await svc.create(uid, data)
        assert product.name == "Widget"
        assert product.base_price == Decimal("29.99")
        assert product.current_price == Decimal("29.99")
        assert product.user_id == uid
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_sets_defaults(self):
        session = _make_session()
        session.refresh = AsyncMock()
        svc = ProductService(session)
        data = _FakeProductCreate()

        product = await svc.create(uuid4(), data)
        assert product.auto_pricing_enabled is False
        assert product.is_active is True
        assert product.keywords == []


class TestGetById:
    @pytest.mark.asyncio
    async def test_found(self):
        session = _make_session()
        uid = uuid4()
        prod = _make_product(user_id=uid)
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        result = await svc.get_by_id(prod.id)
        assert result is prod

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = _make_session()
        session.get = AsyncMock(return_value=None)
        svc = ProductService(session)

        result = await svc.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_wrong_user_returns_none(self):
        session = _make_session()
        prod = _make_product(user_id=uuid4())
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        result = await svc.get_by_id(prod.id, user_id=uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_correct_user_returns_product(self):
        session = _make_session()
        uid = uuid4()
        prod = _make_product(user_id=uid)
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        result = await svc.get_by_id(prod.id, user_id=uid)
        assert result is prod


class TestList:
    @pytest.mark.asyncio
    async def test_basic_pagination(self):
        session = _make_session()
        svc = ProductService(session)

        # Count query
        count_result = MagicMock()
        count_result.scalar.return_value = 2

        # Items query
        items_scalars = MagicMock()
        items_scalars.all.return_value = [_make_product(), _make_product()]
        items_result = MagicMock()
        items_result.scalars.return_value = items_scalars

        session.execute = AsyncMock(side_effect=[count_result, items_result])

        with patch("services.products.product_service.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_query.subquery.return_value = MagicMock()
            mock_query.order_by.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_select.return_value = mock_query

            with patch("services.products.product_service.func") as mock_func:
                mock_func.count.return_value = MagicMock()
                mock_count_select = MagicMock()
                mock_count_select.select_from.return_value = MagicMock()
                # Second call to select() for count
                mock_select.side_effect = [mock_query, mock_count_select]

                products, total = await svc.list(uuid4(), page=1, page_size=20)

        assert total == 2
        assert len(products) == 2

    @pytest.mark.asyncio
    async def test_empty_results(self):
        session = _make_session()
        svc = ProductService(session)

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        items_scalars = MagicMock()
        items_scalars.all.return_value = []
        items_result = MagicMock()
        items_result.scalars.return_value = items_scalars

        session.execute = AsyncMock(side_effect=[count_result, items_result])

        with patch("services.products.product_service.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_query.subquery.return_value = MagicMock()
            mock_query.order_by.return_value = mock_query
            mock_query.offset.return_value = mock_query
            mock_query.limit.return_value = mock_query
            mock_select.return_value = mock_query

            with patch("services.products.product_service.func") as mock_func:
                mock_func.count.return_value = MagicMock()
                mock_count_select = MagicMock()
                mock_count_select.select_from.return_value = MagicMock()
                mock_select.side_effect = [mock_query, mock_count_select]

                products, total = await svc.list(uuid4())

        assert total == 0
        assert products == []


class TestUpdate:
    @pytest.mark.asyncio
    async def test_partial_update(self):
        session = _make_session()
        session.refresh = AsyncMock()
        uid = uuid4()
        prod = _make_product(user_id=uid, name="Old Name")
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        data = _FakeProductUpdate(name="New Name")
        result = await svc.update(prod.id, uid, data)

        assert result.name == "New Name"
        assert hasattr(result, "updated_at")
        session.add.assert_called_once()
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        session = _make_session()
        session.get = AsyncMock(return_value=None)
        svc = ProductService(session)

        data = _FakeProductUpdate(name="X")
        result = await svc.update(uuid4(), uuid4(), data)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_wrong_user(self):
        session = _make_session()
        prod = _make_product(user_id=uuid4())
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        data = _FakeProductUpdate(name="X")
        result = await svc.update(prod.id, uuid4(), data)
        assert result is None


class TestDelete:
    @pytest.mark.asyncio
    async def test_successful_delete(self):
        session = _make_session()
        uid = uuid4()
        prod = _make_product(user_id=uid)
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        with patch("services.products.product_service.cascade_delete_product",
                    new_callable=AsyncMock, return_value={"sentiments": 3}):
            result = await svc.delete(prod.id, uid)

        assert result is True
        session.delete.assert_awaited_once_with(prod)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        session = _make_session()
        session.get = AsyncMock(return_value=None)
        svc = ProductService(session)

        result = await svc.delete(uuid4(), uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_rollback_on_error(self):
        session = _make_session()
        uid = uuid4()
        prod = _make_product(user_id=uid)
        session.get = AsyncMock(return_value=prod)
        session.delete = AsyncMock(side_effect=Exception("db error"))
        svc = ProductService(session)

        with patch("services.products.product_service.cascade_delete_product",
                    new_callable=AsyncMock, return_value={}):
            with pytest.raises(Exception, match="db error"):
                await svc.delete(prod.id, uid)

        session.rollback.assert_awaited_once()


class TestFetchCompetitorPrices:
    @pytest.mark.asyncio
    async def test_fetches_valid_prices(self):
        session = _make_session()
        svc = ProductService(session)

        cp = _FakeCompetitorProduct(
            current_price=Decimal("24.99"),
            last_checked_at=datetime.now(timezone.utc),
            is_active=True,
        )
        comp = _FakeCompetitor(name="Amazon")

        result_mock = MagicMock()
        result_mock.all.return_value = [(cp, comp)]
        session.execute = AsyncMock(return_value=result_mock)

        with patch("services.products.product_service.select") as mock_select:
            mock_q = MagicMock()
            mock_q.join.return_value = mock_q
            mock_q.where.return_value = mock_q
            mock_select.return_value = mock_q

            prices = await svc._fetch_competitor_prices(uuid4())

        assert len(prices) == 1
        assert prices[0].competitor_name == "Amazon"
        assert prices[0].competitor_price == Decimal("24.99")

    @pytest.mark.asyncio
    async def test_skips_zero_price(self):
        session = _make_session()
        svc = ProductService(session)

        cp = _FakeCompetitorProduct(current_price=Decimal("0"), last_checked_at=None)
        comp = _FakeCompetitor(name="BadStore")

        result_mock = MagicMock()
        result_mock.all.return_value = [(cp, comp)]
        session.execute = AsyncMock(return_value=result_mock)

        with patch("services.products.product_service.select") as mock_select:
            mock_q = MagicMock()
            mock_q.join.return_value = mock_q
            mock_q.where.return_value = mock_q
            mock_select.return_value = mock_q

            prices = await svc._fetch_competitor_prices(uuid4())

        assert len(prices) == 0

    @pytest.mark.asyncio
    async def test_skips_too_high_price(self):
        session = _make_session()
        svc = ProductService(session)

        cp = _FakeCompetitorProduct(current_price=Decimal("99999"), last_checked_at=None)
        comp = _FakeCompetitor(name="ErrorStore")

        result_mock = MagicMock()
        result_mock.all.return_value = [(cp, comp)]
        session.execute = AsyncMock(return_value=result_mock)

        with patch("services.products.product_service.select") as mock_select:
            mock_q = MagicMock()
            mock_q.join.return_value = mock_q
            mock_q.where.return_value = mock_q
            mock_select.return_value = mock_q

            prices = await svc._fetch_competitor_prices(uuid4())

        assert len(prices) == 0

    @pytest.mark.asyncio
    async def test_skips_none_price(self):
        session = _make_session()
        svc = ProductService(session)

        cp = _FakeCompetitorProduct(current_price=None, last_checked_at=None)
        comp = _FakeCompetitor(name="NullStore")

        result_mock = MagicMock()
        result_mock.all.return_value = [(cp, comp)]
        session.execute = AsyncMock(return_value=result_mock)

        with patch("services.products.product_service.select") as mock_select:
            mock_q = MagicMock()
            mock_q.join.return_value = mock_q
            mock_q.where.return_value = mock_q
            mock_select.return_value = mock_q

            prices = await svc._fetch_competitor_prices(uuid4())

        assert len(prices) == 0


class TestGetPriceSuggestion:
    @pytest.mark.asyncio
    async def test_product_not_found(self):
        session = _make_session()
        session.get = AsyncMock(return_value=None)
        svc = ProductService(session)

        result = await svc.get_price_suggestion(uuid4(), uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_with_sentiment_and_competitors(self):
        session = _make_session()
        uid = uuid4()
        pid = uuid4()
        prod = _make_product(id=pid, user_id=uid)
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        # Sentiment query
        sentiments = [
            _FakeSentiment(compound_score=0.8),
            _FakeSentiment(compound_score=0.6),
        ]
        sent_scalars = MagicMock()
        sent_scalars.all.return_value = sentiments
        sent_result = MagicMock()
        sent_result.scalars.return_value = sent_scalars

        session.execute = AsyncMock(return_value=sent_result)

        # Mock competitor fetch and pricing engine
        fake_comp_prices = [MagicMock(competitor_name="Amazon")]
        svc._fetch_competitor_prices = AsyncMock(return_value=fake_comp_prices)

        suggestion = {"suggested_price": "24.99", "factors": {}}

        with patch("services.products.product_service.pricing_engine") as mock_pe:
            mock_pe.calculate_suggestion.return_value = suggestion
            with patch("services.products.product_service.select"):
                result = await svc.get_price_suggestion(pid, uid)

        assert result is not None
        assert result["factors"]["data_source"] == "sentiment_and_competitor"

    @pytest.mark.asyncio
    async def test_sentiment_only(self):
        session = _make_session()
        uid = uuid4()
        pid = uuid4()
        prod = _make_product(id=pid, user_id=uid)
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        sentiments = [_FakeSentiment(compound_score=0.5)]
        sent_scalars = MagicMock()
        sent_scalars.all.return_value = sentiments
        sent_result = MagicMock()
        sent_result.scalars.return_value = sent_scalars
        session.execute = AsyncMock(return_value=sent_result)

        svc._fetch_competitor_prices = AsyncMock(return_value=[])

        suggestion = {"suggested_price": "21.99", "factors": {}}

        with patch("services.products.product_service.pricing_engine") as mock_pe:
            mock_pe.calculate_suggestion.return_value = suggestion
            with patch("services.products.product_service.select"):
                result = await svc.get_price_suggestion(pid, uid)

        assert result["factors"]["data_source"] == "sentiment_only"

    @pytest.mark.asyncio
    async def test_competitor_only(self):
        session = _make_session()
        uid = uuid4()
        pid = uuid4()
        prod = _make_product(id=pid, user_id=uid)
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        sent_scalars = MagicMock()
        sent_scalars.all.return_value = []
        sent_result = MagicMock()
        sent_result.scalars.return_value = sent_scalars
        session.execute = AsyncMock(return_value=sent_result)

        svc._fetch_competitor_prices = AsyncMock(return_value=[MagicMock()])

        suggestion = {"suggested_price": "18.99", "factors": {}}

        with patch("services.products.product_service.pricing_engine") as mock_pe:
            mock_pe.calculate_suggestion.return_value = suggestion
            with patch("services.products.product_service.select"):
                result = await svc.get_price_suggestion(pid, uid)

        assert result["factors"]["data_source"] == "competitor_only"

    @pytest.mark.asyncio
    async def test_no_data_source(self):
        session = _make_session()
        uid = uuid4()
        pid = uuid4()
        prod = _make_product(id=pid, user_id=uid)
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        sent_scalars = MagicMock()
        sent_scalars.all.return_value = []
        sent_result = MagicMock()
        sent_result.scalars.return_value = sent_scalars
        session.execute = AsyncMock(return_value=sent_result)

        svc._fetch_competitor_prices = AsyncMock(return_value=[])

        suggestion = {"suggested_price": "19.99", "factors": {}}

        with patch("services.products.product_service.pricing_engine") as mock_pe:
            mock_pe.calculate_suggestion.return_value = suggestion
            with patch("services.products.product_service.select"):
                result = await svc.get_price_suggestion(pid, uid)

        assert result["factors"]["data_source"] == "none"
        assert "warning" in result["factors"]

    @pytest.mark.asyncio
    async def test_sentiment_aggregation_math(self):
        """Verify average compound score calculation is correct."""
        session = _make_session()
        uid = uuid4()
        pid = uuid4()
        prod = _make_product(id=pid, user_id=uid)
        session.get = AsyncMock(return_value=prod)
        svc = ProductService(session)

        sentiments = [
            _FakeSentiment(compound_score=0.9),
            _FakeSentiment(compound_score=0.3),
            _FakeSentiment(compound_score=0.6),
        ]
        sent_scalars = MagicMock()
        sent_scalars.all.return_value = sentiments
        sent_result = MagicMock()
        sent_result.scalars.return_value = sent_scalars
        session.execute = AsyncMock(return_value=sent_result)

        svc._fetch_competitor_prices = AsyncMock(return_value=[])

        with patch("services.products.product_service.pricing_engine") as mock_pe:
            mock_pe.calculate_suggestion.return_value = {"factors": {}}
            with patch("services.products.product_service.select"):
                await svc.get_price_suggestion(pid, uid)

            # Verify the sentiment_score passed to pricing engine
            call_kwargs = mock_pe.calculate_suggestion.call_args.kwargs
            expected = Decimal(str(round((0.9 + 0.3 + 0.6) / 3, 3)))
            assert call_kwargs["sentiment_score"] == expected
            assert call_kwargs["mention_volume"] == 3

            