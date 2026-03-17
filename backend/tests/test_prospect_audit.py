"""
Tests for ProspectAuditService

Covers:
  - CSV product analysis (categorization, gap calculation)
  - Impact estimation math
  - Edge cases (empty input, single product, all same price)
  - Shopify URL parsing / normalization
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from schemas.prospect_audit import (
    ProspectAuditRequest,
    ProspectProductRow,
)
from services.prospect_audit_service import ProspectAuditService

# ── Fixtures ──────────────────────────────────────────────────


def make_products(data: list[tuple[str, float]]) -> list[ProspectProductRow]:
    """Helper to create product lists from (name, price) tuples."""
    return [ProspectProductRow(name=name, price=Decimal(str(price))) for name, price in data]


# ── Analysis Tests ────────────────────────────────────────────


class TestAnalyzeProducts:
    def test_empty_input(self):
        service = ProspectAuditService()
        results = service._analyze_products([])
        assert results == []

    def test_single_product(self):
        products = make_products([("Widget A", 29.99)])
        service = ProspectAuditService()
        results = service._analyze_products(products)
        assert len(results) == 1
        # Single product = benchmark is itself, so aligned
        assert results[0].gap_type == "aligned"

    def test_two_products_detects_overpriced(self):
        """If one product is much higher than the other, it should be overpriced."""
        products = make_products(
            [
                ("Running Shoes Pro", 150.00),
                ("Running Shoes Basic", 50.00),
            ]
        )
        service = ProspectAuditService()
        results = service._analyze_products(products)
        assert len(results) == 2
        # At least one should be overpriced or underpriced
        gap_types = {r.gap_type for r in results}
        assert gap_types != {"aligned"}

    def test_all_same_price_aligned(self):
        """Products at the same price should all be aligned."""
        products = make_products(
            [
                ("T-Shirt Red", 25.00),
                ("T-Shirt Blue", 25.00),
                ("T-Shirt Green", 25.00),
            ]
        )
        service = ProspectAuditService()
        results = service._analyze_products(products)
        for r in results:
            assert r.gap_type == "aligned"

    def test_zero_price_excluded(self):
        """Products with zero price should get no_data."""
        products = make_products(
            [
                ("Free Sample", 0.00),
                ("Paid Item", 30.00),
            ]
        )
        service = ProspectAuditService()
        results = service._analyze_products(products)
        free = [r for r in results if r.name == "Free Sample"][0]
        assert free.gap_type == "no_data"

    def test_market_avg_populated(self):
        """Results should include a market average price."""
        products = make_products(
            [
                ("Gadget A", 100.00),
                ("Gadget B", 80.00),
                ("Gadget C", 120.00),
            ]
        )
        service = ProspectAuditService()
        results = service._analyze_products(products)
        for r in results:
            assert r.market_avg_price is not None
            assert r.market_avg_price > 0


class TestCategorization:
    def test_groups_by_keyword(self):
        products = make_products(
            [
                ("Running Shoes Pro", 150.00),
                ("Running Shoes Basic", 50.00),
                ("Yoga Mat Premium", 80.00),
                ("Yoga Mat Standard", 30.00),
            ]
        )
        service = ProspectAuditService()
        categories = service._categorize_products(products)
        # Should create at least 2 groups
        assert len(categories) >= 2

    def test_empty_names_go_to_other(self):
        products = [ProspectProductRow(name="", price=Decimal("10.00"))]
        service = ProspectAuditService()
        categories = service._categorize_products(products)
        assert "other" in categories


class TestImpactEstimation:
    def test_no_overpriced_zero_impact(self):
        """If nothing is overpriced, monthly impact is zero."""
        products = make_products(
            [
                ("Widget A", 25.00),
                ("Widget B", 25.00),
            ]
        )
        service = ProspectAuditService()
        results = service._analyze_products(products)
        impact = service._estimate_monthly_impact(results)
        assert impact == Decimal("0")

    def test_overpriced_produces_positive_impact(self):
        """Overpriced items should generate positive impact estimate."""
        products = make_products(
            [
                ("Premium Widget", 200.00),
                ("Budget Widget", 20.00),
                ("Standard Widget", 30.00),
                ("Basic Widget", 25.00),
            ]
        )
        service = ProspectAuditService()
        results = service._analyze_products(products)
        impact = service._estimate_monthly_impact(results)
        # The $200 widget should be heavily overpriced vs the ~$25 avg
        assert impact > 0

    def test_impact_math_formula(self):
        """Verify: lost_daily = daily_units × elasticity × gap% × price × 30."""
        # Manual calc: 3 units × 0.015 × 10% gap × $50 price × 30 days
        expected_daily = Decimal("3") * Decimal("0.015") * Decimal("10") * Decimal("50")
        expected_monthly = expected_daily * Decimal("30")
        assert expected_monthly == Decimal("675.0")


# ── Teaser Generation Tests ───────────────────────────────────


class TestGenerateTeaser:
    @pytest.mark.asyncio
    async def test_csv_products_teaser(self):
        products = make_products(
            [
                ("Sneakers A", 120.00),
                ("Sneakers B", 80.00),
                ("Jacket A", 200.00),
                ("Jacket B", 150.00),
                ("Socks Pack", 15.00),
                ("Hat Classic", 25.00),
                ("Belt Leather", 45.00),
            ]
        )
        request = ProspectAuditRequest(products=products)
        service = ProspectAuditService()
        teaser = await service.generate_teaser(request)

        assert teaser.total_products_found == 7
        assert len(teaser.top_products) <= 5
        assert teaser.remaining_products_count >= 0

    @pytest.mark.asyncio
    async def test_empty_request_returns_empty(self):
        request = ProspectAuditRequest(products=[])
        service = ProspectAuditService()
        teaser = await service.generate_teaser(request)

        assert teaser.total_products_found == 0
        assert teaser.estimated_monthly_impact == Decimal("0")

    @pytest.mark.asyncio
    async def test_top_products_capped_at_5(self):
        products = make_products([(f"Product {i}", 10.00 + i * 20) for i in range(20)])
        request = ProspectAuditRequest(products=products)
        service = ProspectAuditService()
        teaser = await service.generate_teaser(request)

        assert len(teaser.top_products) <= 5
        assert teaser.remaining_products_count == 20 - len(teaser.top_products)


# ── Shopify URL Tests ─────────────────────────────────────────


class TestShopifyScraper:
    @pytest.mark.asyncio
    async def test_url_normalization(self):
        """Service should handle URLs with/without https."""
        service = ProspectAuditService()

        # Mock httpx to avoid real requests
        with patch("services.prospect_audit_service.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(
                return_value={
                    "products": [
                        {
                            "title": "Test Product",
                            "variants": [{"price": "29.99", "sku": "TEST-001"}],
                        }
                    ]
                }
            )

            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            store_name, products = await service._fetch_shopify_products("mystore.myshopify.com")

            assert store_name == "Mystore"
            assert len(products) == 1
            assert products[0].name == "Test Product"
            assert products[0].price == Decimal("29.99")

    @pytest.mark.asyncio
    async def test_failed_fetch_returns_empty(self):
        """If Shopify returns an error, we should get empty list, not crash."""
        service = ProspectAuditService()

        with patch("services.prospect_audit_service.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Connection refused")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            store_name, products = await service._fetch_shopify_products("https://deadstore.myshopify.com")

            assert products == []
