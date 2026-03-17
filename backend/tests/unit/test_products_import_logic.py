# backend/tests/unit/test_products_import_logic.py
"""
Unit tests for ProductImportService and ImportProductRow.

Covers:
  - ImportProductRow validation (price parsing, field normalization)
  - parse_csv_row platform field mappings (Shopify, WooCommerce)
  - import_products: created / skipped / updated / failed counts
  - Duplicate SKU detection within same import batch
  - Batch size limit enforcement
  - _create_product_from_row field mapping
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from services.products.import_service import (
    ImportProductRow,
    ImportResult,
    ProductImportService,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

TEST_USER_ID = UUID("123e4567-e89b-12d3-a456-426614174000")


def make_row(**kwargs) -> ImportProductRow:
    defaults = {"name": "Test Product", "base_price": Decimal("29.99"), "sku": "TEST-001"}
    defaults.update(kwargs)
    return ImportProductRow(**defaults)


def make_service(existing_skus: set = None) -> ProductImportService:
    """Create a ProductImportService with a mocked async session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    service = ProductImportService(session)
    # Patch _get_existing_skus to avoid DB calls
    service._get_existing_skus = AsyncMock(return_value=existing_skus or set())
    return service


# ── ImportProductRow Validation ────────────────────────────────────────────────


class TestImportProductRow:
    def test_basic_creation(self):
        row = ImportProductRow(name="Widget", base_price=Decimal("19.99"))
        assert row.name == "Widget"
        assert row.base_price == Decimal("19.99")

    def test_price_from_float(self):
        row = ImportProductRow(name="Widget", base_price=19.99)
        assert row.base_price == Decimal("19.99")

    def test_price_from_string(self):
        row = ImportProductRow(name="Widget", base_price="29.99")
        assert row.base_price == Decimal("29.99")

    def test_price_strips_dollar_sign(self):
        row = ImportProductRow(name="Widget", base_price="$49.99")
        assert row.base_price == Decimal("49.99")

    def test_price_strips_euro_sign(self):
        row = ImportProductRow(name="Widget", base_price="€49.99")
        assert row.base_price == Decimal("49.99")

    def test_price_strips_pound_sign(self):
        row = ImportProductRow(name="Widget", base_price="£49.99")
        assert row.base_price == Decimal("49.99")

    def test_price_handles_comma_separator(self):
        row = ImportProductRow(name="Widget", base_price="1,299.99")
        assert row.base_price == Decimal("1299.99")

    def test_invalid_price_raises(self):
        with pytest.raises(Exception):
            ImportProductRow(name="Widget", base_price="not-a-price")

    def test_zero_price_raises(self):
        with pytest.raises(Exception):
            ImportProductRow(name="Widget", base_price=0)

    def test_negative_price_raises(self):
        with pytest.raises(Exception):
            ImportProductRow(name="Widget", base_price=-5.00)

    def test_empty_name_raises(self):
        with pytest.raises(Exception):
            ImportProductRow(name="", base_price=10.00)

    def test_optional_fields_default_none(self):
        row = ImportProductRow(name="Widget", base_price=10.00)
        assert row.sku is None
        assert row.description is None
        assert row.category is None
        assert row.image_url is None

    def test_sku_max_length(self):
        with pytest.raises(Exception):
            ImportProductRow(name="Widget", base_price=10.00, sku="X" * 101)

    def test_stock_quantity_non_negative(self):
        with pytest.raises(Exception):
            ImportProductRow(name="Widget", base_price=10.00, stock_quantity=-1)


# ── parse_csv_row ──────────────────────────────────────────────────────────────


class TestParseCsvRow:
    def test_standard_fields(self):
        row = ProductImportService.parse_csv_row(
            {
                "name": "Standard Widget",
                "base_price": "19.99",
                "sku": "STD-001",
            }
        )
        assert row.name == "Standard Widget"
        assert row.base_price == Decimal("19.99")
        assert row.sku == "STD-001"

    def test_shopify_field_names(self):
        row = ProductImportService.parse_csv_row(
            {
                "Title": "Shopify Product",
                "Variant Price": "39.99",
                "Variant SKU": "SHOP-001",
                "Body (HTML)": "<p>Description</p>",
                "Type": "Apparel",
                "Image Src": "https://cdn.shopify.com/img.jpg",
            }
        )
        assert row.name == "Shopify Product"
        assert row.base_price == Decimal("39.99")
        assert row.sku == "SHOP-001"
        assert row.description == "<p>Description</p>"
        assert row.category == "Apparel"
        assert row.image_url == "https://cdn.shopify.com/img.jpg"

    def test_woocommerce_field_names(self):
        row = ProductImportService.parse_csv_row(
            {
                "Name": "WooCommerce Product",
                "regular_price": "24.99",
                "SKU": "WOO-001",
                "Description": "A great product",
                "Category": "Electronics",
            }
        )
        assert row.name == "WooCommerce Product"
        assert row.base_price == Decimal("24.99")
        assert row.sku == "WOO-001"

    def test_missing_optional_fields_are_none(self):
        row = ProductImportService.parse_csv_row(
            {
                "name": "Minimal Product",
                "price": "9.99",
            }
        )
        assert row.sku is None
        assert row.description is None
        assert row.category is None
        assert row.image_url is None


