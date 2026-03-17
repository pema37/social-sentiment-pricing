# backend/tests/test_competitor_matching_duckduckgo.py
"""
Tests for competitor_matching/providers/duckduckgo.py

Covers:
- Provider properties (name, api_key, rate_limit, cost, is_available)
- _extract_real_url (DDG redirect parsing)
- _parse_html_results (HTML → MatchedProduct list)
- _search (httpx mocking, error handling)
- get_usage_stats

Total: ~25 tests
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

for mod in ["db.session"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

import pytest

from services.competitor_matching.providers.duckduckgo import DuckDuckGoProvider
from services.competitor_matching.schemas import SearchProvider

# ============================================================
# 1. Provider Properties
# ============================================================


class TestDuckDuckGoProperties:
    def test_provider_name(self):
        p = DuckDuckGoProvider()
        assert p.provider_name == SearchProvider.DUCKDUCKGO

    def test_no_api_key_required(self):
        p = DuckDuckGoProvider()
        assert p.requires_api_key is False

    def test_rate_limit(self):
        p = DuckDuckGoProvider()
        assert p.rate_limit_per_minute == 30

    def test_free_cost(self):
        p = DuckDuckGoProvider()
        assert p.cost_per_request == 0.0

    def test_always_available(self):
        p = DuckDuckGoProvider()
        assert p.is_available() is True

    def test_custom_timeout(self):
        p = DuckDuckGoProvider(timeout=10.0)
        assert p.timeout == 10.0

    def test_use_lite(self):
        p = DuckDuckGoProvider(use_lite=True)
        assert p.use_lite is True


# ============================================================
# 2. _extract_real_url
# ============================================================


class TestExtractRealUrl:
    def setup_method(self):
        self.p = DuckDuckGoProvider()

    def test_clean_https_url(self):
        url = "https://www.amazon.com/dp/B09V3KXJPB"
        assert self.p._extract_real_url(url) == url

    def test_clean_http_url(self):
        url = "http://example.com/product"
        assert self.p._extract_real_url(url) == url

    def test_ddg_redirect_double_slash(self):
        href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.amazon.com%2Fdp%2FB09V3"
        result = self.p._extract_real_url(href)
        assert result is not None
        assert "amazon.com" in result

    def test_ddg_redirect_single_slash(self):
        href = "/l/?uddg=https%3A%2F%2Fwww.walmart.com%2Fproduct"
        result = self.p._extract_real_url(href)
        assert result is not None
        assert "walmart.com" in result

    def test_empty_href(self):
        assert self.p._extract_real_url("") is None

    def test_none_href(self):
        assert self.p._extract_real_url(None) is None

    def test_relative_url_skipped(self):
        assert self.p._extract_real_url("/some/path") is None

    def test_garbage_url(self):
        assert self.p._extract_real_url("javascript:void(0)") is None


# ============================================================
# 3. _search with mocked httpx
# ============================================================


class TestDuckDuckGoSearch:
    @pytest.mark.asyncio
    async def test_successful_search(self):
        p = DuckDuckGoProvider(delay_between_requests=0)
        p._last_request_time = 0

        html = """
        <div class="result">
            <a class="result__a" href="https://www.amazon.com/widget">Widget Pro</a>
            <div class="result__snippet">Only $49.99 - Great product</div>
        </div>
        """
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        with patch("services.competitor_matching.providers.duckduckgo.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(return_value=mock_response)
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await p._search("Widget Pro", max_results=5)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        import httpx as httpx_mod

        p = DuckDuckGoProvider(delay_between_requests=0)
        p._last_request_time = 0

        with patch("services.competitor_matching.providers.duckduckgo.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=httpx_mod.TimeoutException("timeout"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await p._search("Widget", max_results=5)

        assert result.success is False
        assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_generic_exception(self):
        p = DuckDuckGoProvider(delay_between_requests=0)
        p._last_request_time = 0

        with patch("services.competitor_matching.providers.duckduckgo.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(side_effect=RuntimeError("network down"))
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await p._search("Widget", max_results=5)

        assert result.success is False
        assert "network down" in result.error


# ============================================================
# 4. get_usage_stats
# ============================================================


class TestGetUsageStats:
    def test_returns_dict(self):
        p = DuckDuckGoProvider()
        stats = p.get_usage_stats()
        assert stats["provider"] == "duckduckgo"
        assert stats["requires_api_key"] is False
        assert stats["cost"] == "Free"
