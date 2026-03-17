# backend/schemas/market_trends.py
"""
Schemas for Market Trends / Trending Products feature.
"""

from pydantic import BaseModel, Field


class TrendingProductSchema(BaseModel):
    """A single trending product from market analysis."""

    rank: int = Field(..., description="Trend rank (1 = most trending)")
    name: str = Field(..., description="Product name")
    category: str = Field(..., description="Product category")
    price_range: str = Field(..., description="Price range e.g. '$20-$50'")
    trend_score: float = Field(..., ge=0, le=100, description="Trend score 0-100")
    sentiment: str = Field(..., description="positive, neutral, or negative")
    source: str = Field(..., description="Data source e.g. Amazon, TikTok")
    reason: str = Field(..., description="Why this product is trending")
    image_url: str | None = Field(None, description="Product image URL")


class MarketTrendsRequest(BaseModel):
    """Request for market trends analysis."""

    category: str | None = Field(None, description="Filter by category")
    source: str | None = Field(None, description="Filter by source (amazon, walmart, tiktok)")
    limit: int = Field(10, ge=1, le=50, description="Number of trends to return")


class MarketTrendsResponse(BaseModel):
    """Response with trending products and AI insights."""

    trends: list[TrendingProductSchema]
    ai_summary: str = Field(..., description="AI-generated market summary")
    generated_at: str = Field(..., description="Timestamp of analysis")
    category: str | None = Field(None, description="Category filter applied")
    source: str | None = Field(None, description="Source filter applied")


class CategorySchema(BaseModel):
    """Available category for filtering."""

    id: str
    name: str
    icon: str


class TrendCategoriesResponse(BaseModel):
    """Available categories for trend filtering."""

    categories: list[CategorySchema]


class TrendSourcesResponse(BaseModel):
    """Available data sources."""

    sources: list[str]
