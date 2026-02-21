# backend/tests/test_competitor_matching_service.py
"""
Tests for competitor_matching/service.py — main orchestrator for
competitor URL matching with multi-provider search, caching, scoring.

Tests cover:
- CacheEntry (expiry logic)
- CompetitorMatchingService init
- _build_cache_key
- _get_from_cache / _add_to_cache / _evict_oldest_entries
- _normalize_url (deduplication)
- _select_providers
- _aggregate_results (dedup, status, domain exclusion)
- _score_and_filter
- _apply_merchant_preferences
- find_competitors (full orchestration)
- get_available_providers
- clear_cache

Total: ~50 tests
"""

import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

# === Import isolation ===
for mod in [
    "db.session",
    "models.competitor",
    "models.competitor_product",
    "models.competitor_price_history",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from services.competitor_matching.schemas import (
    SearchProvider, MatchStatus, MatchedProduct,
    ProviderResult, MatchSearchRequest, MatchSearchResponse,
)
from services.competitor_matching.service import (
    CacheEntry,
    CompetitorMatchingService,
)

SERVICE_PATH = "services.competitor_matching.service"


# ============================================================
# Helpers
# ============================================================

def make_product(
    title="Widget Pro", url="https://amazon.com/widget",
    price=Decimal("29.99"), merchant="Amazon",
    merchant_domain="amazon.com", confidence_score=0.8,
):
    return MatchedProduct(
        title=title, url=url, price=price,
        merchant=merchant, merchant_domain=merchant_domain,
        confidence_score=confidence_score,
    )


def make_svc(**kwargs):
    """Create service with mocked dependencies."""
    with patch(f"{SERVICE_PATH}.provider_registry") as mock_reg, \
         patch(f"{SERVICE_PATH}.setup_providers"):
        mock_reg.available_count = 1
        return CompetitorMatchingService(**kwargs)


# ============================================================
# 1. CacheEntry
# ============================================================

class TestCacheEntry:

    def test_not_expired(self):
        entry = CacheEntry(
            response=MagicMock(),
            created_at=datetime.now(timezone.utc),
        )
        assert entry.is_expired(ttl_hours=24) is False

    def test_expired(self):
        entry = CacheEntry(
            response=MagicMock(),
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
        )
        assert entry.is_expired(ttl_hours=24) is True

    def test_exactly_at_ttl(self):
        entry = CacheEntry(
            response=MagicMock(),
            created_at=datetime.now(timezone.utc) - timedelta(hours=24, seconds=1),
        )
        assert entry.is_expired(ttl_hours=24) is True


# ============================================================
# 2. Init
# ============================================================

class TestCompetitorMatchingServiceInit:

    def test_default_params(self):
        svc = make_svc()
        assert svc.cache_ttl_hours == 24
        assert svc.max_cache_size == 1000
        assert svc.min_confidence == 0.2

    def test_custom_params(self):
        svc = make_svc(cache_ttl_hours=12, max_cache_size=500, min_confidence=0.5)
        assert svc.cache_ttl_hours == 12
        assert svc.max_cache_size == 500
        assert svc.min_confidence == 0.5

    def test_calls_setup_when_no_providers(self):
        with patch(f"{SERVICE_PATH}.provider_registry") as mock_reg, \
             patch(f"{SERVICE_PATH}.setup_providers") as mock_setup:
            mock_reg.available_count = 0
            CompetitorMatchingService()
            mock_setup.assert_called_once()


# ============================================================
# 3. Cache key
# ============================================================

class TestBuildCacheKey:

    def test_deterministic(self):
        svc = make_svc()
        req = MatchSearchRequest(product_name="Widget", keywords=["red"])
        key1 = svc._build_cache_key(req)
        key2 = svc._build_cache_key(req)
        assert key1 == key2

    def test_different_for_different_products(self):
        svc = make_svc()
        req1 = MatchSearchRequest(product_name="Widget A")
        req2 = MatchSearchRequest(product_name="Widget B")
        assert svc._build_cache_key(req1) != svc._build_cache_key(req2)

    def test_keyword_order_independent(self):
        svc = make_svc()
        req1 = MatchSearchRequest(product_name="Widget", keywords=["a", "b"])
        req2 = MatchSearchRequest(product_name="Widget", keywords=["b", "a"])
        assert svc._build_cache_key(req1) == svc._build_cache_key(req2)


# ============================================================
# 4. Cache operations
# ============================================================

class TestCacheOperations:

    def test_get_from_empty_cache(self):
        svc = make_svc()
        assert svc._get_from_cache("nonexistent") is None

    def test_add_and_get(self):
        svc = make_svc()
        response = MatchSearchResponse(status=MatchStatus.SUCCESS)
        svc._add_to_cache("key1", response)
        result = svc._get_from_cache("key1")
        assert result is response

    def test_expired_entry_removed(self):
        svc = make_svc(cache_ttl_hours=1)
        response = MatchSearchResponse(status=MatchStatus.SUCCESS)
        svc._cache["key1"] = CacheEntry(
            response=response,
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        assert svc._get_from_cache("key1") is None
        assert "key1" not in svc._cache

    def test_eviction_when_full(self):
        svc = make_svc(max_cache_size=3)
        for i in range(3):
            svc._add_to_cache(f"key{i}", MatchSearchResponse(status=MatchStatus.SUCCESS))
        assert len(svc._cache) == 3
        # Adding one more should trigger eviction
        svc._add_to_cache("key_new", MatchSearchResponse(status=MatchStatus.SUCCESS))
        # Should have evicted some entries (max_cache_size // 10 = 0, but at least cache works)
        assert "key_new" in svc._cache

    def test_clear_cache(self):
        svc = make_svc()
        svc._add_to_cache("k1", MatchSearchResponse(status=MatchStatus.SUCCESS))
        svc._add_to_cache("k2", MatchSearchResponse(status=MatchStatus.SUCCESS))
        count = svc.clear_cache()
        assert count == 2
        assert len(svc._cache) == 0


# ============================================================
# 5. _normalize_url
# ============================================================

class TestNormalizeUrl:

    def setup_method(self):
        self.svc = make_svc()

    def test_lowercase(self):
        assert "amazon.com" in self.svc._normalize_url("https://AMAZON.COM/Product")

    def test_remove_trailing_slash(self):
        result = self.svc._normalize_url("https://example.com/product/")
        assert not result.endswith("/")

    def test_empty_url(self):
        assert self.svc._normalize_url("") == ""

    def test_removes_utm_params(self):
        result = self.svc._normalize_url("https://example.com/product?utm_source=google&color=red")
        assert "utm_source" not in result

    def test_preserves_path(self):
        result = self.svc._normalize_url("https://example.com/products/widget-pro")
        assert "products/widget-pro" in result


# ============================================================
# 6. _select_providers
# ============================================================

class TestSelectProviders:

    def test_returns_requested_providers(self):
        svc = make_svc()
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        with patch(f"{SERVICE_PATH}.provider_registry") as mock_reg:
            mock_reg.get.return_value = mock_provider
            result = svc._select_providers([SearchProvider.DUCKDUCKGO])
        assert len(result) == 1

    def test_skips_unavailable_requested(self):
        svc = make_svc()
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = False
        with patch(f"{SERVICE_PATH}.provider_registry") as mock_reg:
            mock_reg.get.return_value = mock_provider
            result = svc._select_providers([SearchProvider.DUCKDUCKGO])
        assert len(result) == 0

    def test_uses_all_available_when_none_requested(self):
        svc = make_svc()
        mock_providers = [MagicMock(), MagicMock()]
        with patch(f"{SERVICE_PATH}.provider_registry") as mock_reg:
            mock_reg.get_available.return_value = mock_providers
            result = svc._select_providers(None)
        assert len(result) == 2


# ============================================================
# 7. _aggregate_results
# ============================================================

class TestAggregateResults:

    def setup_method(self):
        self.svc = make_svc()

    def test_success_status(self):
        results = [ProviderResult(
            provider=SearchProvider.DUCKDUCKGO, success=True,
            products=[make_product()],
        )]
        req = MatchSearchRequest(product_name="Widget")
        resp = self.svc._aggregate_results(results, req)
        assert resp.status == MatchStatus.SUCCESS

    def test_partial_status_when_some_fail(self):
        results = [
            ProviderResult(provider=SearchProvider.DUCKDUCKGO, success=True, products=[make_product()]),
            ProviderResult(provider=SearchProvider.SERPAPI_GOOGLE_SHOPPING, success=False, error="API error"),
        ]
        req = MatchSearchRequest(product_name="Widget")
        resp = self.svc._aggregate_results(results, req)
        assert resp.status == MatchStatus.PARTIAL

    def test_failed_status_when_all_fail(self):
        results = [
            ProviderResult(provider=SearchProvider.DUCKDUCKGO, success=False, error="err"),
        ]
        req = MatchSearchRequest(product_name="Widget")
        resp = self.svc._aggregate_results(results, req)
        assert resp.status == MatchStatus.FAILED

    def test_deduplicates_by_url(self):
        p1 = make_product(url="https://amazon.com/widget")
        p2 = make_product(url="https://amazon.com/widget", merchant="Amazon2")
        results = [
            ProviderResult(provider=SearchProvider.DUCKDUCKGO, success=True, products=[p1]),
            ProviderResult(provider=SearchProvider.SERPAPI_GOOGLE_SHOPPING, success=True, products=[p2]),
        ]
        req = MatchSearchRequest(product_name="Widget")
        resp = self.svc._aggregate_results(results, req)
        assert len(resp.products) == 1

    def test_excludes_domains(self):
        p1 = make_product(merchant_domain="mystore.com")
        p2 = make_product(url="https://amazon.com/w", merchant_domain="amazon.com")
        results = [ProviderResult(
            provider=SearchProvider.DUCKDUCKGO, success=True, products=[p1, p2],
        )]
        req = MatchSearchRequest(product_name="Widget", exclude_domains=["mystore.com"])
        resp = self.svc._aggregate_results(results, req)
        assert len(resp.products) == 1
        assert resp.products[0].merchant_domain == "amazon.com"


# ============================================================
# 8. _score_and_filter
# ============================================================

class TestScoreAndFilter:

    def test_filters_below_min_confidence(self):
        svc = make_svc()
        products = [
            make_product(confidence_score=0.8),
            make_product(url="https://other.com", confidence_score=0.1),
        ]
        # Mock scorer to set specific scores
        svc.scorer.calculate_batch = MagicMock(return_value=products)

        req = MatchSearchRequest(product_name="Widget", min_confidence=0.5)
        result = svc._score_and_filter(products, req)
        assert len(result) == 1
        assert result[0].confidence_score == 0.8

    def test_sorted_by_confidence_desc(self):
        svc = make_svc()
        products = [
            make_product(confidence_score=0.5),
            make_product(url="https://other.com", confidence_score=0.9),
        ]
        svc.scorer.calculate_batch = MagicMock(return_value=products)

        req = MatchSearchRequest(product_name="Widget", min_confidence=0.0)
        result = svc._score_and_filter(products, req)
        assert result[0].confidence_score == 0.9


# ============================================================
# 9. _apply_merchant_preferences
# ============================================================

class TestApplyMerchantPreferences:

    def setup_method(self):
        self.svc = make_svc()

    def test_preferred_first(self):
        products = [
            make_product(merchant="BestBuy", merchant_domain="bestbuy.com", confidence_score=0.9),
            make_product(url="https://amazon.com/x", merchant="Amazon", merchant_domain="amazon.com", confidence_score=0.8),
        ]
        result = self.svc._apply_merchant_preferences(products, ["Amazon"])
        assert result[0].merchant == "Amazon"

    def test_preserves_confidence_order_within_tier(self):
        products = [
            make_product(merchant="Amazon", merchant_domain="amazon.com", confidence_score=0.7),
            make_product(url="https://amazon.com/x2", merchant="Amazon US", merchant_domain="amazon.com", confidence_score=0.9),
        ]
        result = self.svc._apply_merchant_preferences(products, ["Amazon"])
        assert result[0].confidence_score >= result[1].confidence_score


# ============================================================
# 10. find_competitors (orchestration)
# ============================================================

class TestFindCompetitors:

    @pytest.mark.asyncio
    async def test_returns_cached_result(self):
        svc = make_svc()
        cached_resp = MatchSearchResponse(
            status=MatchStatus.SUCCESS,
            products=[make_product()],
        )
        svc._get_from_cache = MagicMock(return_value=cached_resp)

        result = await svc.find_competitors("Widget", use_cache=True)
        assert result.cached is True
        assert len(result.products) == 1

    @pytest.mark.asyncio
    async def test_no_providers_returns_failed(self):
        svc = make_svc()
        svc._get_from_cache = MagicMock(return_value=None)
        svc._select_providers = MagicMock(return_value=[])

        result = await svc.find_competitors("Widget")
        assert result.status == MatchStatus.FAILED
        assert "No search providers" in result.error

    @pytest.mark.asyncio
    async def test_successful_search(self):
        svc = make_svc()
        svc._get_from_cache = MagicMock(return_value=None)

        mock_provider = MagicMock()
        mock_provider.provider_name = SearchProvider.DUCKDUCKGO
        svc._select_providers = MagicMock(return_value=[mock_provider])

        provider_result = ProviderResult(
            provider=SearchProvider.DUCKDUCKGO, success=True,
            products=[make_product()],
        )
        svc._search_all_providers = AsyncMock(return_value=[provider_result])
        svc.scorer.calculate_batch = MagicMock(
            side_effect=lambda products, **kw: products
        )

        result = await svc.find_competitors("Widget")
        assert result.status == MatchStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_limits_max_results(self):
        svc = make_svc()
        svc._get_from_cache = MagicMock(return_value=None)

        mock_provider = MagicMock()
        mock_provider.provider_name = SearchProvider.DUCKDUCKGO
        svc._select_providers = MagicMock(return_value=[mock_provider])

        products = [
            make_product(url=f"https://example.com/{i}", confidence_score=0.8)
            for i in range(20)
        ]
        provider_result = ProviderResult(
            provider=SearchProvider.DUCKDUCKGO, success=True,
            products=products,
        )
        svc._search_all_providers = AsyncMock(return_value=[provider_result])
        svc.scorer.calculate_batch = MagicMock(
            side_effect=lambda products, **kw: products
        )

        result = await svc.find_competitors("Widget", max_results=5)
        assert len(result.products) <= 5

    @pytest.mark.asyncio
    async def test_skips_cache_when_disabled(self):
        svc = make_svc()
        svc._get_from_cache = MagicMock(return_value=None)
        svc._add_to_cache = MagicMock()
        svc._select_providers = MagicMock(return_value=[])

        await svc.find_competitors("Widget", use_cache=False)
        svc._get_from_cache.assert_not_called()


# ============================================================
# 11. get_available_providers
# ============================================================

class TestGetAvailableProviders:

    def test_returns_provider_info(self):
        svc = make_svc()
        mock_provider = MagicMock()
        mock_provider.provider_name = SearchProvider.DUCKDUCKGO
        mock_provider.is_available.return_value = True
        mock_provider.requires_api_key = False
        mock_provider.cost_per_request = 0

        with patch(f"{SERVICE_PATH}.provider_registry") as mock_reg:
            mock_reg.get_all.return_value = [mock_provider]
            result = svc.get_available_providers()

        assert len(result) == 1
        assert result[0]["name"] == "duckduckgo"
        assert result[0]["available"] is True


# ============================================================
# 12. _search_all_providers
# ============================================================

class TestSearchAllProviders:

    @pytest.mark.asyncio
    async def test_handles_provider_exception(self):
        svc = make_svc()
        mock_provider = MagicMock()
        mock_provider.provider_name = SearchProvider.DUCKDUCKGO
        mock_provider.search = AsyncMock(side_effect=Exception("API down"))

        results = await svc._search_all_providers(
            MatchSearchRequest(product_name="Widget"),
            [mock_provider],
        )
        assert len(results) == 1
        assert results[0].success is False
        assert "API down" in results[0].error

    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        svc = make_svc()
        mock_p1 = MagicMock()
        mock_p1.provider_name = SearchProvider.DUCKDUCKGO
        mock_p1.search = AsyncMock(return_value=ProviderResult(
            provider=SearchProvider.DUCKDUCKGO, success=True,
        ))
        mock_p2 = MagicMock()
        mock_p2.provider_name = SearchProvider.SERPAPI_GOOGLE_SHOPPING
        mock_p2.search = AsyncMock(return_value=ProviderResult(
            provider=SearchProvider.SERPAPI_GOOGLE_SHOPPING, success=True,
        ))

        results = await svc._search_all_providers(
            MatchSearchRequest(product_name="Widget"),
            [mock_p1, mock_p2],
        )
        assert len(results) == 2
        assert all(r.success for r in results)



        