# ── _create_product_from_row ───────────────────────────────────────────────────


class TestCreateProductFromRow:
    def test_basic_product_creation(self):
        service = make_service()
        row = make_row(name="  Widget  ", sku="  W-001  ")
        product = service._create_product_from_row(TEST_USER_ID, row)

        assert product.name == "Widget"
        assert product.sku == "W-001"
        assert product.user_id == TEST_USER_ID
        assert product.base_price == row.base_price
        assert product.current_price == row.base_price
        assert product.is_active is True
        assert product.auto_pricing_enabled is False
        assert product.keywords == []

    def test_none_sku_stays_none(self):
        service = make_service()
        row = make_row(sku=None)
        product = service._create_product_from_row(TEST_USER_ID, row)
        assert product.sku is None

    def test_optional_fields_stripped(self):
        service = make_service()
        row = make_row(
            description="  A great product  ",
            category="  Electronics  ",
            image_url="  https://example.com/img.jpg  ",
        )
        product = service._create_product_from_row(TEST_USER_ID, row)
        assert product.description == "A great product"
        assert product.category == "Electronics"
        assert product.image_url == "https://example.com/img.jpg"


# ── import_products ────────────────────────────────────────────────────────────


class TestImportProducts:
    @pytest.mark.asyncio
    async def test_creates_new_products(self):
        service = make_service()
        rows = [
            make_row(name="Product A", sku="A-001"),
            make_row(name="Product B", sku="B-001"),
        ]
        result = await service.import_products(TEST_USER_ID, rows)

        assert result.created == 2
        assert result.skipped == 0
        assert result.failed == 0
        assert service.session.commit.called

    @pytest.mark.asyncio
    async def test_skips_duplicate_skus_by_default(self):
        service = make_service(existing_skus={"EXISTING-001"})
        rows = [
            make_row(name="New Product", sku="NEW-001"),
            make_row(name="Duplicate", sku="EXISTING-001"),
        ]
        result = await service.import_products(TEST_USER_ID, rows)

        assert result.created == 1
        assert result.skipped == 1

    @pytest.mark.asyncio
    async def test_no_duplicates_within_same_batch(self):
        service = make_service()
        rows = [
            make_row(name="Product A", sku="SAME-SKU"),
            make_row(name="Product B", sku="SAME-SKU"),
        ]
        result = await service.import_products(TEST_USER_ID, rows)

        assert result.created == 1
        assert result.skipped == 1

    @pytest.mark.asyncio
    async def test_empty_import_returns_zero_counts(self):
        service = make_service()
        result = await service.import_products(TEST_USER_ID, [])

        assert result.created == 0
        assert result.skipped == 0
        assert result.failed == 0
        assert not service.session.commit.called

    @pytest.mark.asyncio
    async def test_batch_size_limit_raises(self):
        service = make_service()
        rows = [make_row(name=f"Product {i}", sku=f"SKU-{i}") for i in range(1001)]

        with pytest.raises(ValueError, match="Maximum"):
            await service.import_products(TEST_USER_ID, rows)

    @pytest.mark.asyncio
    async def test_exact_batch_size_limit_passes(self):
        service = make_service()
        rows = [make_row(name=f"Product {i}", sku=f"SKU-{i}") for i in range(1000)]
        result = await service.import_products(TEST_USER_ID, rows)
        assert result.created == 1000

    @pytest.mark.asyncio
    async def test_commit_failure_rolls_back(self):
        service = make_service()
        service.session.commit = AsyncMock(side_effect=Exception("DB error"))
        rows = [make_row()]

        with pytest.raises(Exception, match="DB error"):
            await service.import_products(TEST_USER_ID, rows)

        assert service.session.rollback.called

    @pytest.mark.asyncio
    async def test_products_without_sku_always_created(self):
        service = make_service()
        rows = [
            make_row(name="No SKU A", sku=None),
            make_row(name="No SKU B", sku=None),
        ]
        result = await service.import_products(TEST_USER_ID, rows)
        assert result.created == 2

    @pytest.mark.asyncio
    async def test_total_processed_property(self):
        result = ImportResult(created=3, skipped=1, failed=1)
        assert result.total_processed == 5

    @pytest.mark.asyncio
    async def test_errors_capped_at_max(self):
        service = make_service()
        # Patch _create_product_from_row to always raise
        service._create_product_from_row = MagicMock(side_effect=Exception("bad row"))
        rows = [make_row(name=f"Product {i}", sku=f"SKU-{i}") for i in range(100)]

        result = await service.import_products(TEST_USER_ID, rows)

        assert result.failed == 100
        assert len(result.errors) <= ProductImportService.MAX_ERRORS
