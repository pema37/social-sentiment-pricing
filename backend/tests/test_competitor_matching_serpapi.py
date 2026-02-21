# backend/tests/test_competitor_matching_serpapi.py
"""
Tests for competitor_matching/providers/serpapi.py

Covers:
- Provider properties (name, api_key, rate_limit, cost)
- is_available
- _parse_results / _parse_item (shopping_results + inline_shopping_results)
- _extract_currency
- get_usage_stats

Total: ~28 tests
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch

for mod in ["db.session"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from services.competitor_matching.schemas import SearchProvider, ProviderResult
from services.competitor_matching.providers.serpapi import SerpAPIProvider


# ============================================================
# 1. Provider Properties
# ============================================================

class TestSerpAPIProperties:

    def test_provider_name(self):
        p = SerpAPIProvider(api_key="key")
        assert p.provider_name == SearchProvider.SERPAPI_GOOGLE_SHOPPING

    def test_requires_api_key(self):
        p = SerpAPIProvider()
        assert p.requires_api_key is True

    def test_rate_limit(self):
        p = SerpAPIProvider()
        assert p.rate_limit_per_minute == 100

    def test_cost_per_request(self):
        p = SerpAPIProvider()
        assert p.cost_per_request == 0.01

    def test_custom_params(self):
        p = SerpAPIProvider(api_key="k", timeout=15.0, country="uk", language="fr")
        assert p.timeout == 15.0
        assert p.country == "uk"
        assert p.language == "fr"


# ============================================================
# 2. is_available
# ============================================================

class TestIsAvailable:

    def test_available_with_key(self):
        p = SerpAPIProvider(api_key="test-key")
        assert p.is_available() is True

    def test_unavailable_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            p = SerpAPIProvider(api_key=None)
            assert p.is_available() is False


# ============================================================
# 3. _extract_currency
# ============================================================

class TestExtractCurrency:

    def setup_method(self):
        self.p = SerpAPIProvider(api_key="key")

    def test_usd_dollar_sign(self):
        assert self.p._extract_currency({"price": "$49.99"}) == "USD"

    def test_usd_text(self):
        assert self.p._extract_currency({"price": "49.99 USD"}) == "USD"

    def test_eur(self):
        assert self.p._extract_currency({"price": "€39.99"}) == "EUR"

    def test_gbp(self):
        assert self.p._extract_currency({"price": "£29.99"}) == "GBP"

    def test_cad_explicit(self):
        # "CA$" contains "$" which matches USD first in source code
        assert self.p._extract_currency({"price": "59.99 CAD"}) == "CAD"

    def test_default_usd(self):
        assert self.p._extract_currency({"price": "49.99"}) == "USD"

    def test_no_price_field(self):
        assert self.p._extract_currency({}) == "USD"


# ============================================================
# 4. _parse_item
# ============================================================

class TestParseItem:

    def setup_method(self):
        self.p = SerpAPIProvider(api_key="key")

    def test_full_item(self):
        item = {
            "title": "Widget Pro 2024",
            "link": "https://www.amazon.com/widget-pro",
            "extracted_price": 49.99,
            "source": "Amazon",
            "rating": "4.5",
            "reviews": "1234",
            "thumbnail": "https://img.com/thumb.jpg",
            "price": "$49.99",
        }
        product = self.p._parse_item(item)
        assert product is not None
        assert product.merchant == "Amazon"
        assert product.rating == 4.5
        assert product.reviews_count == 1234

    def test_missing_title(self):
        assert self.p._parse_item({"link": "https://amazon.com"}) is None

    def test_missing_url(self):
        assert self.p._parse_item({"title": "Widget"}) is None

    def test_price_from_extracted_price(self):
        item = {"title": "Widget", "link": "https://amazon.com/w", "extracted_price": 29.99}
        product = self.p._parse_item(item)
        assert product is not None

    def test_price_from_price_string(self):
        item = {"title": "Widget", "link": "https://amazon.com/w", "price": "$39.99"}
        product = self.p._parse_item(item)
        assert product is not None

    def test_invalid_rating_ignored(self):
        item = {"title": "Widget", "link": "https://amazon.com/w", "rating": "bad"}
        product = self.p._parse_item(item)
        assert product is not None
        assert product.rating is None

    def test_invalid_reviews_ignored(self):
        item = {"title": "Widget", "link": "https://amazon.com/w", "reviews": "many"}
        product = self.p._parse_item(item)
        assert product is not None
        assert product.reviews_count is None

    def test_out_of_stock(self):
        item = {
            "title": "Widget",
            "link": "https://amazon.com/w",
            "availability": "Out of Stock",
        }
        product = self.p._parse_item(item)
        assert product is not None
        assert product.in_stock is False

    def test_in_stock_default(self):
        item = {"title": "Widget", "link": "https://amazon.com/w"}
        product = self.p._parse_item(item)
        assert product is not None
        assert product.in_stock is True


# ============================================================
# 5. _parse_results
# ============================================================

class TestParseResults:

    def setup_method(self):
        self.p = SerpAPIProvider(api_key="key")

    def test_empty_results(self):
        assert self.p._parse_results({}) == []

    def test_shopping_results(self):
        data = {"shopping_results": [
            {"title": "A", "link": "https://amazon.com/a"},
            {"title": "B", "link": "https://amazon.com/b"},
        ]}
        products = self.p._parse_results(data)
        assert len(products) == 2

    def test_inline_shopping_results(self):
        data = {"inline_shopping_results": [
            {"title": "C", "link": "https://amazon.com/c"},
        ]}
        products = self.p._parse_results(data)
        assert len(products) == 1

    def test_combines_both_result_types(self):
        data = {
            "shopping_results": [{"title": "A", "link": "https://amazon.com/a"}],
            "inline_shopping_results": [{"title": "B", "link": "https://amazon.com/b"}],
        }
        products = self.p._parse_results(data)
        assert len(products) == 2


# ============================================================
# 6. get_usage_stats
# ============================================================

class TestGetUsageStats:

    def test_initial_stats(self):
        p = SerpAPIProvider(api_key="key")
        stats = p.get_usage_stats()
        assert stats["requests_made"] == 0
        assert stats["estimated_cost"] == 0.0
        assert stats["provider"] == "serpapi_google_shopping"

    def test_stats_after_requests(self):
        p = SerpAPIProvider(api_key="key")
        p._requests_made = 100
        stats = p.get_usage_stats()
        assert stats["requests_made"] == 100
        assert stats["estimated_cost"] == pytest.approx(1.0)

        