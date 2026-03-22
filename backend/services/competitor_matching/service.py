# backend/services/competitor_matching/service.py

"""
Competitor Matching Service - Main Orchestrator

This is the main entry point for competitor URL matching.
It coordinates multiple search providers and aggregates results.

Features:
- Multi-provider search with fallback
- Result caching
- Confidence scoring
- Duplicate detection
- Rate limiting awareness

Usage:
    from services.competitor_matching import CompetitorMatchingService

    service = CompetitorMatchingService()

    result = await service.find_competitors(
        product_name="iPhone 15 Pro 256GB",
        keywords=["apple", "smartphone"],
        our_price=Decimal("999.99"),
        max_results=10,
    )

    for product in result.products:
        print(f"{product.merchant}: {product.price_display} ({product.confidence_percent}%)")
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from .providers import (
    BaseSearchProvider,
    provider_registry,
    setup_providers,
)
from .schemas import (
    MatchedProduct,
    MatchSearchRequest,
    MatchSearchResponse,
    MatchStatus,
    ProviderResult,
    SearchProvider,
)
from .scoring import ConfidenceScorer, ScoringWeights

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with timestamp."""

    response: MatchSearchResponse
    created_at: datetime

    def is_expired(self, ttl_hours: int) -> bool:
        """Check if cache entry is expired."""
        age = datetime.now(UTC) - self.created_at
        return age.total_seconds() > (ttl_hours * 3600)


