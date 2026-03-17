# backend/services/competitor_matching/providers/base.py

"""
Abstract base class for search providers.

All providers must implement this interface, ensuring
consistent behavior and easy swapping/testing.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

from ..schemas import (
    MatchedProduct,
    MatchSearchRequest,
    ProviderResult,
    SearchProvider,
)

logger = logging.getLogger(__name__)


class BaseSearchProvider(ABC):
    """
    Abstract base class for competitor search providers.

    Each provider (SerpAPI, Google, DuckDuckGo, etc.) implements
    this interface to provide a consistent API for the orchestrator.

    Subclasses must implement:
        - provider_name: The SearchProvider enum value
        - is_available: Check if provider can be used
        - _search: Perform the actual search
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Properties
    # ─────────────────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def provider_name(self) -> SearchProvider:
        """Return the provider enum value."""
        pass

    @property
    @abstractmethod
    def requires_api_key(self) -> bool:
        """Whether this provider requires an API key."""
        pass

    @property
    def rate_limit_per_minute(self) -> int:
        """Rate limit (requests per minute). Override in subclass."""
        return 60

    @property
    def cost_per_request(self) -> float:
        """Cost per request in USD. Override in subclass."""
        return 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # Abstract Methods
    # ─────────────────────────────────────────────────────────────────────────

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this provider is available for use.

        Should verify:
        - API keys are configured (if required)
        - Service is not rate limited
        - Any other prerequisites

        Returns:
            True if provider can accept requests
        """
        pass

    @abstractmethod
    async def _search(
        self,
        query: str,
        max_results: int,
        **kwargs,
    ) -> ProviderResult:
        """
        Perform the actual search.

        This is the core method that subclasses implement.
        It should:
        1. Make the API request
        2. Parse the response
        3. Convert to MatchedProduct objects
        4. Return ProviderResult

        Args:
            query: Search query string
            max_results: Maximum results to return
            **kwargs: Additional provider-specific options

        Returns:
            ProviderResult with products or error
        """
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # Public Methods (Template Method Pattern)
    # ─────────────────────────────────────────────────────────────────────────

    async def search(
        self,
        request: MatchSearchRequest,
        **kwargs,
    ) -> ProviderResult:
        """
        Execute a search with standard pre/post processing.

        This is the public method called by the orchestrator.
        It wraps _search() with:
        - Availability check
        - Error handling
        - Logging
        - Timing

        Args:
            request: Search request parameters
            **kwargs: Additional options

        Returns:
            ProviderResult
        """
        import time

        start_time = time.time()

        # Check availability
        if not self.is_available():
            return ProviderResult(
                provider=self.provider_name,
                success=False,
                error=f"{self.provider_name.value} is not available (missing API key or rate limited)",
            )

        try:
            # Build query from request
            query = request.build_query()

            logger.info(f"[{self.provider_name.value}] Searching for: {query} (max_results={request.max_results})")

            # Execute search
            result = await self._search(
                query=query,
                max_results=request.max_results,
                **kwargs,
            )

            # Calculate response time
            result.response_time_ms = int((time.time() - start_time) * 1000)

            # Log result
            if result.success:
                logger.info(
                    f"[{self.provider_name.value}] Found {result.product_count} products in {result.response_time_ms}ms"
                )
            else:
                logger.warning(f"[{self.provider_name.value}] Search failed: {result.error}")

            return result

        except Exception as e:
            logger.exception(f"[{self.provider_name.value}] Unexpected error: {e}")
            return ProviderResult(
                provider=self.provider_name,
                success=False,
                error=str(e),
                response_time_ms=int((time.time() - start_time) * 1000),
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Helper Methods (Available to subclasses)
    # ─────────────────────────────────────────────────────────────────────────

    def _create_product(
        self,
        title: str,
        url: str,
        price: Any | None = None,
        merchant: str = "",
        **kwargs,
    ) -> MatchedProduct | None:
        """
        Helper to create a MatchedProduct with validation.

        Args:
            title: Product title
            url: Product URL
            price: Price (will be parsed)
            merchant: Merchant name
            **kwargs: Additional fields

        Returns:
            MatchedProduct or None if validation fails
        """
        from ..utils import (
            clean_product_title,
            extract_domain,
            get_merchant_name,
            is_skip_domain,
            parse_price,
        )

        # Validate required fields
        if not title or not url:
            return None

        # Extract and validate domain
        domain = extract_domain(url)
        if is_skip_domain(domain):
            return None

        # Parse price
        parsed_price = parse_price(price)

        # Get merchant name
        if not merchant:
            merchant = get_merchant_name(domain)

        # Clean title
        clean_title = clean_product_title(title)

        return MatchedProduct(
            title=clean_title or title,
            url=url,
            price=parsed_price,
            merchant=merchant,
            merchant_domain=domain,
            source=self.provider_name,
            **kwargs,
        )

    def _log_debug(self, message: str) -> None:
        """Log debug message with provider prefix."""
        logger.debug(f"[{self.provider_name.value}] {message}")

    def _log_warning(self, message: str) -> None:
        """Log warning message with provider prefix."""
        logger.warning(f"[{self.provider_name.value}] {message}")


class ProviderRegistry:
    """
    Registry of available search providers.

    Allows dynamic registration and lookup of providers.
    """

    def __init__(self):
        self._providers: dict[SearchProvider, BaseSearchProvider] = {}

    def register(self, provider: BaseSearchProvider) -> None:
        """Register a provider instance."""
        self._providers[provider.provider_name] = provider
        logger.info(f"Registered provider: {provider.provider_name.value}")

    def get(self, name: SearchProvider) -> BaseSearchProvider | None:
        """Get a provider by name."""
        return self._providers.get(name)

    def get_available(self) -> list[BaseSearchProvider]:
        """Get all available (configured) providers."""
        return [p for p in self._providers.values() if p.is_available()]

    def get_all(self) -> list[BaseSearchProvider]:
        """Get all registered providers."""
        return list(self._providers.values())

    @property
    def available_count(self) -> int:
        """Count of available providers."""
        return len(self.get_available())


# Global registry instance
provider_registry = ProviderRegistry()
