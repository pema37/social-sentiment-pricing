# backend/api/v1/routes/pricing/_generation_endpoints.py
"""
Recommendation generation and diagnostic endpoints.

FIX (2026-01-27): generate-all now includes products with competitor links,
not just products with active rules. This enables WooCommerce products to
get competitor-based recommendations even without explicit pricing rules.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import ANALYSIS_RATE_LIMIT, limiter
from db.session import get_session
from models.competitor import Competitor
from models.competitor_product import CompetitorProduct
from models.pricing_rule import PricingRule
from models.product import Product
from models.user import User
from schemas.pricing import PriceRecommendationResponse
from services.pricing.recommendation_service import RecommendationService
from services.pricing.signal_processor import SignalProcessor

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/recommendations/diagnose/{product_id}")
async def diagnose_product_recommendations(
    request: Request,
    product_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Diagnose why recommendations aren't being generated for a product.

    Returns detailed information about:
    - Product status
    - Linked competitors and their prices
    - Active pricing rules
    - Current market signals
    - Why rules aren't matching
    """
    # Get product
    product = await db.get(Product, product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")

    diagnosis = {
        "product": {
            "id": str(product.id),
            "name": product.name,
            "current_price": str(product.current_price),
            "auto_pricing_enabled": product.auto_pricing_enabled,
            "min_price": str(product.min_price) if product.min_price else None,
            "max_price": str(product.max_price) if product.max_price else None,
        },
        "competitors": [],
        "rules": [],
        "signals": {},
        "issues": [],
        "recommendations": [],
    }

    # Check competitor products linked to this product
    stmt = (
        select(CompetitorProduct, Competitor)
        .join(Competitor, CompetitorProduct.competitor_id == Competitor.id)
        .where(CompetitorProduct.product_id == product_id)
        .where(CompetitorProduct.is_active == True)
    )
    result = await db.execute(stmt)
    competitor_products = result.all()

    if not competitor_products:
        diagnosis["issues"].append("NO_COMPETITOR_PRODUCTS: No competitor products linked to this product")

    for cp, competitor in competitor_products:
        diagnosis["competitors"].append(
            {
                "competitor_id": str(competitor.id),
                "competitor_name": competitor.name,
                "competitor_product_name": cp.competitor_product_name,
                "current_price": str(cp.current_price) if cp.current_price else None,
                "last_checked_at": cp.last_checked_at.isoformat() if cp.last_checked_at else None,
            }
        )

        if not cp.current_price:
            diagnosis["issues"].append(f"NO_COMPETITOR_PRICE: Competitor '{competitor.name}' has no price set")

    # Check pricing rules for this product
    stmt = select(PricingRule).where(PricingRule.product_id == product_id).where(PricingRule.user_id == current_user.id)
    result = await db.execute(stmt)
    rules = list(result.scalars().all())

    if not rules:
        diagnosis["issues"].append(
            "NO_RULES: No pricing rules configured for this product. "
            "Competitor-based recommendations can still be generated if competitor products are linked."
        )

    active_rules = [r for r in rules if r.is_active]
    if rules and not active_rules:
        diagnosis["issues"].append("NO_ACTIVE_RULES: Rules exist but none are active")

    for rule in rules:
        rule_info = {
            "id": str(rule.id),
            "name": rule.name,
            "rule_type": rule.rule_type.value if hasattr(rule.rule_type, "value") else rule.rule_type,
            "is_active": rule.is_active,
            "priority": rule.priority,
            "action": rule.action.value if hasattr(rule.action, "value") else rule.action,
            "action_value": str(rule.action_value),
            "cooldown_hours": rule.cooldown_hours,
            "last_triggered_at": rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        }

        # Check if rule is in cooldown
        if rule.last_triggered_at:
            cooldown_until = rule.last_triggered_at + timedelta(hours=rule.cooldown_hours)
            if datetime.now(UTC) < cooldown_until:
                rule_info["in_cooldown"] = True
                rule_info["cooldown_until"] = cooldown_until.isoformat()
                diagnosis["issues"].append(
                    f"RULE_COOLDOWN: Rule '{rule.name}' is in cooldown until {cooldown_until.isoformat()}"
                )

        # Check competitor rule has valid competitor_id
        rule_type_value = rule.rule_type.value if hasattr(rule.rule_type, "value") else rule.rule_type
        if rule_type_value == "competitor_relative":
            rule_info["competitor_id"] = str(rule.competitor_id) if rule.competitor_id else None
            if not rule.competitor_id:
                diagnosis["issues"].append(
                    f"MISSING_COMPETITOR_ID: Competitor rule '{rule.name}' has no competitor_id set"
                )
            else:
                # Check if competitor_id matches any linked competitor
                competitor_ids = [str(cp.competitor_id) for cp, _ in competitor_products]
                if str(rule.competitor_id) not in competitor_ids:
                    diagnosis["issues"].append(
                        f"COMPETITOR_NOT_LINKED: Rule '{rule.name}' references competitor "
                        f"{rule.competitor_id} but no CompetitorProduct links that competitor to this product"
                    )

        diagnosis["rules"].append(rule_info)

    # Gather current signals
    try:
        signal_processor = SignalProcessor(db)
        signals = await signal_processor.gather_signals(product)

        diagnosis["signals"] = {
            "sentiment_score": float(signals.sentiment_score) if signals.sentiment_score else None,
            "sentiment_change_24h": float(signals.sentiment_change_24h) if signals.sentiment_change_24h else None,
            "mention_count_24h": signals.mention_count_24h,
            "mention_baseline": signals.mention_baseline,
            "viral_detected": signals.viral_detected,
            "viral_reach": signals.viral_reach,
            "competitor_prices": {str(k): float(v) for k, v in signals.competitor_prices.items()},
            "is_trending": signals.is_trending,
            "trend_direction": signals.trend_direction,
        }

        if not signals.competitor_prices:
            diagnosis["issues"].append(
                "NO_COMPETITOR_SIGNALS: No competitor prices found in signals. "
                "Check that CompetitorProduct records have current_price set."
            )

    except Exception as e:
        diagnosis["signals"] = {"error": str(e)}
        diagnosis["issues"].append(f"SIGNAL_ERROR: {e!s}")

    # Try to generate recommendation and capture why it fails
    try:
        service = RecommendationService(db)
        recommendation = await service.generate_recommendation(product, current_user.id)

        if recommendation:
            diagnosis["recommendations"].append(
                {
                    "id": str(recommendation.id),
                    "current_price": str(recommendation.current_price),
                    "recommended_price": str(recommendation.recommended_price),
                    "change_percent": str(recommendation.change_percent),
                    "confidence_score": str(recommendation.confidence_score),
                    "status": recommendation.status.value
                    if hasattr(recommendation.status, "value")
                    else recommendation.status,
                    "data_source": recommendation.factors.get("data_source", "rule_based")
                    if recommendation.factors
                    else "rule_based",
                }
            )
        else:
            diagnosis["issues"].append(
                "NO_RECOMMENDATION_GENERATED: RecommendationService returned None. "
                "This means no rule matched, no competitor fallback was possible, "
                "or the calculated price equals current price."
            )
    except Exception as e:
        diagnosis["issues"].append(f"GENERATION_ERROR: {e!s}")

    # Summary
    diagnosis["summary"] = {
        "has_competitors": len(diagnosis["competitors"]) > 0,
        "has_active_rules": len([r for r in diagnosis["rules"] if r.get("is_active")]) > 0,
        "has_competitor_prices": bool(diagnosis["signals"].get("competitor_prices")),
        "issue_count": len(diagnosis["issues"]),
        "can_generate": len(diagnosis["issues"]) == 0 or len(diagnosis["recommendations"]) > 0,
    }

    return diagnosis


@router.post("/recommendations/generate/{product_id}", response_model=Optional[PriceRecommendationResponse])
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def generate_recommendation(
    request: Request,
    product_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger recommendation generation for a product."""
    product = await db.get(Product, product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")

    service = RecommendationService(db)
    recommendation = await service.generate_recommendation(product, current_user.id)
    return recommendation


@router.post("/recommendations/generate-all")
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def generate_all_recommendations(
    request: Request,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Generate recommendations for all eligible products.

    Eligible products:
    - Products with active pricing rules, OR
    - Products with linked competitor products (for competitor fallback)

    This enables:
    - Rule-based recommendations for products with explicit pricing rules
    - Competitor-based fallback recommendations for products with only competitor data

    FIX (2026-01-27): Now includes products with competitor links, not just
    products with active rules. This enables WooCommerce products (and any
    products without explicit rules) to get competitor-based recommendations.

    Previous behavior: Only products with active pricing rules were processed,
    which excluded WooCommerce products that had competitors linked but no rules.
    """
    # ═══════════════════════════════════════════════════════════════════════
    # FIX (2026-01-27): Include products with EITHER active rules OR competitor products
    # Previously: Only products with active rules (inner join excluded products without rules)
    # Now: Products with rules OR products with competitor products are included
    # ═══════════════════════════════════════════════════════════════════════

    # Subquery: products with active pricing rules
    has_active_rules = (
        select(PricingRule.product_id)
        .where(PricingRule.is_active == True)
        .where(PricingRule.user_id == current_user.id)
    )

    # Subquery: products with active competitor products that have prices
    has_competitor_products = (
        select(CompetitorProduct.product_id)
        .where(CompetitorProduct.is_active == True)
        .where(CompetitorProduct.current_price.isnot(None))
    )

    # Get products that match EITHER condition
    stmt = (
        select(Product)
        .where(Product.user_id == current_user.id)
        .where(Product.is_active == True)
        .where(or_(Product.id.in_(has_active_rules), Product.id.in_(has_competitor_products)))
    )

    result = await db.execute(stmt)
    products = list(result.scalars().all())

    if not products:
        return {
            "message": "No eligible products found. Products need either active pricing rules or linked competitor products with prices.",
            "products_checked": 0,
            "recommendations_created": 0,
            "recommendations_by_source": {"rule_based": 0, "competitor_only": 0},
            "results": [],
        }

    results = []
    recommendations_created = 0
    rule_based_count = 0
    competitor_only_count = 0

    service = RecommendationService(db)

    for product in products:
        try:
            recommendation = await service.generate_recommendation(product, current_user.id)

            if recommendation:
                recommendations_created += 1

                # Determine data source from factors
                factors = recommendation.factors or {}
                data_source = factors.get("data_source", "rule_based")

                if data_source == "competitor_only":
                    competitor_only_count += 1
                else:
                    rule_based_count += 1

                results.append(
                    {
                        "product_id": str(product.id),
                        "product_name": product.name,
                        "success": True,
                        "recommendation_id": str(recommendation.id),
                        "current_price": str(product.current_price),
                        "recommended_price": str(recommendation.recommended_price),
                        "change_percent": str(recommendation.change_percent),
                        "confidence_score": str(recommendation.confidence_score),
                        "data_source": data_source,
                        "requires_approval": recommendation.requires_approval,
                    }
                )
            else:
                results.append(
                    {
                        "product_id": str(product.id),
                        "product_name": product.name,
                        "success": True,
                        "recommendation_id": None,
                        "message": "No rule matched and no competitor fallback applicable, or price unchanged",
                    }
                )
        except Exception as e:
            logger.error(f"Error generating recommendation for product {product.id}: {e}")
            results.append(
                {"product_id": str(product.id), "product_name": product.name, "success": False, "error": str(e)}
            )

    return {
        "message": f"Processed {len(products)} products, created {recommendations_created} recommendations",
        "products_checked": len(products),
        "recommendations_created": recommendations_created,
        "recommendations_by_source": {"rule_based": rule_based_count, "competitor_only": competitor_only_count},
        "results": results,
    }
