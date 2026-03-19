# backend/api/v1/routes/market_trends.py
"""
Market Trends API routes.
"""

from fastapi import APIRouter, HTTPException

from schemas.market_trends import (
    MarketTrendsRequest,
    MarketTrendsResponse,
    TrendCategoriesResponse,
    TrendSourcesResponse,
)
from services.market_trends_service import market_trends_service

router = APIRouter(prefix="/market-trends", tags=["Market Trends"])


@router.post("/analyze", response_model=MarketTrendsResponse)
async def analyze_market_trends(request: MarketTrendsRequest) -> MarketTrendsResponse:
    """
    Get AI-analyzed trending products.

    Analyzes current market trends and returns trending products
    with AI-generated insights and recommendations.
    """
    try:
        result = await market_trends_service.get_trends(
            category=request.category, source=request.source, limit=request.limit
        )

        return MarketTrendsResponse(
            trends=result["trends"],
            ai_summary=result["ai_summary"],
            generated_at=result["generated_at"],
            category=result.get("category"),
            source=result.get("source"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends", response_model=MarketTrendsResponse)
async def get_trends(category: str | None = None, source: str | None = None, limit: int = 10) -> MarketTrendsResponse:
    """
    Get trending products (GET version for easy testing).
    """
    try:
        result = await market_trends_service.get_trends(category=category, source=source, limit=limit)

        return MarketTrendsResponse(
            trends=result["trends"],
            ai_summary=result["ai_summary"],
            generated_at=result["generated_at"],
            category=result.get("category"),
            source=result.get("source"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=TrendCategoriesResponse)
async def get_categories() -> TrendCategoriesResponse:
    """Get available product categories for filtering."""
    categories = market_trends_service.get_categories()
    return TrendCategoriesResponse(categories=categories)


@router.get("/sources", response_model=TrendSourcesResponse)
async def get_sources() -> TrendSourcesResponse:
    """Get available data sources for filtering."""
    sources = market_trends_service.get_sources()
    return TrendSourcesResponse(sources=sources)


@router.get("/health")
async def market_trends_health():
    """Check if market trends service is operational."""
    return market_trends_service.get_health()
