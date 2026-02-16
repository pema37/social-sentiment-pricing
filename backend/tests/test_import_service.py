"""
Tests for services/products/import_service.py — ProductImportService

Covers:
- ImportProductRow: validation, price parsing ($, €, £, commas)
- ImportResult: defaults, total_processed property
- ProductImportService.__init__
- import_products: batch insert, skip_duplicates, update_existing,
  max batch size, row errors, commit/rollback, MAX_ERRORS cap
- _get_existing_skus: query building, empty results
- _create_product_from_row: field mapping, stripping, None handling
- parse_csv_row: Shopify fields, WooCommerce fields, missing fields
"""

import sys
import os
from types import ModuleType
from decimal import Decimal
from uuid import uuid4, UUID
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = [
    "db.session",
    "models.product",
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
]:
    if _pkg not in sys.modules:
        _mod = ModuleType(_pkg)
        _mod.__path__ = [os.path.join(_backend_dir, _subdir)]
        _mod.__package__ = _pkg
        sys.modules[_pkg] = _mod

# Stub models.product with a dual-purpose fake Product
if "models" not in sys.modules:
    _models_pkg = ModuleType("models")
    _models_pkg.__path__ = [os.path.join(_backend_dir, "models")]
    _models_pkg.__package__ = "models"
    sys.modules["models"] = _models_pkg

_product_stub = ModuleType("models.product")


class _FakeProduct:
    """Dual-purpose fake: class-level attrs for queries, instance for construction."""
    user_id = MagicMock()
    sku = MagicMock()
    # sku.isnot must return a MagicMock for query building
    sku.isnot = MagicMock(return_value=MagicMock())

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


_product_stub.Product = _FakeProduct
sys.modules["models.product"] = _product_stub

# Stub sqlmodel
_sqlmodel_stub = ModuleType("sqlmodel")
_sqlmodel_stub.select = MagicMock()
sys.modules["sqlmodel"] = _sqlmodel_stub

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.products.import_service import (
    ImportProductRow,
    ImportResult,
    ProductImportService,
)

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

def _make_row(**overrides) -> ImportProductRow:
    defaults = {"name": "Test Product", "base_price": Decimal("19.99")}
    defaults.update(overrides)
    return ImportProductRow(**defaults)


def _make_service(session=None) -> ProductImportService:
    if session is None:
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.execute = AsyncMock()
    return ProductImportService(session)


# ===========================================================================
# ImportProductRow Tests
# ===========================================================================

class TestImportProductRow:
    """Test ImportProductRow schema validation."""

    def test_valid_minimal(self):
        row = ImportProductRow(name="Widget", base_price=Decimal("9.99"))
        assert row.name == "Widget"
        assert row.base_price == Decimal("9.99")
        assert row.sku is None
        assert row.description is None

    def test_valid_full(self):
        row = ImportProductRow(
            name="Widget",
            base_price=Decimal("9.99"),
            sku="WDG-001",
            description="A fine widget",
            category="Gadgets",
            image_url="https://img.com/w.jpg",
            stock_quantity=50,
        )
        assert row.sku == "WDG-001"
        assert row.stock_quantity == 50

    def test_price_from_float(self):
        row = ImportProductRow(name="X", base_price=19.99)
        assert row.base_price == Decimal("19.99")

    def test_price_from_int(self):
        row = ImportProductRow(name="X", base_price=20)
        assert row.base_price == Decimal("20")

    def test_price_from_dollar_string(self):
        row = ImportProductRow(name="X", base_price="$29.99")
        assert row.base_price == Decimal("29.99")

    def test_price_from_euro_string(self):
        row = ImportProductRow(name="X", base_price="€15.50")
        assert row.base_price == Decimal("15.50")

    def test_price_from_pound_string(self):
        row = ImportProductRow(name="X", base_price="£9.99")
        assert row.base_price == Decimal("9.99")

    def test_price_with_commas(self):
        row = ImportProductRow(name="X", base_price="1,299.99")
        assert row.base_price == Decimal("1299.99")

    def test_price_with_spaces(self):
        row = ImportProductRow(name="X", base_price="  $19.99  ")
        assert row.base_price == Decimal("19.99")

    def test_invalid_price_string(self):
        with pytest.raises(Exception):
            ImportProductRow(name="X", base_price="not-a-price")

    def test_zero_price_rejected(self):
        with pytest.raises(Exception):
            ImportProductRow(name="X", base_price=Decimal("0"))

    def test_negative_price_rejected(self):
        with pytest.raises(Exception):
            ImportProductRow(name="X", base_price=Decimal("-5"))

    def test_empty_name_rejected(self):
        with pytest.raises(Exception):
            ImportProductRow(name="", base_price=Decimal("9.99"))

    def test_negative_stock_rejected(self):
        with pytest.raises(Exception):
            ImportProductRow(name="X", base_price=Decimal("9.99"), stock_quantity=-1)


