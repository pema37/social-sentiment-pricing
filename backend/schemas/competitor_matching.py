# backend/schemas/competitor_matching.py

"""
Pydantic Schemas for Competitor Matching API

These schemas are used for:
- Request/response validation
- OpenAPI documentation generation
- Type hints throughout the codebase
"""

from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


# ─────────────────────────────────────────────────────────────────────────────
# Enums as string literals for API
# ─────────────────────────────────────────────────────────────────────────────

SEARCH_PROVIDERS = [
    "serpapi_google_shopping",
    "google_custom_search", 
    "duckduckgo",
    "keepa",
    "rainforest",
]

MATCH_STATUSES = [
    "success",
    "partial",
    "failed",
    "cached",
]


# ─────────────────────────────────────────────────────────────────────────────
# Request Schemas
# ─────────────────────────────────────────────────────────────────────────────

class CompetitorSearchRequest(BaseModel):
    """Request to search for competitor products."""
    
    product_name: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Product name to search for",
        json_schema_extra={"example": "iPhone 15 Pro 256GB"},
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Additional keywords to improve search accuracy",
        json_schema_extra={"example": ["apple", "smartphone", "unlocked"]},
    )
    our_price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Your product's price for relevance scoring",
        json_schema_extra={"example": "999.99"},
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return",
    )
    exclude_domains: Optional[List[str]] = Field(
        default=None,
        description="Domains to exclude from results (e.g., your own store)",
        json_schema_extra={"example": ["mystore.com"]},
    )
    preferred_merchants: Optional[List[str]] = Field(
        default=None,
        description="Preferred merchants to prioritize in results",
        json_schema_extra={"example": ["Amazon", "Best Buy", "Walmart"]},
    )
    min_confidence: float = Field(
        default=0.3,
        ge=0,
        le=1,
        description="Minimum confidence score (0-1) to include in results",
    )
    use_cache: bool = Field(
        default=True,
        description="Use cached results if available (faster)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_name": "iPhone 15 Pro 256GB",
                "keywords": ["apple", "smartphone", "unlocked"],
                "our_price": "999.99",
                "max_results": 10,
                "preferred_merchants": ["Amazon", "Best Buy"],
                "min_confidence": 0.3,
                "use_cache": True,
            }
        }
    )


class ProductMatchRequest(BaseModel):
    """Request to find competitors for a specific product."""
    
    product_id: UUID = Field(
        ...,
        description="ID of your product to find competitors for",
    )
    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum results per product",
    )
    exclude_domains: Optional[List[str]] = Field(
        default=None,
        description="Domains to exclude",
    )
    preferred_merchants: Optional[List[str]] = Field(
        default=None,
        description="Preferred merchants",
    )
    auto_link: bool = Field(
        default=False,
        description="Automatically create competitor links for high-confidence matches",
    )
    auto_link_threshold: float = Field(
        default=0.8,
        ge=0.5,
        le=1,
        description="Minimum confidence score for auto-linking",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "product_id": "123e4567-e89b-12d3-a456-426614174000",
                "max_results": 10,
                "auto_link": True,
                "auto_link_threshold": 0.8,
            }
        }
    )


class BulkMatchRequest(BaseModel):
    """Request to match multiple products at once."""
    
    product_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of product IDs to find competitors for",
    )
    max_results_per_product: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum results per product",
    )
    auto_link: bool = Field(
        default=False,
        description="Auto-link high-confidence matches",
    )
    auto_link_threshold: float = Field(
        default=0.8,
        ge=0.5,
        le=1,
        description="Confidence threshold for auto-linking",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Response Schemas
# ─────────────────────────────────────────────────────────────────────────────

class MatchedProductSchema(BaseModel):
    """A competitor product found via search."""
    
    title: str = Field(description="Product title")
    url: str = Field(description="Product URL")
    price: Optional[str] = Field(description="Product price")
    currency: str = Field(default="USD", description="Price currency")
    merchant: str = Field(description="Merchant/retailer name")
    merchant_domain: str = Field(description="Merchant domain")
    image_url: Optional[str] = Field(description="Product image URL")
    rating: Optional[float] = Field(description="Product rating (0-5)")
    reviews_count: Optional[int] = Field(description="Number of reviews")
    confidence_score: float = Field(description="Match confidence (0-1)")
    confidence_percent: int = Field(description="Match confidence as percentage")
    source: str = Field(description="Search provider that found this result")
    in_stock: bool = Field(default=True, description="Whether product is in stock")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Apple iPhone 15 Pro 256GB - Natural Titanium",
                "url": "https://www.amazon.com/dp/B0CMZJ2KQY",
                "price": "999.00",
                "currency": "USD",
                "merchant": "Amazon",
                "merchant_domain": "amazon.com",
                "image_url": "https://images.amazon.com/...",
                "rating": 4.5,
                "reviews_count": 1234,
                "confidence_score": 0.92,
                "confidence_percent": 92,
                "source": "serpapi_google_shopping",
                "in_stock": True,
            }
        }
    )


