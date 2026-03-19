"""
You.com API Client for ActualPrice Market Intelligence.

Integrates You.com Search, News, and Contents APIs to provide
live web data for the multi-agent pricing pipeline.

DeveloperWeek 2026 Hackathon - You.com Challenge Track
"""

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

YOUCOM_BASE_URL = "https://ydc-index.io"
YOUCOM_SEARCH_ENDPOINT = f"{YOUCOM_BASE_URL}/v1/search"
YOUCOM_NEWS_ENDPOINT = f"{YOUCOM_BASE_URL}/v1/news"
YOUCOM_CONTENTS_ENDPOINT = f"{YOUCOM_BASE_URL}/v1/contents"

DEFAULT_SEARCH_COUNT = 5
DEFAULT_NEWS_COUNT = 5
DEFAULT_TIMEOUT = 15.0
CACHE_TTL_SECONDS = 300  # 5 min cache for repeated queries
MAX_RETRIES = 2
RETRY_BACKOFF_BASE = 1.5


class Freshness(StrEnum):
    """You.com freshness filter options."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class WebResult:
    """Single web search result from You.com."""

    url: str
    title: str
    description: str
    snippets: list[str] = field(default_factory=list)
    page_age: str | None = None
    authors: list[str] = field(default_factory=list)
    thumbnail_url: str | None = None
    favicon_url: str | None = None
    contents_markdown: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> "WebResult":
        contents = data.get("contents", {})
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            snippets=data.get("snippets", []),
            page_age=data.get("page_age"),
            authors=data.get("authors", []),
            thumbnail_url=data.get("thumbnail_url"),
            favicon_url=data.get("favicon_url"),
            contents_markdown=contents.get("markdown") if contents else None,
        )


@dataclass
class NewsResult:
    """Single news result from You.com."""

    url: str
    title: str
    description: str
    page_age: str | None = None
    thumbnail_url: str | None = None

    @classmethod
    def from_api(cls, data: dict) -> "NewsResult":
        return cls(
            url=data.get("url", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            page_age=data.get("page_age"),
            thumbnail_url=data.get("thumbnail_url"),
        )


@dataclass
class SearchResponse:
    """Combined search response with web and news results."""

    query: str
    web_results: list[WebResult] = field(default_factory=list)
    news_results: list[NewsResult] = field(default_factory=list)
    latency_ms: float = 0.0
    request_id: str | None = None
    cached: bool = False

    @property
    def total_results(self) -> int:
        return len(self.web_results) + len(self.news_results)

    def to_context_block(self) -> str:
        """Format results as a context block for LLM consumption."""
        parts = [f"## Live Web Intelligence for: {self.query}\n"]

        if self.web_results:
            parts.append("### Web Sources")
            for i, r in enumerate(self.web_results, 1):
                snippets_text = " ".join(r.snippets[:3])
                parts.append(f"{i}. **{r.title}**\n   URL: {r.url}\n   {snippets_text}\n")

        if self.news_results:
            parts.append("\n### Recent News")
            for i, n in enumerate(self.news_results, 1):
                parts.append(
                    f"{i}. **{n.title}**\n"
                    f"   URL: {n.url}\n"
                    f"   {n.description}\n"
                    f"   Published: {n.page_age or 'Unknown'}\n"
                )

        parts.append(
            f"\n*{self.total_results} sources retrieved in {self.latency_ms:.0f}ms{' (cached)' if self.cached else ''}*"
        )
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------


class _TTLCache:
    """Simple TTL cache to avoid hammering You.com for repeated queries."""

    def __init__(self, ttl: float = CACHE_TTL_SECONDS):
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl

    def _key(self, query: str, **kwargs) -> str:
        raw = f"{query}|{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, query: str, **kwargs) -> Any | None:
        key = self._key(query, **kwargs)
        if key in self._store:
            ts, value = self._store[key]
            if time.time() - ts < self._ttl:
                return value
            del self._store[key]
        return None

    def set(self, query: str, value: Any, **kwargs) -> None:
        key = self._key(query, **kwargs)
        self._store[key] = (time.time(), value)

    def clear(self) -> None:
        self._store.clear()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class YouComClient:
    """
    Async client for You.com APIs.

    Usage:
        client = YouComClient(api_key="your-key")
        results = await client.search("Nike Air Max price comparison")
    """

    def __init__(
        self,
        api_key: str,
        timeout: float = DEFAULT_TIMEOUT,
        cache_ttl: float = CACHE_TTL_SECONDS,
        max_retries: int = MAX_RETRIES,
    ):
        if not api_key:
            raise ValueError("You.com API key is required. Get one at api.you.com")
        self._api_key = api_key
        self._timeout = timeout
        self._max_retries = max_retries
        self._cache = _TTLCache(ttl=cache_ttl)
        self._client: httpx.AsyncClient | None = None
        self._request_count = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "X-API-Key": self._api_key,
                    "Accept": "application/json",
                    "User-Agent": "ActualPrice/1.0 (DeveloperWeek2026)",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request_with_retry(self, url: str, params: dict) -> dict:
        """Execute HTTP GET with exponential backoff retry."""
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                self._request_count += 1
                resp = await client.get(url, params=params)

                if resp.status_code == 429:
                    wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning("You.com rate limited (429). Retrying in %.1fs", wait)
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp.json()

            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "You.com request timed out (attempt %d/%d)",
                    attempt + 1,
                    self._max_retries + 1,
                )
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in (500, 502, 503):
                    wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        "You.com server error %d. Retrying in %.1fs",
                        exc.response.status_code,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise  # 4xx (non-429) errors are not retryable
            except httpx.RequestError as exc:
                last_exc = exc
                logger.warning("You.com request error: %s", exc)

            if attempt < self._max_retries:
                await asyncio.sleep(RETRY_BACKOFF_BASE**attempt)

        raise ConnectionError(f"You.com API failed after {self._max_retries + 1} attempts: {last_exc}")

    # ----- Public API -----

    async def search(
        self,
        query: str,
        count: int = DEFAULT_SEARCH_COUNT,
        freshness: Freshness | None = None,
        country: str | None = None,
        livecrawl: str | None = None,
    ) -> SearchResponse:
        """
        Search You.com for web and news results.

        Args:
            query: Search terms (e.g. "Nike Air Max 90 price competitor")
            count: Max results per section (web/news). Default 5.
            freshness: Time filter - day/week/month/year
            country: ISO 3166-2 code for geo targeting (e.g. "US")
            livecrawl: "web", "news", or "all" for full-page content

        Returns:
            SearchResponse with web_results, news_results, and metadata
        """
        cache_kwargs = dict(
            count=count,
            freshness=freshness.value if freshness else None,
            country=country,
        )
        cached = self._cache.get(query, **cache_kwargs)
        if cached:
            cached.cached = True
            return cached

        params: dict[str, Any] = {"query": query, "count": count}
        if freshness:
            params["freshness"] = freshness.value
        if country:
            params["country"] = country
        if livecrawl:
            params["livecrawl"] = livecrawl

        start = time.time()
        data = await self._request_with_retry(YOUCOM_SEARCH_ENDPOINT, params)
        elapsed_ms = (time.time() - start) * 1000

        results_data = data.get("results", {})
        metadata = data.get("metadata", {})

        response = SearchResponse(
            query=query,
            web_results=[WebResult.from_api(r) for r in results_data.get("web", [])],
            news_results=[NewsResult.from_api(r) for r in results_data.get("news", [])],
            latency_ms=elapsed_ms,
            request_id=metadata.get("request_uuid"),
        )

        self._cache.set(query, response, **cache_kwargs)
        logger.info(
            "You.com search: %r → %d web + %d news (%.0fms)",
            query,
            len(response.web_results),
            len(response.news_results),
            elapsed_ms,
        )
        return response

    async def get_contents(self, url: str, output_format: str = "markdown") -> str:
        """
        Fetch full page content from a URL via You.com Contents API.

        Args:
            url: Target webpage URL
            output_format: "markdown" or "html"

        Returns:
            Page content as string
        """
        params = {"url": url, "format": output_format}
        data = await self._request_with_retry(YOUCOM_CONTENTS_ENDPOINT, params)
        return data.get("contents", "")

    async def search_competitor_prices(
        self,
        product_name: str,
        category: str | None = None,
        brand: str | None = None,
    ) -> SearchResponse:
        """
        Specialized search for competitor pricing data.

        Constructs optimized queries for e-commerce price intelligence.
        """
        query_parts = [product_name, "price"]
        if brand:
            query_parts.insert(0, brand)
        if category:
            query_parts.append(category)
        query_parts.append("buy online")

        query = " ".join(query_parts)
        return await self.search(
            query=query,
            count=8,
            freshness=Freshness.MONTH,
            country="US",
        )

    async def search_market_sentiment(
        self,
        product_name: str,
        brand: str | None = None,
    ) -> SearchResponse:
        """
        Search for social sentiment and reviews about a product.
        """
        query_parts = [product_name]
        if brand:
            query_parts.insert(0, brand)
        query_parts.extend(["reviews", "sentiment", "opinions"])

        return await self.search(
            query=" ".join(query_parts),
            count=5,
            freshness=Freshness.WEEK,
        )

    async def search_market_trends(
        self,
        category: str,
        freshness: Freshness = Freshness.WEEK,
    ) -> SearchResponse:
        """
        Search for market trends and industry news in a category.
        """
        return await self.search(
            query=f"{category} market trends pricing 2026",
            count=5,
            freshness=freshness,
        )

    @property
    def request_count(self) -> int:
        return self._request_count
