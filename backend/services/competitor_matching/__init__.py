"""Import directly from submodules where needed."""
from services.competitor_matching.service import competitor_matching_service
from services.competitor_matching.schemas import (
    MatchSearchResponse,
    MatchedProduct,
    SearchProvider,
)

# Convenience aliases matching the route import pattern
find_competitors = competitor_matching_service.find_competitors
get_available_providers = competitor_matching_service.get_available_providers

__all__ = [
    "competitor_matching_service",
    "find_competitors",
    "get_available_providers",
    "MatchSearchResponse",
    "MatchedProduct",
    "SearchProvider",
]
