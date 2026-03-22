# backend/api/v1/routes/competitors/matching.py

"""
Competitor Matching API Routes

Endpoints for automatically finding competitor product URLs.
Uses the competitor_matching service to search multiple providers.

Endpoints:
    POST /api/v1/competitors/match/search     - Search for competitor products
    POST /api/v1/competitors/match/product    - Find competitors for a specific product
    POST /api/v1/competitors/match/bulk       - Bulk search for multiple products
    GET  /api/v1/competitors/match/providers  - List available search providers
"""

import logging
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from db.session import get_session as get_db  # Fixed: use get_session from db.session
from models.competitor import Competitor
from models.competitor_product import CompetitorProduct
from models.product import Product
from models.user import User
from services.competitor_matching import (
    MatchedProduct,
    MatchSearchResponse,
    competitor_matching_service,
    get_available_providers,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/match", tags=["competitor-matching"])


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response Schemas
# ─────────────────────────────────────────────────────────────────────────────


class CompetitorSearchRequest(BaseModel):
    """Request schema for competitor search."""

    product_name: str = Field(..., min_length=2, max_length=500, description="Product name to search")
    keywords: list[str] | None = Field(default=None, description="Additional keywords")
    our_price: Decimal | None = Field(default=None, ge=0, description="Our product price for comparison")
    max_results: int = Field(default=10, ge=1, le=50, description="Maximum results to return")
    exclude_domains: list[str] | None = Field(default=None, description="Domains to exclude")
    preferred_merchants: list[str] | None = Field(default=None, description="Preferred merchants")
    min_confidence: float | None = Field(default=0.3, ge=0, le=1, description="Minimum confidence score")
    use_cache: bool = Field(default=True, description="Use cached results if available")

    class Config:
        json_schema_extra = {
            "example": {
                "product_name": "iPhone 15 Pro 256GB",
                "keywords": ["apple", "smartphone", "unlocked"],
                "our_price": "999.99",
                "max_results": 10,
                "preferred_merchants": ["Amazon", "Best Buy"],
                "min_confidence": 0.3,
            }
        }


class ProductMatchRequest(BaseModel):
    """Request schema for matching a specific product."""

    product_id: UUID = Field(..., description="Product ID to find competitors for")
    max_results: int = Field(default=10, ge=1, le=50)
    exclude_domains: list[str] | None = Field(default=None)
    preferred_merchants: list[str] | None = Field(default=None)
    auto_link: bool = Field(default=False, description="Automatically link high-confidence matches")
    auto_link_threshold: float = Field(default=0.8, ge=0.5, le=1, description="Confidence threshold for auto-linking")

    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "123e4567-e89b-12d3-a456-426614174000",
                "max_results": 10,
                "auto_link": True,
                "auto_link_threshold": 0.8,
            }
        }


class BulkMatchRequest(BaseModel):
    """Request schema for bulk matching."""

    product_ids: list[UUID] = Field(..., min_length=1, max_length=20, description="Product IDs to match")
    max_results_per_product: int = Field(default=5, ge=1, le=20)
    auto_link: bool = Field(default=False)
    auto_link_threshold: float = Field(default=0.8, ge=0.5, le=1)


class MatchedProductResponse(BaseModel):
    """Response schema for a matched product."""

    title: str
    url: str
    price: str | None
    currency: str
    merchant: str
    merchant_domain: str
    image_url: str | None
    rating: float | None
    reviews_count: int | None
    confidence_score: float
    confidence_percent: int
    source: str
    in_stock: bool

    @classmethod
    def from_model(cls, product: MatchedProduct) -> "MatchedProductResponse":
        return cls(
            title=product.title,
            url=product.url,
            price=str(product.price) if product.price else None,
            currency=product.currency,
            merchant=product.merchant,
            merchant_domain=product.merchant_domain,
            image_url=product.image_url,
            rating=product.rating,
            reviews_count=product.reviews_count,
            confidence_score=product.confidence_score,
            confidence_percent=product.confidence_percent,
            source=product.source.value,
            in_stock=product.in_stock,
        )


class CompetitorSearchResponse(BaseModel):
    """Response schema for competitor search."""

    success: bool
    status: str
    query_used: str
    total_found: int
    products: list[MatchedProductResponse]
    providers_used: list[str]
    providers_failed: list[str]
    search_time_ms: int
    cached: bool

    @classmethod
    def from_service_response(cls, response: MatchSearchResponse) -> "CompetitorSearchResponse":
        return cls(
            success=response.success,
            status=response.status.value,
            query_used=response.query_used,
            total_found=response.total_found,
            products=[MatchedProductResponse.from_model(p) for p in response.products],
            providers_used=[p.value for p in response.providers_used],
            providers_failed=response.providers_failed,
            search_time_ms=response.search_time_ms,
            cached=response.cached,
        )


