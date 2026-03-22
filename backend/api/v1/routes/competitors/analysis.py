# backend/api/v1/routes/competitors/analysis.py
"""Competitor analysis and comparison endpoints."""

import uuid as uuid_lib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from api.v1.routes.auth import get_current_user
from db.session import get_session
from models.competitor import Competitor
from models.competitor_price_history import CompetitorPriceHistory
from models.competitor_product import CompetitorProduct
from models.product import Product
from models.user import User
from schemas.competitor import CompetitorAlert, CompetitorPriceComparison

router = APIRouter()


@router.get("/compare/{product_id}", response_model=CompetitorPriceComparison)
async def compare_prices(
    request: Request,
    product_id: uuid_lib.UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Compare your product price against all tracked competitors."""
    result = await db.execute(select(Product).where(Product.id == product_id).where(Product.user_id == current_user.id))
    product = result.scalars().first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    cp_result = await db.execute(
        select(CompetitorProduct)
        .where(CompetitorProduct.product_id == product_id)
        .where(CompetitorProduct.is_active)
        .where(CompetitorProduct.current_price.is_not(None))
    )
    competitor_products = cp_result.scalars().all()

    if not competitor_products:
        return CompetitorPriceComparison(
            product_id=product_id,
            product_name=product.name,
            your_price=product.current_price,
            competitor_prices=[],
            your_position="no_data",
            recommendation="Add competitor product links to enable price comparison.",
        )

    # Batch-fetch all competitors in one query instead of N+1
    competitor_ids = {cp.competitor_id for cp in competitor_products}
    comp_result = await db.execute(
        select(Competitor).where(Competitor.id.in_(competitor_ids))
    )
    competitors_map = {c.id: c for c in comp_result.scalars().all()}

    competitor_prices = []
    for cp in competitor_products:
        competitor = competitors_map.get(cp.competitor_id)

        diff = product.current_price - cp.current_price
        competitor_prices.append(
            {
                "competitor_name": competitor.name if competitor else "Unknown",
                "price": cp.current_price,
                "url": cp.competitor_product_url,
                "difference": diff,
                "difference_percent": (diff / cp.current_price * 100).quantize(Decimal("0.01"))
                if cp.current_price
                else None,
                "last_updated": cp.last_price_update,
            }
        )

    prices = [cp.current_price for cp in competitor_products]
    lowest = min(prices)
    highest = max(prices)
    average = sum(prices) / len(prices)

    if product.current_price <= lowest:
        position = "lowest"
    elif product.current_price >= highest:
        position = "highest"
    else:
        position = "middle"

    if position == "highest":
        recommendation = f"You're priced {((product.current_price - average) / average * 100):.1f}% above average. Consider lowering price to remain competitive."
    elif position == "lowest":
        recommendation = f"You're the price leader at {((average - product.current_price) / average * 100):.1f}% below average. Opportunity to increase margins."
    else:
        recommendation = "Competitively positioned. Monitor for competitor changes."

    return CompetitorPriceComparison(
        product_id=product_id,
        product_name=product.name,
        your_price=product.current_price,
        competitor_prices=competitor_prices,
        lowest_competitor_price=lowest,
        highest_competitor_price=highest,
        average_competitor_price=average.quantize(Decimal("0.01")),
        your_position=position,
        recommendation=recommendation,
    )


@router.get("/alerts", response_model=list[CompetitorAlert])
async def get_competitor_alerts(
    request: Request,
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get recent significant competitor price changes."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)

    # Single joined query instead of N+1 (3 queries per history record)
    result = await db.execute(
        select(CompetitorPriceHistory, CompetitorProduct, Competitor, Product)
        .join(CompetitorProduct, CompetitorPriceHistory.competitor_product_id == CompetitorProduct.id)
        .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
        .join(Product, CompetitorProduct.product_id == Product.id)
        .where(Product.user_id == current_user.id)
        .where(CompetitorPriceHistory.observed_at >= cutoff)
        .where(
            (CompetitorPriceHistory.change_type == "promotion")
            | (CompetitorPriceHistory.change_type == "restock")
            | (func.abs(CompetitorPriceHistory.change_percent) > 5)
        )
        .order_by(CompetitorPriceHistory.observed_at.desc())
    )
    rows = result.all()

    alerts = []
    for h, cp, competitor, product in rows:
        if h.change_type == "promotion":
            alert_type = "price_drop"
            suggested_action = "Monitor closely. Consider matching if promotion persists."
        elif h.change_type == "restock":
            alert_type = "back_in_stock"
            suggested_action = "Competitor product back in stock. Review your inventory."
        elif h.change_percent and h.change_percent < 0:
            alert_type = "price_drop"
            suggested_action = "Evaluate if price adjustment needed to stay competitive."
        else:
            alert_type = "price_increase"
            suggested_action = "Opportunity to increase margins while remaining competitive."

        alerts.append(
            CompetitorAlert(
                alert_type=alert_type,
                competitor_name=competitor.name,
                competitor_product_name=cp.competitor_product_name,
                product_id=product.id,
                your_product_name=product.name,
                old_price=h.old_price,
                new_price=h.new_price,
                change_percent=h.change_percent,
                your_current_price=product.current_price,
                suggested_action=suggested_action,
                observed_at=h.observed_at,
            )
        )

    return alerts


# ═══════════════════════════════════════════════════════════════════════════════
# AI COMPETITOR ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


from pydantic import BaseModel


class AICompetitorAnalysisResponse(BaseModel):
    """AI-generated competitor analysis."""

    competitor_id: uuid_lib.UUID
    competitor_name: str
    strategy_detected: str  # "aggressive", "premium", "discount", "stable"
    analysis: str
    recommended_response: str
    confidence: float
    ai_powered: bool = True


@router.get("/{competitor_id}/ai-analysis", response_model=AICompetitorAnalysisResponse)
async def get_ai_competitor_analysis(
    request: Request,
    competitor_id: uuid_lib.UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get AI-powered analysis of a competitor's pricing strategy.

    Analyzes price history patterns to detect:
    - Pricing strategy (aggressive, premium, discount, stable)
    - Seasonal patterns
    - Response recommendations
    """
    from services.ai_generator import ai_generator

    # Get competitor
    result = await db.execute(
        select(Competitor).where(Competitor.id == competitor_id).where(Competitor.user_id == current_user.id)
    )
    competitor = result.scalars().first()

    if not competitor:
        raise HTTPException(status_code=404, detail="Competitor not found")

    # Get competitor products with price history
    cp_result = await db.execute(
        select(CompetitorProduct)
        .where(CompetitorProduct.competitor_id == competitor_id)
        .where(CompetitorProduct.is_active)
    )
    competitor_products = cp_result.scalars().all()

    # Get price history for analysis
    price_changes = []
    for cp in competitor_products:
        history_result = await db.execute(
            select(CompetitorPriceHistory)
            .where(CompetitorPriceHistory.competitor_product_id == cp.id)
            .order_by(CompetitorPriceHistory.observed_at.desc())
            .limit(20)
        )
        histories = history_result.scalars().all()

        for h in histories:
            if h.change_percent:
                price_changes.append(
                    {
                        "product": cp.competitor_product_name,
                        "change_percent": float(h.change_percent),
                        "change_type": h.change_type,
                        "date": h.observed_at.isoformat() if h.observed_at else None,
                    }
                )

    # Detect strategy based on patterns
    if not price_changes:
        strategy = "unknown"
        analysis = f"No price history available for {competitor.name}. Add competitor products to track their pricing patterns."
        recommendation = "Start tracking competitor products to enable AI analysis."
        confidence = 0.1
    else:
        # Calculate metrics
        avg_change = sum(p["change_percent"] for p in price_changes) / len(price_changes)
        drops = sum(1 for p in price_changes if p["change_percent"] < -2)
        increases = sum(1 for p in price_changes if p["change_percent"] > 2)
        promotions = sum(1 for p in price_changes if p.get("change_type") == "promotion")

        # Determine strategy
        if promotions > len(price_changes) * 0.3 or drops > increases * 2:
            strategy = "aggressive"
        elif increases > drops * 2 and avg_change > 3:
            strategy = "premium"
        elif avg_change < -2:
            strategy = "discount"
        else:
            strategy = "stable"

        confidence = min(0.9, 0.3 + len(price_changes) * 0.03)

        # Use AI for deeper analysis if available
        if ai_generator.is_available():
            try:
                ai_result = await _generate_ai_analysis(
                    ai_generator,
                    competitor.name,
                    strategy,
                    price_changes,
                    avg_change,
                )
                analysis = ai_result["analysis"]
                recommendation = ai_result["recommendation"]
                confidence = min(0.95, confidence + 0.1)
            except Exception:
                analysis, recommendation = _generate_basic_analysis(
                    competitor.name, strategy, avg_change, len(price_changes)
                )
        else:
            analysis, recommendation = _generate_basic_analysis(
                competitor.name, strategy, avg_change, len(price_changes)
            )

    return AICompetitorAnalysisResponse(
        competitor_id=competitor_id,
        competitor_name=competitor.name,
        strategy_detected=strategy,
        analysis=analysis,
        recommended_response=recommendation,
        confidence=confidence,
        ai_powered=ai_generator.is_available() if price_changes else False,
    )


def _generate_basic_analysis(name: str, strategy: str, avg_change: float, data_points: int) -> tuple:
    """Generate basic analysis without AI."""
    strategies = {
        "aggressive": (
            f"{name} shows aggressive pricing with frequent discounts and promotions.",
            "Monitor closely. Match critical promotions but avoid a price war.",
        ),
        "premium": (
            f"{name} is positioning as premium with consistent price increases.",
            "Opportunity to capture price-sensitive customers. Emphasize value.",
        ),
        "discount": (
            f"{name} appears to be in discount mode with declining prices.",
            "Focus on value differentiation rather than price matching.",
        ),
        "stable": (
            f"{name} maintains stable pricing with minimal changes.",
            "Safe to maintain current pricing strategy. Focus on other differentiators.",
        ),
        "unknown": (
            f"Insufficient data to analyze {name}'s pricing strategy.",
            "Continue monitoring to gather more pricing data.",
        ),
    }
    return strategies.get(strategy, strategies["unknown"])


async def _generate_ai_analysis(ai_generator, name: str, strategy: str, changes: list, avg_change: float) -> dict:
    """Generate AI-powered analysis."""
    import json

    prompt = f"""Analyze this competitor's pricing behavior:

Competitor: {name}
Detected Strategy: {strategy}
Average Price Change: {avg_change:.1f}%
Recent Changes: {json.dumps(changes[:10])}

Provide:
1. A 2-3 sentence analysis of their pricing strategy
2. A specific recommendation for how to respond

Return JSON: {{"analysis": "...", "recommendation": "..."}}"""

    system_prompt = "You are a competitive pricing analyst. Be specific and actionable."
    result_text, _provider = await ai_generator._generate(
        system_prompt=system_prompt,
        user_message=prompt,
        temperature=0.5,
        max_tokens=300,
    )

    return ai_generator._parse_json_response(result_text)
