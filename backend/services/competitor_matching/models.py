# backend/services/competitor_matching/models.py

"""
Data models for competitor matching service.

These are pure data classes with no business logic,
making them easy to serialize, test, and reuse.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class SearchProvider(str, Enum):
    """Available search providers."""
    SERPAPI_GOOGLE_SHOPPING = "serpapi_google_shopping"
    GOOGLE_CUSTOM_SEARCH = "google_custom_search"
    DUCKDUCKGO = "duckduckgo"
    KEEPA = "keepa"  # Future
    RAINFOREST = "rainforest"  # Future


class MatchStatus(str, Enum):
    """Status of a match operation."""
    SUCCESS = "success"
    PARTIAL = "partial"  # Some providers failed
    FAILED = "failed"
    CACHED = "cached"


@dataclass
class MatchedProduct:
    """
    A competitor product found via search.
    
    Represents a single product listing from a competitor
    that potentially matches one of our products.
    """
    title: str
    url: str
    price: Optional[Decimal] = None
    currency: str = "USD"
    merchant: str = ""
    merchant_domain: str = ""
    image_url: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    confidence_score: float = 0.0  # 0-1, how well it matches our product
    source: SearchProvider = SearchProvider.SERPAPI_GOOGLE_SHOPPING
    in_stock: bool = True
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def price_display(self) -> str:
        """Format price for display."""
        if self.price is not None:
            return f"${self.price:.2f}"
        return "N/A"

    @property
    def confidence_percent(self) -> int:
        """Confidence as percentage."""
        return int(self.confidence_score * 100)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "title": self.title,
            "url": self.url,
            "price": str(self.price) if self.price else None,
            "currency": self.currency,
            "merchant": self.merchant,
            "merchant_domain": self.merchant_domain,
            "image_url": self.image_url,
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "confidence_score": self.confidence_score,
            "confidence_percent": self.confidence_percent,
            "source": self.source.value,
            "in_stock": self.in_stock,
        }


@dataclass
class ProviderResult:
    """
    Result from a single search provider.
    
    Each provider returns this structure, allowing
    the orchestrator to aggregate results.
    """
    provider: SearchProvider
    success: bool
    products: List[MatchedProduct] = field(default_factory=list)
    error: Optional[str] = None
    response_time_ms: int = 0
    rate_limited: bool = False
    credits_used: int = 0  # For paid APIs

    @property
    def product_count(self) -> int:
        return len(self.products)


@dataclass
class MatchSearchRequest:
    """
    Request parameters for a competitor search.
    
    Encapsulates all search parameters in a single object
    for cleaner function signatures.
    """
    product_name: str
    keywords: List[str] = field(default_factory=list)
    our_price: Optional[Decimal] = None
    our_sku: Optional[str] = None
    max_results: int = 10
    exclude_domains: List[str] = field(default_factory=list)
    preferred_merchants: List[str] = field(default_factory=list)
    providers: Optional[List[SearchProvider]] = None  # None = use all available
    use_cache: bool = True
    min_confidence: float = 0.3  # Filter out low-confidence matches

    def build_query(self) -> str:
        """Build optimized search query."""
        query = self.product_name.strip()
        
        if self.keywords:
            # Only add keywords not already in product name
            name_lower = self.product_name.lower()
            new_keywords = [k for k in self.keywords if k.lower() not in name_lower]
            if new_keywords:
                query = f"{query} {' '.join(new_keywords[:3])}"
        
        return query


@dataclass
class MatchSearchResponse:
    """
    Complete response from competitor matching service.
    
    Aggregates results from all providers with metadata
    about the search operation.
    """
    status: MatchStatus
    products: List[MatchedProduct] = field(default_factory=list)
    query_used: str = ""
    total_found: int = 0
    providers_used: List[SearchProvider] = field(default_factory=list)
    providers_failed: List[str] = field(default_factory=list)
    search_time_ms: int = 0
    cached: bool = False
    error: Optional[str] = None
    searched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def success(self) -> bool:
        return self.status in (MatchStatus.SUCCESS, MatchStatus.CACHED, MatchStatus.PARTIAL)

    @property
    def has_results(self) -> bool:
        return len(self.products) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "status": self.status.value,
            "products": [p.to_dict() for p in self.products],
            "query_used": self.query_used,
            "total_found": self.total_found,
            "providers_used": [p.value for p in self.providers_used],
            "providers_failed": self.providers_failed,
            "search_time_ms": self.search_time_ms,
            "cached": self.cached,
            "error": self.error,
            "searched_at": self.searched_at.isoformat(),
        }


@dataclass
class MerchantInfo:
    """
    Information about a known merchant/retailer.
    
    Used for merchant recognition and reliability scoring.
    """
    domain: str
    name: str
    is_marketplace: bool = False  # Amazon, eBay, etc.
    reliability_score: float = 0.8  # 0-1
    supports_api: bool = False
    logo_url: Optional[str] = None

    def __hash__(self):
        return hash(self.domain)
    


    