class ProviderInfo(BaseModel):
    """Information about a search provider."""

    name: str
    available: bool
    requires_api_key: bool
    cost_per_request: float


class ProvidersResponse(BaseModel):
    """Response schema for providers list."""

    providers: list[ProviderInfo]
    available_count: int
    total_count: int


class LinkResultResponse(BaseModel):
    """Response for auto-link operations."""

    product_id: str
    linked_count: int
    links_created: list[dict]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/search",
    response_model=CompetitorSearchResponse,
    summary="Search for competitor products",
    description="Search multiple providers for competitor products matching the given product name.",
)
async def search_competitors(
    request: CompetitorSearchRequest,
    current_user: User = Depends(get_current_user),
) -> CompetitorSearchResponse:
    """
    Search for competitor products by name.

    This endpoint searches Google Shopping, Google Custom Search, and DuckDuckGo
    to find competitor listings for the given product.

    Results are scored by confidence (how well they match your product)
    and sorted with best matches first.
    """
    logger.info(f"User {current_user.id} searching for: {request.product_name}")

    try:
        response = await competitor_matching_service.find_competitors(
            product_name=request.product_name,
            keywords=request.keywords,
            our_price=request.our_price,
            max_results=request.max_results,
            exclude_domains=request.exclude_domains,
            preferred_merchants=request.preferred_merchants,
            min_confidence=request.min_confidence,
            use_cache=request.use_cache,
        )

        return CompetitorSearchResponse.from_service_response(response)

    except Exception as e:
        logger.exception(f"Competitor search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {e!s}",
        )


