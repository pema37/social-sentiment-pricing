"""Price Check schemas — public, unauthenticated pricing intelligence scan."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

# ── Request ───────────────────────────────────────────────────────────


class PriceCheckRequest(BaseModel):
    store_url: str = Field(..., description="Shopify or WooCommerce store URL")
    email: EmailStr = Field(..., description="Lead capture email")
    category: str | None = Field(None, description="Optional product category filter")


# ── Opportunity detail ────────────────────────────────────────────────


class PriceCheckOpportunity(BaseModel):
    product_name: str
    current_price: float
    suggested_price: float
    reason: str = Field(..., description="Human-readable explanation")
    confidence: float = Field(..., ge=0, le=100)


# ── Competitor detail ─────────────────────────────────────────────────


class CompetitorMatch(BaseModel):
    competitor_name: str
    competitor_url: str
    product_name: str
    competitor_price: float
    your_price: float
    gap_percent: float


# ── Sentiment detail ──────────────────────────────────────────────────


class SentimentSummary(BaseModel):
    total_mentions: int = 0
    positive_pct: float = 0.0
    negative_pct: float = 0.0
    neutral_pct: float = 0.0
    avg_score: float = Field(0.0, ge=-1, le=1)
    trend: str = "stable"  # "rising", "falling", "stable"
    trend_pct: float = 0.0
    top_mentions: list[str] = Field(default_factory=list)


# ── Full report ───────────────────────────────────────────────────────


class PriceCheckReport(BaseModel):
    store_name: str
    store_url: str
    products_scanned: int
    competitors_found: int
    avg_price_position: float = Field(0.0, description="+12 means 12% above market avg")
    price_position_label: str = "at"  # "above", "below", "at"
    competitor_matches: list[CompetitorMatch] = Field(default_factory=list)
    sentiment: SentimentSummary = Field(default_factory=SentimentSummary)
    opportunities: list[PriceCheckOpportunity] = Field(default_factory=list)
    estimated_monthly_impact: float = 0.0
    estimated_annual_impact: float = 0.0
    confidence: float = Field(0.0, ge=0, le=100)
    email: str = ""


# ── SSE event wrapper ─────────────────────────────────────────────────


class SSEEvent(BaseModel):
    """Streamed to the frontend during the Price Check scan."""

    agent: str = Field(..., description="scout | analyst | strategist | complete | error")
    status: str = Field(..., description="started | progress | done | error")
    message: str = ""
    data: dict | None = None


# ── Lead storage ──────────────────────────────────────────────────────


class PriceCheckLead(BaseModel):
    email: str
    store_url: str
    store_name: str = ""
    products_scanned: int = 0
    estimated_impact: float = 0.0
