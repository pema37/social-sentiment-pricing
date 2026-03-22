# backend/api/v1/routes/x402_agent_api.py
"""
x402 Agent-Facing API — Pay-per-query pricing intelligence for autonomous agents.

SF Agentic Commerce x402 Hackathon (Feb 2026)
These endpoints are designed to be consumed by AI agents via x402 micropayments.
No API keys, no subscriptions — just pay and query.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi_x402 import pay
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from db.session import get_session
from models.competitor_product import CompetitorProduct
from models.product import Product
from models.sentiment import Sentiment

router = APIRouter(prefix="/api/v1/agent", tags=["x402 Agent API"])


# ───────────────────── Response Schemas ───────────────────── #


class PricingIntelligenceResponse(BaseModel):
    product: str
    current_price: float
    competitor_avg: float
    competitor_min: float
    competitor_max: float
    recommendation: str
    confidence: float
    sentiment_score: float
    timestamp: str


class CrisisAlertResponse(BaseModel):
    brand: str
    crisis_detected: bool
    severity: str  # "none", "low", "medium", "high", "critical"
    description: str
    sentiment_shift: float
    recommended_action: str
    timestamp: str


class MarketTrendResponse(BaseModel):
    category: str
    trend_direction: str  # "up", "down", "stable"
    price_movement_pct: float
    volume_change_pct: float
    top_movers: list[str]
    ai_summary: str
    timestamp: str


class AgentHealthResponse(BaseModel):
    status: str
    agents: dict
    x402_enabled: bool
    endpoints_available: int
    timestamp: str


# ───────────────────── Free Endpoint (discovery) ───────────────────── #


@router.get("/health")
async def agent_health():
    """Free endpoint — lets agents discover ActualPrice capabilities."""
    return AgentHealthResponse(
        status="operational",
        agents={
            "scout": "monitoring competitors, launches, market movements",
            "analyst": "processing sentiment, detecting crises",
            "strategist": "generating pricing recommendations",
        },
        x402_enabled=True,
        endpoints_available=3,
        timestamp=datetime.now(UTC).isoformat(),
    )


# ───────────────────── Paid Endpoints (x402 gated) ───────────────────── #


@router.get("/pricing-intelligence")
@pay("$0.01")  # 1 cent per query in USDC
async def get_pricing_intelligence(
    product: str = "wireless-headphones",
    session: AsyncSession = Depends(get_session),
):
    """
    Agent-consumable pricing intelligence.
    Pay $0.01 USDC via x402 to get real-time competitive pricing data.

    The Scout agent monitors competitors, the Analyst processes sentiment,
    and the Strategist generates the recommendation — all in one query.
    """
    # Find matching product by name
    result = await session.execute(
        select(Product)
        .where(Product.name.ilike(f"%{product}%"))
        .where(Product.is_active.is_(True))
        .limit(1)
    )
    db_product = result.scalar_one_or_none()

    if not db_product:
        raise HTTPException(
            status_code=404,
            detail=f"No product data available for '{product}'",
        )

    # Get real competitor prices
    comp_result = await session.execute(
        select(CompetitorProduct)
        .where(CompetitorProduct.product_id == db_product.id)
        .where(CompetitorProduct.is_active.is_(True))
        .where(CompetitorProduct.current_price.isnot(None))
    )
    competitor_products = comp_result.scalars().all()

    if not competitor_products:
        raise HTTPException(
            status_code=404,
            detail=f"No competitor pricing data available for '{product}'",
        )

    comp_prices = [float(cp.current_price) for cp in competitor_products]
    competitor_min = min(comp_prices)
    competitor_max = max(comp_prices)
    competitor_avg = sum(comp_prices) / len(comp_prices)

    # Get recent sentiment score
    sentiment_result = await session.execute(
        select(func.avg(Sentiment.compound_score))
        .where(Sentiment.product_id == db_product.id)
        .where(Sentiment.analyzed_at >= datetime.now(UTC) - timedelta(days=7))
    )
    avg_sentiment = sentiment_result.scalar_one_or_none()
    sentiment_score = float(avg_sentiment) if avg_sentiment is not None else 0.0

    # Generate recommendation from real data
    current_price = float(db_product.current_price)
    if current_price > competitor_avg * 1.1:
        recommendation = "LOWER_PRICE"
        confidence = 0.85
    elif current_price < competitor_avg * 0.9:
        recommendation = "RAISE_PRICE"
        confidence = 0.78
    else:
        recommendation = "HOLD_PRICE"
        confidence = 0.72

    # Adjust confidence based on data quality
    confidence *= min(len(comp_prices) / 5.0, 1.0)  # More competitors = higher confidence

    return PricingIntelligenceResponse(
        product=product,
        current_price=round(current_price, 2),
        competitor_avg=round(competitor_avg, 2),
        competitor_min=round(competitor_min, 2),
        competitor_max=round(competitor_max, 2),
        recommendation=recommendation,
        confidence=round(confidence, 3),
        sentiment_score=round(sentiment_score, 3),
        timestamp=datetime.now(UTC).isoformat(),
    )


@router.get("/crisis-detection")
@pay("$0.01")
async def detect_crisis(
    brand: str = "nike",
    session: AsyncSession = Depends(get_session),
):
    """
    Real-time crisis detection for any brand.
    Pay $0.01 USDC via x402 to check if a brand is experiencing a social media crisis
    that could impact pricing decisions.

    The Analyst agent monitors social sentiment across platforms and flags
    significant negative shifts that require immediate pricing action.
    """
    # Find products matching the brand
    product_result = await session.execute(
        select(Product.id)
        .where(Product.name.ilike(f"%{brand}%"))
        .where(Product.is_active.is_(True))
    )
    product_ids = [row[0] for row in product_result.all()]

    if not product_ids:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for brand '{brand}'",
        )

    now = datetime.now(UTC)

    # Get recent sentiment (last 24h)
    recent_result = await session.execute(
        select(func.avg(Sentiment.compound_score), func.count(Sentiment.id))
        .where(Sentiment.product_id.in_(product_ids))
        .where(Sentiment.analyzed_at >= now - timedelta(hours=24))
    )
    recent_row = recent_result.one()
    recent_avg = float(recent_row[0]) if recent_row[0] is not None else None
    recent_count = recent_row[1]

    # Get baseline sentiment (7-30 days ago)
    baseline_result = await session.execute(
        select(func.avg(Sentiment.compound_score))
        .where(Sentiment.product_id.in_(product_ids))
        .where(Sentiment.analyzed_at >= now - timedelta(days=30))
        .where(Sentiment.analyzed_at < now - timedelta(days=7))
    )
    baseline_avg = baseline_result.scalar_one_or_none()
    baseline_avg = float(baseline_avg) if baseline_avg is not None else 0.0

    if recent_avg is None or recent_count < 3:
        return CrisisAlertResponse(
            brand=brand,
            crisis_detected=False,
            severity="none",
            description=f"Insufficient recent sentiment data for {brand} ({recent_count} mentions in 24h).",
            sentiment_shift=0.0,
            recommended_action="INSUFFICIENT_DATA — gather more sentiment before making pricing decisions",
            timestamp=now.isoformat(),
        )

    sentiment_shift = round(recent_avg - baseline_avg, 3)

    # Detect crisis: significant negative shift
    if sentiment_shift < -0.3:
        severity = "critical" if sentiment_shift < -0.5 else "high"
        return CrisisAlertResponse(
            brand=brand,
            crisis_detected=True,
            severity=severity,
            description=f"Significant negative sentiment shift detected for {brand}. "
            f"Recent avg: {recent_avg:.3f}, baseline: {baseline_avg:.3f} "
            f"({recent_count} mentions in 24h).",
            sentiment_shift=sentiment_shift,
            recommended_action="PAUSE_PRICE_INCREASES — wait 48-72 hours for sentiment to stabilize",
            timestamp=now.isoformat(),
        )
    elif sentiment_shift < -0.15:
        return CrisisAlertResponse(
            brand=brand,
            crisis_detected=True,
            severity="medium",
            description=f"Moderate negative sentiment trend for {brand}. "
            f"Recent avg: {recent_avg:.3f}, baseline: {baseline_avg:.3f}.",
            sentiment_shift=sentiment_shift,
            recommended_action="MONITOR_CLOSELY — delay aggressive pricing changes",
            timestamp=now.isoformat(),
        )
    else:
        return CrisisAlertResponse(
            brand=brand,
            crisis_detected=False,
            severity="none",
            description=f"No crisis detected for {brand}. Sentiment is within normal range "
            f"(recent: {recent_avg:.3f}, baseline: {baseline_avg:.3f}).",
            sentiment_shift=sentiment_shift,
            recommended_action="PROCEED_NORMALLY — safe to execute pricing changes",
            timestamp=now.isoformat(),
        )


@router.get("/market-trends")
@pay("$0.01")
async def get_market_trends(
    category: str = "electronics",
    session: AsyncSession = Depends(get_session),
):
    """
    Market trend analysis for a product category.
    Pay $0.01 USDC via x402 to get AI-generated market insights.

    The Scout agent collects market data, and the Strategist generates
    actionable trend analysis for pricing decisions.
    """
    now = datetime.now(UTC)

    # Find products in this category
    product_result = await session.execute(
        select(Product)
        .where(Product.category.ilike(f"%{category}%"))
        .where(Product.is_active.is_(True))
    )
    products = product_result.scalars().all()

    if not products:
        raise HTTPException(
            status_code=404,
            detail=f"No market data available for category '{category}'",
        )

    product_ids = [p.id for p in products]

    # Get competitor prices now vs 30 days ago
    current_prices_result = await session.execute(
        select(func.avg(CompetitorProduct.current_price))
        .where(CompetitorProduct.product_id.in_(product_ids))
        .where(CompetitorProduct.is_active.is_(True))
        .where(CompetitorProduct.current_price.isnot(None))
    )
    current_avg = current_prices_result.scalar_one_or_none()

    if current_avg is None:
        raise HTTPException(
            status_code=404,
            detail=f"No competitor pricing data for category '{category}'",
        )

    current_avg = float(current_avg)

    # Get sentiment volume change
    recent_volume = await session.execute(
        select(func.count(Sentiment.id))
        .where(Sentiment.product_id.in_(product_ids))
        .where(Sentiment.analyzed_at >= now - timedelta(days=7))
    )
    recent_vol = recent_volume.scalar_one() or 0

    baseline_volume = await session.execute(
        select(func.count(Sentiment.id))
        .where(Sentiment.product_id.in_(product_ids))
        .where(Sentiment.analyzed_at >= now - timedelta(days=37))
        .where(Sentiment.analyzed_at < now - timedelta(days=7))
    )
    baseline_vol = (baseline_volume.scalar_one() or 0) / max(1, 4)  # Normalize to 7-day window

    volume_change_pct = ((recent_vol - baseline_vol) / max(baseline_vol, 1)) * 100

    # Determine trend from product price data
    avg_base_price = sum(float(p.base_price) for p in products) / len(products)
    avg_current_price = sum(float(p.current_price) for p in products) / len(products)
    price_movement_pct = ((avg_current_price - avg_base_price) / max(avg_base_price, 0.01)) * 100

    if price_movement_pct > 3:
        direction = "up"
    elif price_movement_pct < -3:
        direction = "down"
    else:
        direction = "stable"

    # Top movers: products with largest price difference from base
    sorted_products = sorted(
        products,
        key=lambda p: abs(float(p.current_price) - float(p.base_price)),
        reverse=True,
    )
    top_movers = [p.name for p in sorted_products[:5]]

    competitive_pressure = "increasing" if direction == "down" else "moderate"
    strategy = "aggressive pricing" if direction == "down" else "maintain margins"

    return MarketTrendResponse(
        category=category,
        trend_direction=direction,
        price_movement_pct=round(price_movement_pct, 2),
        volume_change_pct=round(volume_change_pct, 2),
        top_movers=top_movers,
        ai_summary=f"The {category} market is trending {direction} based on {len(products)} tracked products. "
        f"Competitive pressure is {competitive_pressure} with avg competitor price at ${current_avg:.2f}. "
        f"Recommended strategy: {strategy}.",
        timestamp=now.isoformat(),
    )