class CompetitorMatchingService:
    """
    Main service for finding competitor product URLs.

    Orchestrates multiple search providers and provides:
    - Unified interface for all providers
    - Automatic fallback when providers fail
    - Result deduplication
    - Confidence scoring
    - Caching
    """

    def __init__(
        self,
        cache_ttl_hours: int = 24,
        max_cache_size: int = 1000,
        scorer_weights: ScoringWeights | None = None,
        min_confidence: float = 0.2,
    ):
        """
        Initialize the matching service.

        Args:
            cache_ttl_hours: How long to cache results
            max_cache_size: Maximum cache entries
            scorer_weights: Custom scoring weights
            min_confidence: Minimum confidence to include in results
        """
        self.cache_ttl_hours = cache_ttl_hours
        self.max_cache_size = max_cache_size
        self.min_confidence = min_confidence

        # Initialize scorer
        self.scorer = ConfidenceScorer(weights=scorer_weights)

        # Per-process result cache (not shared across Uvicorn workers).
        # Use asyncio.Lock to prevent race conditions during concurrent eviction.
        self._cache: dict[str, CacheEntry] = {}
        self._cache_lock = asyncio.Lock()

        # Ensure providers are set up
        if provider_registry.available_count == 0:
            setup_providers()

    # ─────────────────────────────────────────────────────────────────────────
    # Main Public Methods
    # ─────────────────────────────────────────────────────────────────────────

    async def find_competitors(
        self,
        product_name: str,
        keywords: list[str] | None = None,
        our_price: Decimal | None = None,
        our_sku: str | None = None,
        max_results: int = 10,
        exclude_domains: list[str] | None = None,
        preferred_merchants: list[str] | None = None,
        providers: list[SearchProvider] | None = None,
        use_cache: bool = True,
        min_confidence: float | None = None,
    ) -> MatchSearchResponse:
        """
        Find competitor products matching the given product.

        This is the main entry point for competitor matching.

        Args:
            product_name: Product name to search for
            keywords: Additional keywords (brand, model, etc.)
            our_price: Our product's price for relevance scoring
            our_sku: Our SKU (for logging/tracking)
            max_results: Maximum results to return
            exclude_domains: Domains to exclude (e.g., your own store)
            preferred_merchants: Prioritize these merchants in results
            providers: Specific providers to use (None = all available)
            use_cache: Whether to use/update cache
            min_confidence: Override default minimum confidence

        Returns:
            MatchSearchResponse with found products
        """
        import time

        start_time = time.time()

        # Build request
        request = MatchSearchRequest(
            product_name=product_name,
            keywords=keywords or [],
            our_price=our_price,
            our_sku=our_sku,
            max_results=max_results,
            exclude_domains=exclude_domains or [],
            preferred_merchants=preferred_merchants or [],
            providers=providers,
            use_cache=use_cache,
            min_confidence=min_confidence or self.min_confidence,
        )

        # Check cache first
        cache_key = self._build_cache_key(request)
        if use_cache:
            cached = await self._get_from_cache(cache_key)
            if cached:
                logger.info(f"Cache hit for: {product_name}")
                cached.cached = True
                cached.search_time_ms = int((time.time() - start_time) * 1000)
                return cached

        # Get providers to use
        providers_to_use = self._select_providers(providers)

        if not providers_to_use:
            return MatchSearchResponse(
                status=MatchStatus.FAILED,
                error="No search providers available",
                query_used=request.build_query(),
                search_time_ms=int((time.time() - start_time) * 1000),
            )

        logger.info(f"Searching for competitors: '{product_name}' using {len(providers_to_use)} provider(s)")

        # Search with all selected providers
        provider_results = await self._search_all_providers(
            request=request,
            providers=providers_to_use,
        )

        # Aggregate results
        response = self._aggregate_results(
            provider_results=provider_results,
            request=request,
        )

        # Score and sort products
        if response.products:
            response.products = self._score_and_filter(
                products=response.products,
                request=request,
            )

        # Apply merchant preferences
        if request.preferred_merchants and response.products:
            response.products = self._apply_merchant_preferences(
                products=response.products,
                preferred=request.preferred_merchants,
            )

        # Limit results
        response.products = response.products[:max_results]
        response.total_found = len(response.products)

        # Update timing
        response.search_time_ms = int((time.time() - start_time) * 1000)

        # Cache successful results
        if use_cache and response.success:
            await self._add_to_cache(cache_key, response)

        logger.info(f"Found {response.total_found} competitors for '{product_name}' in {response.search_time_ms}ms")

        return response

    async def find_competitors_for_product(
        self,
        product_id: str,
        product_name: str,
        product_keywords: list[str] | None = None,
        product_price: Decimal | None = None,
        **kwargs,
    ) -> MatchSearchResponse:
        """
        Convenience method for finding competitors for a database product.

        Args:
            product_id: Product ID (for logging)
            product_name: Product name
            product_keywords: Product keywords
            product_price: Product's current price
            **kwargs: Additional arguments passed to find_competitors

        Returns:
            MatchSearchResponse
        """
        logger.info(f"Finding competitors for product {product_id}: {product_name}")

        return await self.find_competitors(
            product_name=product_name,
            keywords=product_keywords,
            our_price=product_price,
            **kwargs,
        )

    def get_available_providers(self) -> list[dict[str, Any]]:
        """
        Get information about available providers.

        Returns:
            List of provider info dicts
        """
        providers = []

        for provider in provider_registry.get_all():
            providers.append(
                {
                    "name": provider.provider_name.value,
                    "available": provider.is_available(),
                    "requires_api_key": provider.requires_api_key,
                    "cost_per_request": provider.cost_per_request,
                }
            )

        return providers

    def clear_cache(self) -> int:
        """
        Clear the result cache.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared {count} cache entries")
        return count

    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods - Provider Management
    # ─────────────────────────────────────────────────────────────────────────

    def _select_providers(
        self,
        requested: list[SearchProvider] | None = None,
    ) -> list[BaseSearchProvider]:
        """Select providers to use for search."""
        if requested:
            # Use specific requested providers
            providers = []
            for name in requested:
                provider = provider_registry.get(name)
                if provider and provider.is_available():
                    providers.append(provider)
            return providers
        else:
            # Use all available providers
            return provider_registry.get_available()

    async def _search_all_providers(
        self,
        request: MatchSearchRequest,
        providers: list[BaseSearchProvider],
    ) -> list[ProviderResult]:
        """
        Search with all providers concurrently.

        Args:
            request: Search request
            providers: Providers to use

        Returns:
            List of ProviderResult from each provider
        """
        # Create tasks for concurrent execution
        tasks = [provider.search(request) for provider in providers]

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        provider_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Provider raised an exception
                logger.error(f"Provider {providers[i].provider_name.value} failed: {result}")
                provider_results.append(
                    ProviderResult(
                        provider=providers[i].provider_name,
                        success=False,
                        error=str(result),
                    )
                )
            else:
                provider_results.append(result)

        return provider_results

    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods - Result Processing
    # ─────────────────────────────────────────────────────────────────────────

    def _aggregate_results(
        self,
        provider_results: list[ProviderResult],
        request: MatchSearchRequest,
    ) -> MatchSearchResponse:
        """
        Aggregate results from multiple providers.

        Handles deduplication, status determination, and error collection.
        """
        all_products: list[MatchedProduct] = []
        providers_used: list[SearchProvider] = []
        providers_failed: list[str] = []
        seen_urls: set[str] = set()

        for result in provider_results:
            if result.success:
                providers_used.append(result.provider)

                # Add products, deduplicating by URL
                for product in result.products:
                    url_normalized = self._normalize_url(product.url)
                    if url_normalized not in seen_urls:
                        seen_urls.add(url_normalized)
                        all_products.append(product)
            else:
                providers_failed.append(f"{result.provider.value}: {result.error}")

        # Determine overall status
        if not providers_used:
            status = MatchStatus.FAILED
        elif providers_failed:
            status = MatchStatus.PARTIAL
        else:
            status = MatchStatus.SUCCESS

        # Filter out excluded domains
        if request.exclude_domains:
            all_products = [
                p
                for p in all_products
                if not any(excluded in p.merchant_domain for excluded in request.exclude_domains)
            ]

        return MatchSearchResponse(
            status=status,
            products=all_products,
            query_used=request.build_query(),
            total_found=len(all_products),
            providers_used=providers_used,
            providers_failed=providers_failed,
        )

    def _score_and_filter(
        self,
        products: list[MatchedProduct],
        request: MatchSearchRequest,
    ) -> list[MatchedProduct]:
        """Score products and filter by minimum confidence."""
        # Score all products
        scored = self.scorer.calculate_batch(
            products=products,
            search_name=request.product_name,
            keywords=request.keywords,
            our_price=request.our_price,
        )

        # Filter by minimum confidence
        filtered = [p for p in scored if p.confidence_score >= request.min_confidence]

        # Sort by confidence (highest first)
        return sorted(
            filtered,
            key=lambda p: p.confidence_score,
            reverse=True,
        )

    def _apply_merchant_preferences(
        self,
        products: list[MatchedProduct],
        preferred: list[str],
    ) -> list[MatchedProduct]:
        """
        Sort products to prioritize preferred merchants.

        Preferred merchants appear first, then sorted by confidence.
        """

        def sort_key(product: MatchedProduct) -> tuple:
            # Check if merchant is preferred
            merchant_priority = len(preferred)  # Default: lowest priority
            for i, pref in enumerate(preferred):
                if pref.lower() in product.merchant.lower() or pref.lower() in product.merchant_domain:
                    merchant_priority = i
                    break

            # Sort by: merchant priority (asc), confidence (desc)
            return (merchant_priority, -product.confidence_score)

        return sorted(products, key=sort_key)

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        if not url:
            return ""

        # Lowercase
        normalized = url.lower()

        # Remove trailing slash
        normalized = normalized.rstrip("/")

        # Remove common tracking parameters
        tracking_params = ["utm_", "ref=", "tag=", "source="]
        for param in tracking_params:
            if param in normalized:
                # Simple removal - in production, use proper URL parsing
                idx = normalized.find(param)
                if idx > 0:
                    # Find the & or end
                    end_idx = normalized.find("&", idx)
                    if end_idx > 0:
                        normalized = normalized[:idx] + normalized[end_idx + 1 :]
                    else:
                        # Remove from ? or &
                        sep_idx = max(normalized.rfind("?", 0, idx), normalized.rfind("&", 0, idx))
                        if sep_idx > 0:
                            normalized = normalized[:sep_idx]

        return normalized

    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods - Caching
    # ─────────────────────────────────────────────────────────────────────────

    def _build_cache_key(self, request: MatchSearchRequest) -> str:
        """Build cache key from request."""
        key_parts = [
            request.product_name.lower(),
            ",".join(sorted(request.keywords)),
            str(request.max_results),
        ]
        key_string = "|".join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    async def _get_from_cache(self, key: str) -> MatchSearchResponse | None:
        """Get result from cache if not expired (lock-protected)."""
        async with self._cache_lock:
            entry = self._cache.get(key)

            if entry is None:
                return None

            if entry.is_expired(self.cache_ttl_hours):
                del self._cache[key]
                return None

            return entry.response

    async def _add_to_cache(self, key: str, response: MatchSearchResponse) -> None:
        """Add result to cache, evicting old entries if needed (lock-protected)."""
        async with self._cache_lock:
            # Evict old entries if cache is full
            if len(self._cache) >= self.max_cache_size:
                self._evict_oldest_entries(count=self.max_cache_size // 10)

            self._cache[key] = CacheEntry(
                response=response,
                created_at=datetime.now(UTC),
            )

    def _evict_oldest_entries(self, count: int) -> None:
        """Evict oldest cache entries. Must be called under _cache_lock."""
        if not self._cache:
            return

        # Sort by creation time
        sorted_keys = sorted(
            self._cache.keys(),
            key=lambda k: self._cache[k].created_at,
        )

        # Remove oldest
        for key in sorted_keys[:count]:
            del self._cache[key]


# ─────────────────────────────────────────────────────────────────────────────
# Module-level Instance
# ─────────────────────────────────────────────────────────────────────────────

# Singleton instance with default configuration
competitor_matching_service = CompetitorMatchingService()