class CompetitorSearchResponse(BaseModel):
    """Response from competitor search."""
    
    success: bool = Field(description="Whether search was successful")
    status: str = Field(description="Search status (success, partial, failed, cached)")
    query_used: str = Field(description="The search query that was used")
    total_found: int = Field(description="Total number of matches found")
    products: List[MatchedProductSchema] = Field(description="Matched products")
    providers_used: List[str] = Field(description="Search providers that returned results")
    providers_failed: List[str] = Field(description="Providers that failed (with error messages)")
    search_time_ms: int = Field(description="Search time in milliseconds")
    cached: bool = Field(description="Whether results came from cache")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "status": "success",
                "query_used": "iPhone 15 Pro 256GB apple smartphone",
                "total_found": 10,
                "products": [],  # See MatchedProductSchema for example
                "providers_used": ["serpapi_google_shopping"],
                "providers_failed": [],
                "search_time_ms": 1234,
                "cached": False,
            }
        }
    )


class ProviderInfoSchema(BaseModel):
    """Information about a search provider."""
    
    name: str = Field(description="Provider name")
    available: bool = Field(description="Whether provider is configured and available")
    requires_api_key: bool = Field(description="Whether provider requires an API key")
    cost_per_request: float = Field(description="Cost per request in USD")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "serpapi_google_shopping",
                "available": True,
                "requires_api_key": True,
                "cost_per_request": 0.01,
            }
        }
    )


class ProvidersListResponse(BaseModel):
    """Response listing available providers."""
    
    providers: List[ProviderInfoSchema] = Field(description="List of all providers")
    available_count: int = Field(description="Number of available providers")
    total_count: int = Field(description="Total number of providers")


class BulkMatchResultSchema(BaseModel):
    """Result for a single product in bulk match."""
    
    product_name: str = Field(description="Product name")
    success: bool = Field(description="Whether match was successful")
    total_found: Optional[int] = Field(default=None, description="Number of matches found")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    top_matches: Optional[List[dict]] = Field(default=None, description="Top 3 matches summary")


class BulkMatchResponse(BaseModel):
    """Response from bulk match operation."""
    
    total_products: int = Field(description="Total products processed")
    results: dict = Field(description="Results keyed by product ID")


class AutoLinkResultSchema(BaseModel):
    """Result of auto-linking operation."""
    
    product_id: str = Field(description="Product ID")
    linked_count: int = Field(description="Number of competitors linked")
    links_created: List[dict] = Field(description="Details of created links")


class CacheClearResponse(BaseModel):
    """Response from cache clear operation."""
    
    success: bool = Field(description="Whether operation succeeded")
    entries_cleared: int = Field(description="Number of cache entries cleared")


# ─────────────────────────────────────────────────────────────────────────────
# Error Schemas
# ─────────────────────────────────────────────────────────────────────────────

class MatchingErrorResponse(BaseModel):
    """Error response for matching operations."""
    
    detail: str = Field(description="Error message")
    error_code: Optional[str] = Field(default=None, description="Error code")
    provider_errors: Optional[List[str]] = Field(default=None, description="Provider-specific errors")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detail": "Search failed: All providers unavailable",
                "error_code": "NO_PROVIDERS",
                "provider_errors": [
                    "serpapi: Invalid API key",
                    "google_custom: Rate limit exceeded",
                ],
            }
        }
    )



