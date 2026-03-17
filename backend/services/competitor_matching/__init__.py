"""Import directly from submodules where needed."""

from services.competitor_matching.schemas import (
    MatchedProduct,
    MatchSearchResponse,
    SearchProvider,
)
from services.competitor_matching.service import competitor_matching_service

# Convenience aliases matching the route import pattern
find_competitors = competitor_matching_service.find_competitors
get_available_providers = competitor_matching_service.get_available_providers

__all__ = [
    "MatchSearchResponse",
    "MatchedProduct",
    "SearchProvider",
    "competitor_matching_service",
    "find_competitors",
    "get_available_providers",
]
