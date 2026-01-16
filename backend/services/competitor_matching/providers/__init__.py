# backend/services/competitor_matching/providers/__init__.py

"""
Search Providers Package

This package contains all competitor search providers.
Each provider implements the BaseSearchProvider interface.

Available Providers:
- SerpAPIProvider: Google Shopping via SerpAPI (paid, best quality)
- GoogleCustomSearchProvider: Google Custom Search (100 free/day)
- DuckDuckGoProvider: Free fallback (no API key needed)

Usage:
    from services.competitor_matching.providers import (
        SerpAPIProvider,
        GoogleCustomSearchProvider,
        DuckDuckGoProvider,
        provider_registry,
    )
    
    # Register providers
    provider_registry.register(SerpAPIProvider(api_key="xxx"))
    provider_registry.register(GoogleCustomSearchProvider(api_key="xxx", search_engine_id="xxx"))
    provider_registry.register(DuckDuckGoProvider())
    
    # Get available providers
    available = provider_registry.get_available()
"""

from .base import (
    BaseSearchProvider,
    ProviderRegistry,
    provider_registry,
)
from .serpapi import SerpAPIProvider
from .google_custom import GoogleCustomSearchProvider
from .duckduckgo import DuckDuckGoProvider


__all__ = [
    # Base
    "BaseSearchProvider",
    "ProviderRegistry",
    "provider_registry",
    # Providers
    "SerpAPIProvider",
    "GoogleCustomSearchProvider",
    "DuckDuckGoProvider",
]


def setup_providers(
    serpapi_key: str = None,
    google_api_key: str = None,
    google_cx: str = None,
) -> ProviderRegistry:
    """
    Convenience function to setup all providers.
    
    Automatically registers providers based on available credentials.
    
    Args:
        serpapi_key: SerpAPI key (or uses SERPAPI_KEY env var)
        google_api_key: Google API key (or uses GOOGLE_API_KEY env var)
        google_cx: Google Custom Search Engine ID (or uses GOOGLE_SEARCH_CX env var)
        
    Returns:
        Configured ProviderRegistry
    """
    import os
    
    # Clear existing registrations
    global provider_registry
    provider_registry = ProviderRegistry()
    
    # SerpAPI (best quality)
    serpapi_key = serpapi_key or os.getenv("SERPAPI_KEY")
    if serpapi_key:
        provider_registry.register(SerpAPIProvider(api_key=serpapi_key))
    
    # Google Custom Search (free tier)
    google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
    google_cx = google_cx or os.getenv("GOOGLE_SEARCH_CX")
    if google_api_key and google_cx:
        provider_registry.register(
            GoogleCustomSearchProvider(
                api_key=google_api_key,
                search_engine_id=google_cx,
            )
        )
    
    # DuckDuckGo (always available, free fallback)
    provider_registry.register(DuckDuckGoProvider())
    
    return provider_registry



