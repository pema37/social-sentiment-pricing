# backend/tests/test_competitor_matching_models.py
"""
Tests for competitor_matching/models.py — pure data classes, enums,
properties, and serialization methods.

Total: ~40 tests
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.competitor_matching.models import (
    SearchProvider,
    MatchStatus,
    MatchedProduct,
    ProviderResult,
    MatchSearchRequest,
    MatchSearchResponse,
    MerchantInfo,
)


# ============================================================
# 1. Enums
# ============================================================

class TestSearchProvider:

    def test_values(self):
        assert SearchProvider.SERPAPI_GOOGLE_SHOPPING == "serpapi_google_shopping"
        assert SearchProvider.GOOGLE_CUSTOM_SEARCH == "google_custom_search"
        assert SearchProvider.DUCKDUCKGO == "duckduckgo"

    def test_is_str_enum(self):
        assert isinstance(SearchProvider.DUCKDUCKGO, str)


class TestMatchStatus:

    def test_values(self):
        assert MatchStatus.SUCCESS == "success"
        assert MatchStatus.PARTIAL == "partial"
        assert MatchStatus.FAILED == "failed"
        assert MatchStatus.CACHED == "cached"


# ============================================================
# 2. MatchedProduct
# ============================================================

class TestMatchedProduct:

    def test_defaults(self):
        p = MatchedProduct(title="Widget", url="https://example.com")
        assert p.price is None
        assert p.currency == "USD"
        assert p.merchant == ""
        assert p.confidence_score == 0.0
        assert p.in_stock is True

    def test_price_display_with_price(self):
        p = MatchedProduct(title="Widget", url="https://example.com", price=Decimal("29.99"))
        assert p.price_display == "$29.99"

    def test_price_display_no_price(self):
        p = MatchedProduct(title="Widget", url="https://example.com")
        assert p.price_display == "N/A"

    def test_confidence_percent(self):
        p = MatchedProduct(title="W", url="u", confidence_score=0.85)
        assert p.confidence_percent == 85

    def test_confidence_percent_zero(self):
        p = MatchedProduct(title="W", url="u", confidence_score=0.0)
        assert p.confidence_percent == 0

    def test_to_dict(self):
        p = MatchedProduct(
            title="Widget", url="https://example.com",
            price=Decimal("19.99"), merchant="Amazon",
            confidence_score=0.9,
            source=SearchProvider.SERPAPI_GOOGLE_SHOPPING,
        )
        d = p.to_dict()
        assert d["title"] == "Widget"
        assert d["price"] == "19.99"
        assert d["merchant"] == "Amazon"
        assert d["confidence_percent"] == 90
        assert d["source"] == "serpapi_google_shopping"

    def test_to_dict_no_price(self):
        p = MatchedProduct(title="W", url="u")
        d = p.to_dict()
        assert d["price"] is None

    def test_raw_data_default_empty(self):
        p = MatchedProduct(title="W", url="u")
        assert p.raw_data == {}


# ============================================================
# 3. ProviderResult
# ============================================================

class TestProviderResult:

    def test_defaults(self):
        r = ProviderResult(provider=SearchProvider.DUCKDUCKGO, success=True)
        assert r.products == []
        assert r.error is None
        assert r.rate_limited is False
        assert r.credits_used == 0

    def test_product_count(self):
        products = [
            MatchedProduct(title="A", url="u1"),
            MatchedProduct(title="B", url="u2"),
        ]
        r = ProviderResult(
            provider=SearchProvider.DUCKDUCKGO, success=True, products=products
        )
        assert r.product_count == 2

    def test_product_count_empty(self):
        r = ProviderResult(provider=SearchProvider.DUCKDUCKGO, success=True)
        assert r.product_count == 0

    def test_failure_with_error(self):
        r = ProviderResult(
            provider=SearchProvider.SERPAPI_GOOGLE_SHOPPING,
            success=False, error="API key invalid",
        )
        assert r.success is False
        assert r.error == "API key invalid"


# ============================================================
# 4. MatchSearchRequest
# ============================================================

class TestMatchSearchRequest:

    def test_defaults(self):
        req = MatchSearchRequest(product_name="Widget Pro")
        assert req.max_results == 10
        assert req.min_confidence == 0.3
        assert req.use_cache is True
        assert req.providers is None
        assert req.exclude_domains == []

    def test_build_query_simple(self):
        req = MatchSearchRequest(product_name="Widget Pro")
        assert req.build_query() == "Widget Pro"

    def test_build_query_with_keywords(self):
        req = MatchSearchRequest(
            product_name="Widget Pro",
            keywords=["bluetooth", "wireless"],
        )
        query = req.build_query()
        assert "bluetooth" in query
        assert "wireless" in query

    def test_build_query_dedupes_keywords_in_name(self):
        req = MatchSearchRequest(
            product_name="Wireless Widget Pro",
            keywords=["wireless", "bluetooth"],
        )
        query = req.build_query()
        # "wireless" already in name, should not be duplicated
        assert query.count("ireless") == 1  # case-insensitive check
        assert "bluetooth" in query

    def test_build_query_limits_to_3_keywords(self):
        req = MatchSearchRequest(
            product_name="Widget",
            keywords=["a", "b", "c", "d", "e"],
        )
        query = req.build_query()
        parts = query.split()
        # Widget + max 3 keywords = 4 parts
        assert len(parts) <= 4

    def test_build_query_strips_whitespace(self):
        req = MatchSearchRequest(product_name="  Widget Pro  ")
        assert req.build_query() == "Widget Pro"


# ============================================================
# 5. MatchSearchResponse
# ============================================================

class TestMatchSearchResponse:

    def test_defaults(self):
        r = MatchSearchResponse(status=MatchStatus.SUCCESS)
        assert r.products == []
        assert r.cached is False
        assert r.searched_at is not None

    def test_success_property(self):
        assert MatchSearchResponse(status=MatchStatus.SUCCESS).success is True
        assert MatchSearchResponse(status=MatchStatus.CACHED).success is True
        assert MatchSearchResponse(status=MatchStatus.PARTIAL).success is True
        assert MatchSearchResponse(status=MatchStatus.FAILED).success is False

    def test_has_results(self):
        r = MatchSearchResponse(
            status=MatchStatus.SUCCESS,
            products=[MatchedProduct(title="W", url="u")],
        )
        assert r.has_results is True

    def test_has_results_empty(self):
        r = MatchSearchResponse(status=MatchStatus.SUCCESS)
        assert r.has_results is False

    def test_to_dict(self):
        r = MatchSearchResponse(
            status=MatchStatus.SUCCESS,
            query_used="widget",
            total_found=5,
            providers_used=[SearchProvider.DUCKDUCKGO],
            search_time_ms=200,
        )
        d = r.to_dict()
        assert d["status"] == "success"
        assert d["query_used"] == "widget"
        assert d["total_found"] == 5
        assert d["providers_used"] == ["duckduckgo"]
        assert d["search_time_ms"] == 200

    def test_to_dict_includes_products(self):
        r = MatchSearchResponse(
            status=MatchStatus.SUCCESS,
            products=[MatchedProduct(title="W", url="u", price=Decimal("10"))],
        )
        d = r.to_dict()
        assert len(d["products"]) == 1
        assert d["products"][0]["title"] == "W"


# ============================================================
# 6. MerchantInfo
# ============================================================

class TestMerchantInfo:

    def test_defaults(self):
        m = MerchantInfo(domain="amazon.com", name="Amazon")
        assert m.is_marketplace is False
        assert m.reliability_score == 0.8
        assert m.supports_api is False

    def test_hashable(self):
        m1 = MerchantInfo(domain="amazon.com", name="Amazon")
        m2 = MerchantInfo(domain="amazon.com", name="Amazon")
        assert hash(m1) == hash(m2)

    def test_different_domains_different_hash(self):
        m1 = MerchantInfo(domain="amazon.com", name="Amazon")
        m2 = MerchantInfo(domain="walmart.com", name="Walmart")
        assert hash(m1) != hash(m2)

    def test_in_set(self):
        m1 = MerchantInfo(domain="amazon.com", name="Amazon")
        m2 = MerchantInfo(domain="amazon.com", name="Amazon US")
        s = {m1, m2}
        # Same hash but different name → __eq__ is False → 2 entries
        assert len(s) == 2
        # Identical objects deduplicate
        m3 = MerchantInfo(domain="amazon.com", name="Amazon")
        s2 = {m1, m3}
        assert len(s2) == 1


        