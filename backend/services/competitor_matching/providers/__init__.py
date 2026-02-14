"""Import directly from submodules where needed."""
from .base import provider_registry, BaseSearchProvider, ProviderRegistry
from .duckduckgo import DuckDuckGoProvider
from .google_custom import GoogleCustomSearchProvider
from .serpapi import SerpAPIProvider


def setup_providers():
    """Register all available providers with the registry."""
    providers = [
        DuckDuckGoProvider(),
        GoogleCustomSearchProvider(),
        SerpAPIProvider(),
    ]
    for provider in providers:
        try:
            if provider not in provider_registry.get_all():
                provider_registry.register(provider)
        except Exception:
            pass
