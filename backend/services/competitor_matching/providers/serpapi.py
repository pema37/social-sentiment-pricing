# backend/services/competitor_matching/providers/serpapi.py

"""
SerpAPI Provider - Google Shopping Search

SerpAPI provides access to Google Shopping results with:
- Product prices, images, ratings
- Merchant information
- High accuracy and reliability

Pricing: ~$50/month for 5,000 searches
Docs: https://serpapi.com/google-shopping-api
"""

import contextlib
import logging
import os
from typing import Any

import httpx

from ..schemas import (
    MatchedProduct,
    ProviderResult,
    SearchProvider,
)
from .base import BaseSearchProvider

logger = logging.getLogger(__name__)


class SerpAPIProvider(BaseSearchProvider):
    """
    Google Shopping search via SerpAPI.

    This is the highest quality provider, returning structured
    product data including prices, ratings, and images.
    """

    ENDPOINT = "https://serpapi.com/search.json"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
        country: str = "us",
        language: str = "en",
    ):
        """
        Initialize SerpAPI provider.

        Args:
            api_key: SerpAPI key (or set SERPAPI_KEY env var)
            timeout: Request timeout in seconds
            country: Country code for results (us, uk, ca, etc.)
            language: Language code (en, fr, de, etc.)
        """
        self.api_key = api_key or os.getenv("SERPAPI_KEY")
        self.timeout = timeout
        self.country = country
        self.language = language

        # Track usage
        self._requests_made = 0

    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Property Implementations
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def provider_name(self) -> SearchProvider:
        return SearchProvider.SERPAPI_GOOGLE_SHOPPING

    @property
    def requires_api_key(self) -> bool:
        return True

    @property
    def rate_limit_per_minute(self) -> int:
        return 100  # SerpAPI is generous

    @property
    def cost_per_request(self) -> float:
        return 0.01  # ~$50 for 5000 searches

    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Method Implementations
    # ─────────────────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if SerpAPI is configured."""
        return bool(self.api_key)

    async def _search(
        self,
        query: str,
        max_results: int,
        **kwargs,
    ) -> ProviderResult:
        """
        Search Google Shopping via SerpAPI.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            ProviderResult with products
        """
        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.api_key,
            "num": min(max_results * 2, 40),  # Get extra for filtering
            "hl": self.language,
            "gl": self.country,
        }

        # Optional: filter by price range
        if kwargs.get("min_price"):
            params["tbs"] = f"price:1,ppr_min:{kwargs['min_price']}"
        if kwargs.get("max_price"):
            price_filter = params.get("tbs", "")
            params["tbs"] = f"{price_filter},ppr_max:{kwargs['max_price']}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.ENDPOINT, params=params)
                response.raise_for_status()
                data = response.json()

            self._requests_made += 1

            # Check for API errors
            if "error" in data:
                return ProviderResult(
                    provider=self.provider_name,
                    success=False,
                    error=data["error"],
                )

            # Parse shopping results
            products = self._parse_results(data)

            return ProviderResult(
                provider=self.provider_name,
                success=True,
                products=products[:max_results],
                credits_used=1,
            )

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"

            # Check for specific errors
            if e.response.status_code == 401:
                error_msg = "Invalid API key"
            elif e.response.status_code == 429:
                error_msg = "Rate limit exceeded"
                return ProviderResult(
                    provider=self.provider_name,
                    success=False,
                    error=error_msg,
                    rate_limited=True,
                )

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
            logger.exception(f"SerpAPI error: {e}")
            return ProviderResult(
                provider=self.provider_name,
                success=False,
                error=str(e),
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_results(self, data: dict[str, Any]) -> list[MatchedProduct]:
        """
        Parse SerpAPI shopping results into MatchedProduct objects.

        Args:
            data: Raw API response

        Returns:
            List of MatchedProduct
        """
        products = []

        shopping_results = data.get("shopping_results", [])

        for item in shopping_results:
            product = self._parse_item(item)
            if product:
                products.append(product)

        # Also check inline shopping results
        inline_results = data.get("inline_shopping_results", [])
        for item in inline_results:
            product = self._parse_item(item)
            if product:
                products.append(product)

        return products

    def _parse_item(self, item: dict[str, Any]) -> MatchedProduct | None:
        """
        Parse a single shopping result item.

        Args:
            item: Single result from API

        Returns:
            MatchedProduct or None
        """
        title = item.get("title", "")
        url = item.get("link", "")

        if not title or not url:
            return None

        # Extract price - SerpAPI provides multiple formats
        price = None
        if "extracted_price" in item:
            price = item["extracted_price"]
        elif "price" in item:
            # Price string like "$29.99"
            price = item["price"]

        # Extract rating
        rating = None
        if "rating" in item:
            with contextlib.suppress(ValueError, TypeError):
                rating = float(item["rating"])

        # Extract reviews count
        reviews = None
        if "reviews" in item:
            with contextlib.suppress(ValueError, TypeError):
                reviews = int(item["reviews"])

        # Check stock status
        in_stock = True
        if item.get("availability"):
            availability = item["availability"].lower()
            in_stock = "out of stock" not in availability

        # Use helper from base class
        return self._create_product(
            title=title,
            url=url,
            price=price,
            merchant=item.get("source", ""),
            image_url=item.get("thumbnail"),
            rating=rating,
            reviews_count=reviews,
            currency=self._extract_currency(item),
            in_stock=in_stock,
            raw_data=item,
        )

    def _extract_currency(self, item: dict[str, Any]) -> str:
        """Extract currency from item."""
        # SerpAPI usually returns USD for US searches
        price_str = item.get("price", "")

        if "$" in price_str or "USD" in price_str:
            return "USD"
        elif "€" in price_str or "EUR" in price_str:
            return "EUR"
        elif "£" in price_str or "GBP" in price_str:
            return "GBP"
        elif "CA$" in price_str or "CAD" in price_str:
            return "CAD"

        return "USD"  # Default

    # ─────────────────────────────────────────────────────────────────────────
    # Public Utility Methods
    # ─────────────────────────────────────────────────────────────────────────

    def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        return {
            "provider": self.provider_name.value,
            "requests_made": self._requests_made,
            "estimated_cost": self._requests_made * self.cost_per_request,
        }

    async def check_api_status(self) -> dict[str, Any]:
        """
        Check API key status and remaining credits.

        Returns:
            Dict with status info
        """
        if not self.api_key:
            return {"status": "not_configured"}

        try:
            params = {
                "api_key": self.api_key,
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://serpapi.com/account.json",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            return {
                "status": "active",
                "plan": data.get("plan_name"),
                "searches_remaining": data.get("total_searches_left"),
                "this_month": data.get("this_month_usage"),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }
