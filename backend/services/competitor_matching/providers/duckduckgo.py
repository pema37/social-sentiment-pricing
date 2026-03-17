# backend/services/competitor_matching/providers/duckduckgo.py

"""
DuckDuckGo Search Provider

Free fallback provider that requires no API key.
Uses DuckDuckGo's HTML interface to scrape results.

Pros:
- Completely free
- No API key required
- No rate limits (within reason)
- Privacy-focused

Cons:
- Less reliable than paid APIs
- No structured product data
- Price extraction is best-effort
- May break if DDG changes HTML structure

Use this as a fallback when paid providers are unavailable.
"""

import asyncio
import logging
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from ..schemas import (
    MatchedProduct,
    ProviderResult,
    SearchProvider,
)
from ..utils import extract_price_from_text
from .base import BaseSearchProvider

logger = logging.getLogger(__name__)


class DuckDuckGoProvider(BaseSearchProvider):
    """
    DuckDuckGo search provider.

    Free fallback that scrapes DDG's HTML interface.
    No API key needed, but results are less structured.
    """

    # DDG HTML search endpoint
    ENDPOINT = "https://html.duckduckgo.com/html/"

    # Alternative: DDG lite
    LITE_ENDPOINT = "https://lite.duckduckgo.com/lite/"

    # User agent to avoid blocking
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        timeout: float = 30.0,
        use_lite: bool = False,
        delay_between_requests: float = 1.0,
    ):
        """
        Initialize DuckDuckGo provider.

        Args:
            timeout: Request timeout in seconds
            use_lite: Use lite version (simpler HTML)
            delay_between_requests: Delay to avoid rate limiting
        """
        self.timeout = timeout
        self.use_lite = use_lite
        self.delay = delay_between_requests

        self._last_request_time: float = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Property Implementations
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def provider_name(self) -> SearchProvider:
        return SearchProvider.DUCKDUCKGO

    @property
    def requires_api_key(self) -> bool:
        return False  # Free!

    @property
    def rate_limit_per_minute(self) -> int:
        return 30  # Be respectful

    @property
    def cost_per_request(self) -> float:
        return 0.0  # Free

    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Method Implementations
    # ─────────────────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """DuckDuckGo is always available (no API key needed)."""
        return True

    async def _search(
        self,
        query: str,
        max_results: int,
        **kwargs,
    ) -> ProviderResult:
        """
        Search using DuckDuckGo HTML interface.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            ProviderResult with products
        """
        # Rate limiting - be respectful
        await self._respect_rate_limit()

        # Add shopping keywords to improve results
        shopping_query = f"{query} buy price shop"

        endpoint = self.LITE_ENDPOINT if self.use_lite else self.ENDPOINT

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        data = {
            "q": shopping_query,
            "b": "",  # No pagination offset
            "kl": "us-en",  # US English
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint,
                    data=data,
                    headers=headers,
                    follow_redirects=True,
                )
                response.raise_for_status()
                html = response.text

            # Parse results
            products = self._parse_html_results(html, max_results * 2)

            return ProviderResult(
                provider=self.provider_name,
                success=True,
                products=products[:max_results],
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"

            if e.response.status_code == 403:
                error_msg = "Blocked by DuckDuckGo (try again later)"
            elif e.response.status_code == 503:
                error_msg = "DuckDuckGo temporarily unavailable"

            return ProviderResult(
                provider=self.provider_name,
                success=False,
                error=error_msg,
            )

        except httpx.TimeoutException:
            return ProviderResult(
                provider=self.provider_name,
                success=False,
                error="Request timeout",
            )

        except Exception as e:
            logger.exception(f"DuckDuckGo error: {e}")
            return ProviderResult(
                provider=self.provider_name,
                success=False,
                error=str(e),
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_html_results(self, html: str, max_results: int) -> list[MatchedProduct]:
        """
        Parse DuckDuckGo HTML results.

        Args:
            html: Raw HTML response
            max_results: Maximum results to parse

        Returns:
            List of MatchedProduct
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("BeautifulSoup not installed. Run: pip install beautifulsoup4")
            return []

        soup = BeautifulSoup(html, "html.parser")
        products = []

        # Find result containers
        # DDG HTML uses .result class
        results = soup.select(".result")

        if not results:
            # Try alternative selectors
            results = soup.select(".links_main")

        if not results:
            # Lite version uses different structure
            results = soup.select("tr")

        for result in results:
            if len(products) >= max_results:
                break

            product = self._parse_result_element(result)
            if product:
                products.append(product)

        return products

    def _parse_result_element(self, element) -> MatchedProduct | None:
        """
        Parse a single result element.

        Args:
            element: BeautifulSoup element

        Returns:
            MatchedProduct or None
        """
        # Try to find link
        link_elem = (
            element.select_one(".result__a") or element.select_one("a.result__url") or element.select_one("a[href]")
        )

        if not link_elem:
            return None

        # Extract URL
        href = link_elem.get("href", "")
        url = self._extract_real_url(href)

        if not url:
            return None

        # Extract title
        title = link_elem.get_text(strip=True)

        # Try to get better title from heading
        title_elem = element.select_one(".result__title")
        if title_elem:
            title = title_elem.get_text(strip=True)

        if not title:
            return None

        # Extract snippet for price
        snippet = ""
        snippet_elem = (
            element.select_one(".result__snippet")
            or element.select_one(".result__body")
            or element.select_one("td:last-child")
        )
        if snippet_elem:
            snippet = snippet_elem.get_text(strip=True)

        # Try to extract price from snippet
        price = extract_price_from_text(snippet)

        # Also try from title
        if not price:
            price = extract_price_from_text(title)

        # Use helper from base class
        return self._create_product(
            title=title,
            url=url,
            price=price,
            raw_data={"snippet": snippet},
        )

    def _extract_real_url(self, href: str) -> str | None:
        """
        Extract real URL from DuckDuckGo redirect URL.

        DDG wraps URLs like:
        //duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.amazon.com%2F...

        Args:
            href: Raw href from DDG

        Returns:
            Real URL or None
        """
        if not href:
            return None

        # If it's already a clean URL
        if href.startswith("http://") or href.startswith("https://"):
            return href

        # Handle DDG redirect format
        if "uddg=" in href:
            try:
                # Parse the redirect URL
                if href.startswith("//"):
                    href = "https:" + href
                elif href.startswith("/"):
                    href = "https://duckduckgo.com" + href

                parsed = urlparse(href)
                params = parse_qs(parsed.query)

                if "uddg" in params:
                    real_url = unquote(params["uddg"][0])
                    return real_url
            except Exception as e:
                self._log_debug(f"Failed to parse DDG URL: {e}")
                return None

        # Handle relative URLs (shouldn't happen but just in case)
        if href.startswith("/"):
            return None  # Skip relative URLs

        return None

    async def _respect_rate_limit(self) -> None:
        """
        Ensure we don't hit DDG too fast.

        Adds delay between requests to be respectful.
        """
        import time

        now = time.time()
        elapsed = now - self._last_request_time

        if elapsed < self.delay:
            wait_time = self.delay - elapsed
            self._log_debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        self._last_request_time = time.time()

    # ─────────────────────────────────────────────────────────────────────────
    # Public Utility Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        return {
            "provider": self.provider_name.value,
            "requires_api_key": False,
            "cost": "Free",
            "note": "No usage limits tracked (be respectful)",
        }
