# backend/tests/test_competitor_matching_providers_base.py
"""
Tests for competitor_matching/providers/base.py

Covers:
- BaseSearchProvider: default properties, search() template method, _create_product helper
- ProviderRegistry: register, get, get_available, get_all, available_count

Total: ~25 tests
"""

import sys
from unittest.mock import MagicMock, AsyncMock, patch

for mod in ["db.session", "core.logging"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
sys.modules["core.logging"].get_logger = MagicMock(return_value=MagicMock())

import pytest

from services.competitor_matching.models import (
    SearchProvider,
    MatchedProduct,
    ProviderResult,
    MatchSearchRequest,
)
from services.competitor_matching.providers.base import (
    BaseSearchProvider,
    ProviderRegistry,
)


# ============================================================
# Concrete subclass for testing the ABC
# ============================================================

class FakeProvider(BaseSearchProvider):
    """Minimal concrete implementation for testing."""

    def __init__(self, available=True, api_key_required=True):
        self._available = available
        self._api_key_required = api_key_required
        self._search_result = None

    @property
    def provider_name(self) -> SearchProvider:
        return SearchProvider.SERPAPI_GOOGLE_SHOPPING

    @property
    def requires_api_key(self) -> bool:
        return self._api_key_required

    def is_available(self) -> bool:
        return self._available

    async def _search(self, query, max_results, **kwargs):
        if self._search_result is not None:
            return self._search_result
        return ProviderResult(
            provider=self.provider_name,
            success=True,
            products=[
                MatchedProduct(title="Test Product", url="https://amazon.com/test", source=self.provider_name)
            ],
        )


# ============================================================
# 1. BaseSearchProvider default properties
# ============================================================

class TestBaseSearchProviderDefaults:

    def test_rate_limit_default(self):
        p = FakeProvider()
        assert p.rate_limit_per_minute == 60

    def test_cost_default(self):
        p = FakeProvider()
        assert p.cost_per_request == 0.0

    def test_provider_name(self):
        p = FakeProvider()
        assert p.provider_name == SearchProvider.SERPAPI_GOOGLE_SHOPPING

    def test_requires_api_key(self):
        p = FakeProvider(api_key_required=True)
        assert p.requires_api_key is True


# ============================================================
# 2. search() template method
# ============================================================

class TestSearchTemplateMethod:

    @pytest.mark.asyncio
    async def test_successful_search(self):
        p = FakeProvider(available=True)
        request = MatchSearchRequest(product_name="Widget Pro")
        result = await p.search(request)
        assert result.success is True
        assert result.product_count >= 1
        assert result.response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_unavailable_provider_returns_failure(self):
        p = FakeProvider(available=False)
        request = MatchSearchRequest(product_name="Widget Pro")
        result = await p.search(request)
        assert result.success is False
        assert "not available" in result.error

    @pytest.mark.asyncio
    async def test_exception_in_search_returns_failure(self):
        p = FakeProvider(available=True)
        # Make _search raise
        p._search = AsyncMock(side_effect=RuntimeError("API exploded"))
        request = MatchSearchRequest(product_name="Widget Pro")
        result = await p.search(request)
        assert result.success is False
        assert "API exploded" in result.error
        assert result.response_time_ms >= 0

    @pytest.mark.asyncio
    async def test_builds_query_from_request(self):
        p = FakeProvider(available=True)
        p._search = AsyncMock(return_value=ProviderResult(
            provider=p.provider_name, success=True, products=[],
        ))
        request = MatchSearchRequest(product_name="Widget Pro", keywords=["extra"])
        await p.search(request)
        # _search should have received the built query
        call_kwargs = p._search.call_args
        assert "Widget Pro" in call_kwargs.kwargs.get("query", "") or "Widget Pro" in call_kwargs.args[0]


# ============================================================
# 3. _create_product helper
# ============================================================

class TestCreateProduct:

    def test_valid_product(self):
        p = FakeProvider()
        product = p._create_product(
            title="iPhone 15 Pro FREE SHIPPING",
            url="https://www.amazon.com/dp/B09V3KXJPB",
            price="$999.99",
        )
        assert product is not None
        assert product.merchant == "Amazon"
        assert product.price is not None
        # Title should be cleaned (FREE SHIPPING removed)
        assert "FREE SHIPPING" not in product.title

    def test_skip_domain_returns_none(self):
        p = FakeProvider()
        product = p._create_product(
            title="Some Video",
            url="https://www.youtube.com/watch?v=abc",
        )
        assert product is None

    def test_empty_title_returns_none(self):
        p = FakeProvider()
        assert p._create_product(title="", url="https://amazon.com/test") is None

    def test_empty_url_returns_none(self):
        p = FakeProvider()
        assert p._create_product(title="Product", url="") is None

    def test_custom_merchant_name(self):
        p = FakeProvider()
        product = p._create_product(
            title="Widget",
            url="https://randomshop.com/widget",
            merchant="Custom Shop",
        )
        assert product is not None
        assert product.merchant == "Custom Shop"

    def test_no_price(self):
        p = FakeProvider()
        product = p._create_product(
            title="Widget",
            url="https://amazon.com/widget",
        )
        assert product is not None
        assert product.price is None


# ============================================================
# 4. ProviderRegistry
# ============================================================

class TestProviderRegistry:

    def test_register_and_get(self):
        reg = ProviderRegistry()
        p = FakeProvider()
        reg.register(p)
        assert reg.get(SearchProvider.SERPAPI_GOOGLE_SHOPPING) is p

    def test_get_missing_returns_none(self):
        reg = ProviderRegistry()
        assert reg.get(SearchProvider.DUCKDUCKGO) is None

    def test_get_available(self):
        reg = ProviderRegistry()
        p1 = FakeProvider(available=True)
        reg.register(p1)
        available = reg.get_available()
        assert len(available) == 1

    def test_get_available_excludes_unavailable(self):
        reg = ProviderRegistry()
        p1 = FakeProvider(available=False)
        reg.register(p1)
        assert len(reg.get_available()) == 0

    def test_get_all(self):
        reg = ProviderRegistry()
        p1 = FakeProvider(available=False)
        reg.register(p1)
        assert len(reg.get_all()) == 1

    def test_available_count(self):
        reg = ProviderRegistry()
        p1 = FakeProvider(available=True)
        reg.register(p1)
        assert reg.available_count == 1

    def test_available_count_zero(self):
        reg = ProviderRegistry()
        assert reg.available_count == 0

        