class TestImportResult:
    """Test ImportResult model."""

    def test_defaults(self):
        r = ImportResult()
        assert r.created == 0
        assert r.updated == 0
        assert r.skipped == 0
        assert r.failed == 0
        assert r.errors == []

    def test_total_processed(self):
        r = ImportResult(created=5, updated=2, skipped=1, failed=3)
        assert r.total_processed == 11

    def test_total_processed_all_zero(self):
        r = ImportResult()
        assert r.total_processed == 0


# ===========================================================================
# ProductImportService Tests
# ===========================================================================

class TestImportServiceInit:
    """Test __init__."""

    def test_stores_session(self):
        session = AsyncMock()
        svc = ProductImportService(session)
        assert svc.session is session

    def test_class_constants(self):
        assert ProductImportService.MAX_BATCH_SIZE == 1000
        assert ProductImportService.MAX_ERRORS == 50


class TestImportProducts:
    """Test import_products method."""

    @pytest.mark.asyncio
    async def test_exceeds_max_batch_raises(self):
        svc = _make_service()
        rows = [_make_row(name=f"P{i}") for i in range(1001)]
        with pytest.raises(ValueError, match="Maximum 1000"):
            await svc.import_products(user_id=uuid4(), products=rows)

    @pytest.mark.asyncio
    async def test_basic_import_creates_products(self):
        svc = _make_service()
        svc._get_existing_skus = AsyncMock(return_value=set())
        rows = [_make_row(name="A"), _make_row(name="B")]

        result = await svc.import_products(user_id=uuid4(), products=rows)
        assert result.created == 2
        assert result.skipped == 0
        assert result.failed == 0
        assert svc.session.add.call_count == 2
        svc.session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skip_duplicates(self):
        svc = _make_service()
        svc._get_existing_skus = AsyncMock(return_value={"SKU-001"})
        rows = [
            _make_row(name="Existing", sku="SKU-001"),
            _make_row(name="New", sku="SKU-002"),
        ]

        result = await svc.import_products(user_id=uuid4(), products=rows, skip_duplicates=True)
        assert result.skipped == 1
        assert result.created == 1

    @pytest.mark.asyncio
    async def test_update_existing_increments(self):
        svc = _make_service()
        svc._get_existing_skus = AsyncMock(return_value={"SKU-001"})
        rows = [_make_row(name="Existing", sku="SKU-001")]

        result = await svc.import_products(
            user_id=uuid4(), products=rows, update_existing=True
        )
        assert result.updated == 1
        assert result.created == 0

    @pytest.mark.asyncio
    async def test_within_import_duplicate_detection(self):
        """If two rows in same import have same SKU, second should be skipped."""
        svc = _make_service()
        svc._get_existing_skus = AsyncMock(return_value=set())
        rows = [
            _make_row(name="First", sku="DUP-SKU"),
            _make_row(name="Second", sku="DUP-SKU"),
        ]

        result = await svc.import_products(user_id=uuid4(), products=rows, skip_duplicates=True)
        assert result.created == 1
        assert result.skipped == 1

    @pytest.mark.asyncio
    async def test_row_error_isolated(self):
        svc = _make_service()
        svc._get_existing_skus = AsyncMock(return_value=set())
        svc._create_product_from_row = MagicMock(side_effect=[
            Exception("bad row"),
            _FakeProduct(name="Good"),
        ])
        rows = [_make_row(name="Bad"), _make_row(name="Good")]

        result = await svc.import_products(user_id=uuid4(), products=rows)
        assert result.failed == 1
        assert result.created == 1
        assert "Row 1 (Bad)" in result.errors[0]

    @pytest.mark.asyncio
    async def test_max_errors_cap(self):
        svc = _make_service()
        svc._get_existing_skus = AsyncMock(return_value=set())
        svc._create_product_from_row = MagicMock(side_effect=Exception("fail"))
        rows = [_make_row(name=f"P{i}") for i in range(60)]

        result = await svc.import_products(user_id=uuid4(), products=rows)
        assert result.failed == 60
        assert len(result.errors) == 50  # capped at MAX_ERRORS

    @pytest.mark.asyncio
    async def test_commit_failure_rollback(self):
        svc = _make_service()
        svc._get_existing_skus = AsyncMock(return_value=set())
        svc.session.commit = AsyncMock(side_effect=Exception("db error"))
        rows = [_make_row(name="A")]

        with pytest.raises(Exception, match="db error"):
            await svc.import_products(user_id=uuid4(), products=rows)
        svc.session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_list_returns_clean_result(self):
        svc = _make_service()
        svc._get_existing_skus = AsyncMock(return_value=set())
        result = await svc.import_products(user_id=uuid4(), products=[])
        assert result.created == 0
        assert result.total_processed == 0
        svc.session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_sku_products_not_deduped(self):
        """Products without SKU should never be treated as duplicates."""
        svc = _make_service()
        svc._get_existing_skus = AsyncMock(return_value=set())
        rows = [
            _make_row(name="A", sku=None),
            _make_row(name="B", sku=None),
        ]

        result = await svc.import_products(user_id=uuid4(), products=rows)
        assert result.created == 2
        assert result.skipped == 0


