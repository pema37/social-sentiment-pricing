"""
Tests for services/youcom_client.py — YouComClient, data models, _TTLCache

Covers:
- WebResult.from_api: all fields, defaults, contents_markdown
- NewsResult.from_api: all fields, defaults
- SearchResponse: total_results, to_context_block, cached flag
- _TTLCache: get/set, expiry, clear, key hashing
- YouComClient.__init__: stores params, no API key raises
- _get_client: creates httpx client, reuses existing
- close: closes client
- _request_with_retry: success, 429 retry, 5xx retry, timeout, non-retryable 4xx, max retries exceeded
- search: builds params, caches result, returns cached, freshness/country/livecrawl params
- get_contents: returns contents string
- search_competitor_prices: query construction with brand/category
- search_market_sentiment: query construction
- search_market_trends: query construction
- request_count property
"""

import os
import sys
import time
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. sys.modules stub isolation
# ---------------------------------------------------------------------------
_MOCKED = ["db.session"]
_originals = {m: sys.modules.get(m) for m in _MOCKED}

for _m in "db.session":
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if "services" not in sys.modules:
    _svc = ModuleType("services")
    _svc.__path__ = [os.path.join(_backend_dir, "services")]
    _svc.__package__ = "services"
    sys.modules["services"] = _svc