@router.post(
    "/product",
    response_model=CompetitorSearchResponse,
    summary="Find competitors for a product",
    description="Find competitor products for a specific product in your catalog.",
)
async def match_product(
    request: ProductMatchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompetitorSearchResponse:
    """
    Find competitors for a specific product in your catalog.

    Uses the product's name, keywords, and price to find matching
    competitor listings. Optionally auto-links high-confidence matches.
    """
    # Fetch the product
    product = await db.get(Product, request.product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if product.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your product")

    logger.info(f"Finding competitors for product {product.id}: {product.name}")

    # Build keywords from product data
    keywords = []
    if product.keywords:
        if isinstance(product.keywords, list):
            keywords = product.keywords
        elif isinstance(product.keywords, str):
            keywords = [k.strip() for k in product.keywords.split(",")]

    if product.category:
        keywords.append(product.category)

    try:
        response = await competitor_matching_service.find_competitors(
            product_name=product.name,
            keywords=keywords,
            our_price=product.current_price or product.base_price,
            max_results=request.max_results,
            exclude_domains=request.exclude_domains,
            preferred_merchants=request.preferred_merchants,
        )

        # Auto-link if requested
        if request.auto_link and response.success:
            background_tasks.add_task(
                _auto_link_competitors,
                db=db,
                user_id=current_user.id,
                product=product,
                matches=response.products,
                threshold=request.auto_link_threshold,
            )

        return CompetitorSearchResponse.from_service_response(response)

    except Exception as e:
        logger.exception(f"Product match failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Match failed: {e!s}",
        )


@router.post(
    "/bulk",
    summary="Bulk match multiple products",
    description="Find competitors for multiple products at once.",
)
async def bulk_match_products(
    request: BulkMatchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Bulk match multiple products.

    Searches are performed concurrently for efficiency.
    Results are returned as a dictionary keyed by product ID.
    """
    from sqlalchemy import select

    # Fetch all products
    stmt = select(Product).where(
        Product.id.in_(request.product_ids),
        Product.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    products = result.scalars().all()

    if not products:
        raise HTTPException(status_code=404, detail="No products found")

    logger.info(f"Bulk matching {len(products)} products for user {current_user.id}")

    # Match each product
    results = {}
    for product in products:
        keywords = []
        if product.keywords and isinstance(product.keywords, list):
            keywords = product.keywords

        try:
            response = await competitor_matching_service.find_competitors(
                product_name=product.name,
                keywords=keywords,
                our_price=product.current_price or product.base_price,
                max_results=request.max_results_per_product,
            )

            results[str(product.id)] = {
                "product_name": product.name,
                "success": response.success,
                "total_found": response.total_found,
                "top_matches": [
                    {
                        "title": p.title,
                        "merchant": p.merchant,
                        "price": str(p.price) if p.price else None,
                        "url": p.url,
                        "confidence": p.confidence_percent,
                    }
                    for p in response.products[:3]  # Top 3 for summary
                ],
            }

            # Auto-link if requested
            if request.auto_link and response.success:
                background_tasks.add_task(
                    _auto_link_competitors,
                    db=db,
                    user_id=current_user.id,
                    product=product,
                    matches=response.products,
                    threshold=request.auto_link_threshold,
                )

        except Exception as e:
            logger.error(f"Failed to match product {product.id}: {e}")
            results[str(product.id)] = {
                "product_name": product.name,
                "success": False,
                "error": str(e),
            }

    return {
        "total_products": len(products),
        "results": results,
    }


@router.get(
    "/providers",
    response_model=ProvidersResponse,
    summary="List search providers",
    description="Get information about available search providers.",
)
async def list_providers(
    current_user: User = Depends(get_current_user),
) -> ProvidersResponse:
    """
    List available search providers.

    Shows which providers are configured and available for use.
    """
    providers = get_available_providers()

    return ProvidersResponse(
        providers=[ProviderInfo(**p) for p in providers],
        available_count=sum(1 for p in providers if p["available"]),
        total_count=len(providers),
    )


@router.post(
    "/clear-cache",
    summary="Clear search cache",
    description="Clear the competitor search cache.",
)
async def clear_cache(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Clear the search cache.

    Use this if you want fresh results instead of cached ones.
    """
    count = competitor_matching_service.clear_cache()

    return {
        "success": True,
        "entries_cleared": count,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


async def _auto_link_competitors(
    db: AsyncSession,
    user_id: UUID,
    product: Product,
    matches: list[MatchedProduct],
    threshold: float,
) -> list[dict]:
    """
    Background task to auto-link high-confidence competitor matches.

    Creates CompetitorProduct entries for matches above the threshold.
    """
    from sqlalchemy import select

    links_created = []
    domain_cache: dict[str, "Competitor"] = {}
    seen_urls: set[str] = set()

    for match in matches:
        # Skip low confidence
        if match.confidence_score < threshold:
            continue

        # Skip if no price
        if match.price is None:
            continue

        # Deduplicate URLs within same batch to prevent duplicate rows
        if match.url in seen_urls:
            continue
        seen_urls.add(match.url)

        try:
            domain = match.merchant_domain

            # Use cached competitor to prevent duplicate creation for same domain
            if domain in domain_cache:
                competitor = domain_cache[domain]
            else:
                # Find or create competitor
                stmt = select(Competitor).where(
                    Competitor.user_id == user_id,
                    Competitor.website.ilike(f"%{domain}%"),
                )
                result = await db.execute(stmt)
                competitor = result.scalar_one_or_none()

                if not competitor:
                    # Create new competitor
                    competitor = Competitor(
                        user_id=user_id,
                        name=match.merchant,
                        website=f"https://{domain}",
                        is_active=True,
                    )
                    db.add(competitor)
                    await db.flush()

                domain_cache[domain] = competitor

            # Check if link already exists
            stmt = select(CompetitorProduct).where(
                CompetitorProduct.product_id == product.id,
                CompetitorProduct.competitor_id == competitor.id,
                CompetitorProduct.competitor_product_url == match.url,
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.current_price = match.price
                existing.match_confidence = Decimal(str(match.confidence_score))
            else:
                # Create new link
                link = CompetitorProduct(
                    product_id=product.id,
                    competitor_id=competitor.id,
                    competitor_product_name=match.title,
                    competitor_product_url=match.url,
                    current_price=match.price,
                    currency=match.currency,
                    match_confidence=Decimal(str(match.confidence_score)),
                    is_active=True,
                )
                db.add(link)

                links_created.append(
                    {
                        "merchant": match.merchant,
                        "url": match.url,
                        "price": str(match.price),
                        "confidence": match.confidence_percent,
                    }
                )

        except Exception as e:
            logger.error(f"Failed to auto-link {match.url}: {e}")
            await db.rollback()
            return []

    try:
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to commit auto-linked competitors: {e}")
        await db.rollback()
        return []

    logger.info(f"Auto-linked {len(links_created)} competitors for product {product.id}")

    return links_created
