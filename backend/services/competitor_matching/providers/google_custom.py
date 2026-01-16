# backend/services/competitor_matching/providers/google_custom.py

"""
Google Custom Search Provider

Google Custom Search API provides:
- 100 free searches per day
- General web results (not shopping-specific)
- Requires setup of Custom Search Engine

Setup:
1. Create project at https://console.cloud.google.com
2. Enable "Custom Search API"
3. Create API key
4. Create Custom Search Engine at https://cse.google.com
5. Get the Search Engine ID (cx)

Docs: https://developers.google.com/custom-search/v1/overview
"""

import os
import logging
from typing import Optional, List, Dict, Any

import httpx

from .base import BaseSearchProvider
from ..models import (
    SearchProvider,
    MatchedProduct,
    ProviderResult,
)
from ..utils import extract_price_from_text


logger = logging.getLogger(__name__)


class GoogleCustomSearchProvider(BaseSearchProvider):
    """
    Google Custom Search API provider.
    
    Good free option with 100 searches/day.
    Results are web pages, not shopping-specific,
    so price extraction is less reliable.
    """

    ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        search_engine_id: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize Google Custom Search provider.
        
        Args:
            api_key: Google API key (or set GOOGLE_API_KEY env var)
            search_engine_id: Custom Search Engine ID (or set GOOGLE_SEARCH_CX env var)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.search_engine_id = search_engine_id or os.getenv("GOOGLE_SEARCH_CX")
        self.timeout = timeout
        
        # Track daily usage (resets at midnight)
        self._daily_requests = 0
        self._last_reset_date: Optional[str] = None

    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Property Implementations
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def provider_name(self) -> SearchProvider:
        return SearchProvider.GOOGLE_CUSTOM_SEARCH

    @property
    def requires_api_key(self) -> bool:
        return True

    @property
    def rate_limit_per_minute(self) -> int:
        return 60

    @property
    def cost_per_request(self) -> float:
        # Free for first 100/day, then $5 per 1000
        return 0.0 if self._daily_requests < 100 else 0.005

    @property
    def daily_free_limit(self) -> int:
        return 100

    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Method Implementations
    # ─────────────────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if Google Custom Search is configured."""
        return bool(self.api_key and self.search_engine_id)

    async def _search(
        self,
        query: str,
        max_results: int,
        **kwargs,
    ) -> ProviderResult:
        """
        Search using Google Custom Search API.
        
        Args:
            query: Search query
            max_results: Maximum results (API max is 10 per request)
            
        Returns:
            ProviderResult with products
        """
        # Reset daily counter if needed
        self._check_daily_reset()

        # Add shopping intent to query
        shopping_query = f"{query} buy price shop"

        # API returns max 10 results per request
        num_results = min(max_results, 10)

        params = {
            "key": self.api_key,
            "cx": self.search_engine_id,
            "q": shopping_query,
            "num": num_results,
            "safe": "active",
        }

        # Optional: restrict to specific sites
        if kwargs.get("site_restrict"):
            params["siteSearch"] = kwargs["site_restrict"]
            params["siteSearchFilter"] = "i"  # include only

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.ENDPOINT, params=params)
                response.raise_for_status()
                data = response.json()

            self._daily_requests += 1

            # Check for errors
            if "error" in data:
                error_info = data["error"]
                error_msg = error_info.get("message", "Unknown error")
                
                # Check for quota exceeded
                if error_info.get("code") == 429:
                    return ProviderResult(
                        provider=self.provider_name,
                        success=False,
                        error="Daily quota exceeded (100 free searches)",
                        rate_limited=True,
                    )
                
                return ProviderResult(
                    provider=self.provider_name,
                    success=False,
                    error=error_msg,
                )

            # Parse results
            products = self._parse_results(data)

            return ProviderResult(
                provider=self.provider_name,
                success=True,
                products=products,
                credits_used=1,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"
            
            if e.response.status_code == 403:
                # Try to get error details
                try:
                    error_data = e.response.json()
                    if "dailyLimitExceeded" in str(error_data):
                        error_msg = "Daily quota exceeded"
                        return ProviderResult(
                            provider=self.provider_name,
                            success=False,
                            error=error_msg,
                            rate_limited=True,
                        )
                except Exception:
                    pass
                error_msg = "API access forbidden - check API key"
            elif e.response.status_code == 400:
                error_msg = "Invalid request - check search engine ID"
            
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
            logger.exception(f"Google Custom Search error: {e}")
            return ProviderResult(
                provider=self.provider_name,
                success=False,
                error=str(e),
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_results(self, data: Dict[str, Any]) -> List[MatchedProduct]:
        """
        Parse Google Custom Search results.
        
        Args:
            data: Raw API response
            
        Returns:
            List of MatchedProduct
        """
        products = []
        
        items = data.get("items", [])
        
        for item in items:
            product = self._parse_item(item)
            if product:
                products.append(product)

        return products

    def _parse_item(self, item: Dict[str, Any]) -> Optional[MatchedProduct]:
        """
        Parse a single search result item.
        
        Args:
            item: Single result from API
            
        Returns:
            MatchedProduct or None
        """
        title = item.get("title", "")
        url = item.get("link", "")
        
        if not title or not url:
            return None

        # Try to extract price from snippet
        snippet = item.get("snippet", "")
        price = extract_price_from_text(snippet)

        # Also check HTML snippet for price
        if not price:
            html_snippet = item.get("htmlSnippet", "")
            price = extract_price_from_text(html_snippet)

        # Try to get image from pagemap
        image_url = self._extract_image(item)

        # Try to get rating from pagemap
        rating = self._extract_rating(item)

        # Use helper from base class
        return self._create_product(
            title=title,
            url=url,
            price=price,
            image_url=image_url,
            rating=rating,
            raw_data=item,
        )

    def _extract_image(self, item: Dict[str, Any]) -> Optional[str]:
        """Extract image URL from pagemap."""
        pagemap = item.get("pagemap", {})
        
        # Try CSE thumbnail
        cse_thumb = pagemap.get("cse_thumbnail", [])
        if cse_thumb and isinstance(cse_thumb, list):
            return cse_thumb[0].get("src")
        
        # Try CSE image
        cse_image = pagemap.get("cse_image", [])
        if cse_image and isinstance(cse_image, list):
            return cse_image[0].get("src")
        
        # Try metatags og:image
        metatags = pagemap.get("metatags", [])
        if metatags and isinstance(metatags, list):
            og_image = metatags[0].get("og:image")
            if og_image:
                return og_image
        
        return None

    def _extract_rating(self, item: Dict[str, Any]) -> Optional[float]:
        """Extract rating from pagemap."""
        pagemap = item.get("pagemap", {})
        
        # Try aggregaterating
        aggregate = pagemap.get("aggregaterating", [])
        if aggregate and isinstance(aggregate, list):
            try:
                return float(aggregate[0].get("ratingvalue", 0))
            except (ValueError, TypeError):
                pass
        
        # Try product schema
        product = pagemap.get("product", [])
        if product and isinstance(product, list):
            try:
                return float(product[0].get("ratingvalue", 0))
            except (ValueError, TypeError):
                pass
        
        return None

    def _check_daily_reset(self) -> None:
        """Reset daily counter if date has changed."""
        from datetime import date
        
        today = date.today().isoformat()
        
        if self._last_reset_date != today:
            self._daily_requests = 0
            self._last_reset_date = today

    # ─────────────────────────────────────────────────────────────────────────
    # Public Utility Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        self._check_daily_reset()
        
        return {
            "provider": self.provider_name.value,
            "daily_requests": self._daily_requests,
            "daily_limit": self.daily_free_limit,
            "remaining_free": max(0, self.daily_free_limit - self._daily_requests),
        }

    def get_remaining_free_searches(self) -> int:
        """Get remaining free searches for today."""
        self._check_daily_reset()
        return max(0, self.daily_free_limit - self._daily_requests)
    


    