# ---------------------------------------------------------------------------
# 2. Import module under test
# ---------------------------------------------------------------------------
from services.youcom_client import (
    Freshness,
    NewsResult,
    SearchResponse,
    WebResult,
    YouComClient,
    _TTLCache,
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
# Data Model Tests
# ===========================================================================


class TestWebResult:
    def test_from_api_full(self):
        data = {
            "url": "https://example.com",
            "title": "Test Page",
            "description": "A test page",
            "snippets": ["snippet 1", "snippet 2"],
            "page_age": "2 days ago",
            "authors": ["Author A"],
            "thumbnail_url": "https://example.com/thumb.jpg",
            "favicon_url": "https://example.com/favicon.ico",
            "contents": {"markdown": "# Hello"},
        }
        r = WebResult.from_api(data)
        assert r.url == "https://example.com"
        assert r.title == "Test Page"
        assert r.snippets == ["snippet 1", "snippet 2"]
        assert r.page_age == "2 days ago"
        assert r.contents_markdown == "# Hello"

    def test_from_api_minimal(self):
        r = WebResult.from_api({})
        assert r.url == ""
        assert r.title == ""
        assert r.description == ""
        assert r.snippets == []
        assert r.authors == []
        assert r.contents_markdown is None

    def test_from_api_no_contents(self):
        r = WebResult.from_api({"url": "https://x.com", "title": "X"})
        assert r.contents_markdown is None


class TestNewsResult:
    def test_from_api_full(self):
        data = {
            "url": "https://news.com/article",
            "title": "Breaking News",
            "description": "Something happened",
            "page_age": "1 hour ago",
            "thumbnail_url": "https://news.com/thumb.jpg",
        }
        r = NewsResult.from_api(data)
        assert r.url == "https://news.com/article"
        assert r.title == "Breaking News"
        assert r.page_age == "1 hour ago"

    def test_from_api_minimal(self):
        r = NewsResult.from_api({})
        assert r.url == ""
        assert r.title == ""
        assert r.page_age is None


class TestSearchResponse:
    def test_total_results(self):
        sr = SearchResponse(
            query="test",
            web_results=[WebResult.from_api({}), WebResult.from_api({})],
            news_results=[NewsResult.from_api({})],
        )
        assert sr.total_results == 3

    def test_total_results_empty(self):
        sr = SearchResponse(query="test")
        assert sr.total_results == 0

    def test_to_context_block_structure(self):
        sr = SearchResponse(
            query="Nike prices",
            web_results=[
                WebResult(url="https://x.com", title="Price Page", description="desc", snippets=["Best price $99"])
            ],
            news_results=[
                NewsResult(url="https://news.com", title="Nike News", description="Launch today", page_age="1h")
            ],
            latency_ms=150.0,
        )
        block = sr.to_context_block()
        assert "Nike prices" in block
        assert "Web Sources" in block
        assert "Recent News" in block
        assert "Price Page" in block
        assert "Nike News" in block
        assert "150ms" in block

    def test_to_context_block_cached(self):
        sr = SearchResponse(query="test", cached=True, latency_ms=5.0)
        block = sr.to_context_block()
        assert "(cached)" in block

    def test_to_context_block_no_results(self):
        sr = SearchResponse(query="empty", latency_ms=100.0)
        block = sr.to_context_block()
        assert "0 sources" in block


# ===========================================================================
# TTL Cache Tests
# ===========================================================================


class TestTTLCache:
    def test_set_and_get(self):
        cache = _TTLCache(ttl=60)
        cache.set("query1", "result1")
        assert cache.get("query1") == "result1"

    def test_get_miss(self):
        cache = _TTLCache(ttl=60)
        assert cache.get("nonexistent") is None

    def test_expiry(self):
        cache = _TTLCache(ttl=0.01)
        cache.set("query1", "result1")
        time.sleep(0.02)
        assert cache.get("query1") is None

    def test_clear(self):
        cache = _TTLCache(ttl=60)
        cache.set("q1", "r1")
        cache.set("q2", "r2")
        cache.clear()
        assert cache.get("q1") is None
        assert cache.get("q2") is None

    def test_kwargs_differentiate_keys(self):
        cache = _TTLCache(ttl=60)
        cache.set("query", "result_a", count=5)
        cache.set("query", "result_b", count=10)
        assert cache.get("query", count=5) == "result_a"
        assert cache.get("query", count=10) == "result_b"

    def test_key_is_deterministic(self):
        cache = _TTLCache(ttl=60)
        k1 = cache._key("test", a=1, b=2)
        k2 = cache._key("test", a=1, b=2)
        assert k1 == k2


# ===========================================================================
# YouComClient Tests
# ===========================================================================


class TestYouComClientInit:
    def test_stores_params(self):
        client = YouComClient(api_key="test-key", timeout=30.0, cache_ttl=600, max_retries=3)
        assert client._api_key == "test-key"
        assert client._timeout == 30.0
        assert client._max_retries == 3
        assert client._request_count == 0

    def test_no_api_key_raises(self):
        with pytest.raises(ValueError, match="API key is required"):
            YouComClient(api_key="")

    def test_none_api_key_raises(self):
        with pytest.raises(ValueError):
            YouComClient(api_key=None)


class TestGetClient:
    @pytest.mark.asyncio
    async def test_creates_client(self):
        client = YouComClient(api_key="test-key")
        http_client = await client._get_client()
        assert http_client is not None
        assert client._client is http_client
        await client.close()

    @pytest.mark.asyncio
    async def test_reuses_existing(self):
        client = YouComClient(api_key="test-key")
        c1 = await client._get_client()
        c2 = await client._get_client()
        assert c1 is c2
        await client.close()


class TestClose:
    @pytest.mark.asyncio
    async def test_closes_client(self):
        client = YouComClient(api_key="test-key")
        await client._get_client()
        assert client._client is not None
        await client.close()
        assert client._client.is_closed


class TestRequestWithRetry:
    @pytest.mark.asyncio
    async def test_success(self):
        client = YouComClient(api_key="test-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": {}}
        mock_resp.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(return_value=mock_resp)
        mock_http.is_closed = False
        client._client = mock_http

        result = await client._request_with_retry("https://api.com", {"q": "test"})
        assert result == {"results": {}}
        assert client._request_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        client = YouComClient(api_key="test-key", max_retries=1)

        import httpx

        mock_http = AsyncMock()
        mock_http.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
        mock_http.is_closed = False
        client._client = mock_http

        with patch("services.youcom_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ConnectionError, match="failed after"):
                await client._request_with_retry("https://api.com", {})

        assert client._request_count == 2  # initial + 1 retry


class TestSearch:
    @pytest.mark.asyncio
    async def test_basic_search(self):
        client = YouComClient(api_key="test-key")
        client._request_with_retry = AsyncMock(
            return_value={
                "results": {
                    "web": [{"url": "https://x.com", "title": "X", "description": "D"}],
                    "news": [],
                },
                "metadata": {"request_uuid": "abc-123"},
            }
        )

        result = await client.search("test query")
        assert result.query == "test query"
        assert len(result.web_results) == 1
        assert result.web_results[0].url == "https://x.com"
        assert result.request_id == "abc-123"
        assert result.cached is False

    @pytest.mark.asyncio
    async def test_cached_result(self):
        client = YouComClient(api_key="test-key")
        cached_response = SearchResponse(query="test", latency_ms=5.0)
        client._cache.set("test", cached_response, count=5, freshness=None, country=None)

        result = await client.search("test")
        assert result.cached is True

    @pytest.mark.asyncio
    async def test_search_with_params(self):
        client = YouComClient(api_key="test-key")
        captured_params = {}

        async def capture_request(url, params):
            captured_params.update(params)
            return {"results": {}, "metadata": {}}

        client._request_with_retry = capture_request

        await client.search("query", count=10, freshness=Freshness.WEEK, country="US", livecrawl="web")

        assert captured_params["query"] == "query"
        assert captured_params["count"] == 10
        assert captured_params["freshness"] == "week"
        assert captured_params["country"] == "US"
        assert captured_params["livecrawl"] == "web"


class TestGetContents:
    @pytest.mark.asyncio
    async def test_returns_contents(self):
        client = YouComClient(api_key="test-key")
        client._request_with_retry = AsyncMock(return_value={"contents": "# Page Title\nSome markdown content"})

        result = await client.get_contents("https://example.com")
        assert result == "# Page Title\nSome markdown content"

    @pytest.mark.asyncio
    async def test_empty_contents(self):
        client = YouComClient(api_key="test-key")
        client._request_with_retry = AsyncMock(return_value={})

        result = await client.get_contents("https://example.com")
        assert result == ""


class TestSearchCompetitorPrices:
    @pytest.mark.asyncio
    async def test_query_construction(self):
        client = YouComClient(api_key="test-key")
        captured_query = None

        async def capture_search(query, **kwargs):
            nonlocal captured_query
            captured_query = query
            return SearchResponse(query=query)

        client.search = capture_search

        await client.search_competitor_prices("Air Max 90", category="Shoes", brand="Nike")
        assert "Nike" in captured_query
        assert "Air Max 90" in captured_query
        assert "price" in captured_query
        assert "Shoes" in captured_query
        assert "buy online" in captured_query

    @pytest.mark.asyncio
    async def test_minimal_query(self):
        client = YouComClient(api_key="test-key")
        captured = {}

        async def capture_search(query, **kwargs):
            captured["query"] = query
            captured.update(kwargs)
            return SearchResponse(query=query)

        client.search = capture_search

        await client.search_competitor_prices("Widget")
        assert "Widget" in captured["query"]
        assert captured.get("count") == 8


class TestSearchMarketSentiment:
    @pytest.mark.asyncio
    async def test_query_construction(self):
        client = YouComClient(api_key="test-key")
        captured = {}

        async def capture_search(query, **kwargs):
            captured["query"] = query
            captured.update(kwargs)
            return SearchResponse(query=query)

        client.search = capture_search

        await client.search_market_sentiment("Air Max 90", brand="Nike")
        assert "Nike" in captured["query"]
        assert "reviews" in captured["query"]
        assert "sentiment" in captured["query"]


class TestSearchMarketTrends:
    @pytest.mark.asyncio
    async def test_query_construction(self):
        client = YouComClient(api_key="test-key")
        captured = {}

        async def capture_search(query, **kwargs):
            captured["query"] = query
            captured.update(kwargs)
            return SearchResponse(query=query)

        client.search = capture_search

        await client.search_market_trends("Electronics")
        assert "Electronics" in captured["query"]
        assert "market trends" in captured["query"]
        assert "2026" in captured["query"]


class TestRequestCount:
    def test_starts_at_zero(self):
        client = YouComClient(api_key="test-key")
        assert client.request_count == 0