class TestGetExistingSkus:
    """Test _get_existing_skus."""

    @pytest.mark.asyncio
    async def test_returns_set_of_skus(self):
        svc = _make_service()
        mock_result = MagicMock()
        mock_result.all.return_value = [("SKU-001",), ("SKU-002",), (None,)]
        svc.session.execute = AsyncMock(return_value=mock_result)

        with patch.dict("sys.modules", {"sqlmodel": MagicMock()}):
            skus = await svc._get_existing_skus(uuid4())
        assert skus == {"SKU-001", "SKU-002"}

    @pytest.mark.asyncio
    async def test_empty_results(self):
        svc = _make_service()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        svc.session.execute = AsyncMock(return_value=mock_result)

        with patch.dict("sys.modules", {"sqlmodel": MagicMock()}):
            skus = await svc._get_existing_skus(uuid4())
        assert skus == set()


class TestCreateProductFromRow:
    """Test _create_product_from_row."""

    def test_basic_fields(self):
        svc = _make_service()
        uid = uuid4()
        row = _make_row(
            name="  Widget  ",
            sku="  WDG-001  ",
            base_price=Decimal("19.99"),
            description="  A widget  ",
            category="  Gadgets  ",
            image_url="  https://img.com/w.jpg  ",
        )

        product = svc._create_product_from_row(uid, row)
        assert product.user_id == uid
        assert product.name == "Widget"
        assert product.sku == "WDG-001"
        assert product.description == "A widget"
        assert product.category == "Gadgets"
        assert product.image_url == "https://img.com/w.jpg"
        assert product.base_price == Decimal("19.99")
        assert product.current_price == Decimal("19.99")
        assert product.is_active is True
        assert product.auto_pricing_enabled is False
        assert product.keywords == []

    def test_none_optional_fields(self):
        svc = _make_service()
        row = _make_row(name="X", sku=None, description=None, category=None, image_url=None)
        product = svc._create_product_from_row(uuid4(), row)
        assert product.sku is None
        assert product.description is None
        assert product.category is None
        assert product.image_url is None


class TestParseCsvRow:
    """Test parse_csv_row classmethod."""

    def test_standard_fields(self):
        row_dict = {"name": "Widget", "price": "19.99", "sku": "W-001"}
        row = ProductImportService.parse_csv_row(row_dict)
        assert row.name == "Widget"
        assert row.base_price == Decimal("19.99")
        assert row.sku == "W-001"

    def test_shopify_fields(self):
        row_dict = {
            "Title": "Shopify Product",
            "Variant Price": "$29.99",
            "Variant SKU": "SP-001",
            "Body (HTML)": "<p>Description</p>",
            "Product Type": "Clothing",
            "Image Src": "https://img.com/sp.jpg",
        }
        row = ProductImportService.parse_csv_row(row_dict)
        assert row.name == "Shopify Product"
        assert row.base_price == Decimal("29.99")
        assert row.sku == "SP-001"
        assert row.description == "<p>Description</p>"
        assert row.category == "Clothing"
        assert row.image_url == "https://img.com/sp.jpg"

    def test_woocommerce_fields(self):
        row_dict = {
            "Name": "Woo Product",
            "regular_price": "49.99",
            "SKU": "WOO-001",
            "Description": "Woo desc",
            "Category": "Electronics",
        }
        row = ProductImportService.parse_csv_row(row_dict)
        assert row.name == "Woo Product"
        assert row.base_price == Decimal("49.99")
        assert row.sku == "WOO-001"
        assert row.category == "Electronics"

    def test_missing_name_uses_empty(self):
        """Missing name fields fall through to empty string, which should fail validation."""
        with pytest.raises(Exception):
            ProductImportService.parse_csv_row({"price": "9.99"})

    def test_missing_price_uses_zero(self):
        """Missing price falls through to '0', which should fail gt=0 validation."""
        with pytest.raises(Exception):
            ProductImportService.parse_csv_row({"name": "X"})

    def test_priority_order_name(self):
        """'name' takes priority over 'Name' and 'title'."""
        row_dict = {"name": "First", "Name": "Second", "title": "Third", "price": "1"}
        row = ProductImportService.parse_csv_row(row_dict)
        assert row.name == "First"

    def test_priority_order_price(self):
        """'base_price' takes priority over 'price'."""
        row_dict = {"name": "X", "base_price": "10", "price": "20"}
        row = ProductImportService.parse_csv_row(row_dict)
        assert row.base_price == Decimal("10")

        