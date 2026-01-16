# backend/services/competitor_matching/__init__.py

"""
Competitor Matching Service Package

Automatically finds competitor product URLs by searching:
- Google Shopping (via SerpAPI) - Best quality, paid
- Google Custom Search - 100 free searches/day
- DuckDuckGo - Free fallback, no API key needed

Usage:
    from services.competitor_matching import competitor_matching_service
    
    # Simple search
    result = await competitor_matching_service.find_competitors(
        product_name="iPhone 15 Pro 256GB",
        keywords=["apple", "smartphone"],
        our_price=Decimal("999.99"),
        max_results=10,
    )
    
    # Check results
    if result.success:
        for product in result.products:
            print(f"{product.merchant}: {product.price_display}")
            print(f"  URL: {product.url}")
            print(f"  Confidence: {product.confidence_percent}%")

Configuration:
    Set these environment variables:
    - SERPAPI_KEY: SerpAPI key for Google Shopping (recommended)
    - GOOGLE_API_KEY: Google API key for Custom Search
    - GOOGLE_SEARCH_CX: Google Custom Search Engine ID
    
    If no API keys are set, DuckDuckGo will be used as fallback.

Architecture:
    competitor_matching/
    ├── __init__.py          # This file - public exports
    ├── models.py            # Data classes
    ├── utils.py             # Helper functions
    ├── scoring.py           # Confidence scoring
    ├── service.py           # Main orchestrator
    └── providers/
        ├── base.py          # Abstract provider
        ├── serpapi.py       # Google Shopping
        ├── google_custom.py # Google Custom Search
        └── duckduckgo.py    # Free fallback
"""

# Models
from .models import (
    SearchProvider,
    MatchStatus,
    MatchedProduct,
    ProviderResult,
    MatchSearchRequest,
    MatchSearchResponse,
    MerchantInfo,
)

# Scoring
from .scoring import (
    ConfidenceScorer,
    ScoringWeights,
    ScoreBreakdown,
    score_products,
)

# Providers
from .providers import (
    BaseSearchProvider,
    ProviderRegistry,
    provider_registry,
    setup_providers,
    SerpAPIProvider,
    GoogleCustomSearchProvider,
    DuckDuckGoProvider,
)

# Main Service
from .service import (
    CompetitorMatchingService,
    competitor_matching_service,
)

# Utils (selective export)
from .utils import (
    extract_domain,
    get_merchant_name,
    parse_price,
    KNOWN_MERCHANTS,
)


__all__ = [
    # Models
    "SearchProvider",
    "MatchStatus",
    "MatchedProduct",
    "ProviderResult",
    "MatchSearchRequest",
    "MatchSearchResponse",
    "MerchantInfo",
    # Scoring
    "ConfidenceScorer",
    "ScoringWeights",
    "ScoreBreakdown",
    "score_products",
    # Providers
    "BaseSearchProvider",
    "ProviderRegistry",
    "provider_registry",
    "setup_providers",
    "SerpAPIProvider",
    "GoogleCustomSearchProvider",
    "DuckDuckGoProvider",
    # Service
    "CompetitorMatchingService",
    "competitor_matching_service",
    # Utils
    "extract_domain",
    "get_merchant_name",
    "parse_price",
    "KNOWN_MERCHANTS",
]


# ─────────────────────────────────────────────────────────────────────────────
# Convenience Functions
# ─────────────────────────────────────────────────────────────────────────────

async def find_competitors(
    product_name: str,
    **kwargs,
) -> MatchSearchResponse:
    """
    Convenience function to find competitors.
    
    Shortcut for competitor_matching_service.find_competitors()
    
    Args:
        product_name: Product name to search
        **kwargs: Additional arguments
        
    Returns:
        MatchSearchResponse
    """
    return await competitor_matching_service.find_competitors(
        product_name=product_name,
        **kwargs,
    )


def get_available_providers() -> list:
    """
    Get list of available search providers.
    
    Returns:
        List of provider info dicts
    """
    return competitor_matching_service.get_available_providers()




