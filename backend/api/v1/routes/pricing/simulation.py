# backend/api/v1/routes/pricing/simulation.py
"""
Rule testing and pricing simulation endpoints.
"""

import contextlib
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from core.rate_limit import ANALYSIS_RATE_LIMIT, limiter
from db.session import get_session
from models.pricing_rule import PricingRule
from models.product import Product
from models.user import User
from schemas.pricing import (
    RuleTestRequest,
    RuleTestResponse,
    SimulationRequest,
    SimulationResponse,
)
from services.pricing.recommendation_service import RecommendationService
from services.pricing.rule_evaluator import MarketSignals, RuleEvaluator
from services.pricing.signal_processor import SignalProcessor

router = APIRouter()


def _build_signals_from_mock(mock) -> MarketSignals:
    """Build MarketSignals from mock data."""
    competitor_prices = {}
    if mock.competitor_prices:
        for k, v in mock.competitor_prices.items():
            with contextlib.suppress(ValueError):
                competitor_prices[UUID(k)] = v

    return MarketSignals(
        sentiment_score=mock.sentiment_score,
        sentiment_change_24h=mock.sentiment_change_24h,
        mention_count_24h=mock.mention_count_24h or 0,
        mention_baseline=mock.mention_baseline or 0,
        viral_detected=mock.viral_detected or False,
        viral_reach=mock.viral_reach or 0,
        viral_engagement=mock.viral_engagement or 0,
        viral_sentiment=mock.viral_sentiment,
        competitor_prices=competitor_prices,
    )


def _signals_to_dict(signals: MarketSignals) -> dict:
    """Convert MarketSignals to dict for response."""
    return {
        "sentiment_score": float(signals.sentiment_score) if signals.sentiment_score is not None else None,
        "sentiment_change_24h": float(signals.sentiment_change_24h)
        if signals.sentiment_change_24h is not None
        else None,
        "mention_count_24h": signals.mention_count_24h,
        "mention_baseline": signals.mention_baseline,
        "viral_detected": signals.viral_detected,
        "viral_reach": signals.viral_reach,
        "viral_engagement": signals.viral_engagement,
        "viral_sentiment": float(signals.viral_sentiment) if signals.viral_sentiment is not None else None,
        "competitor_prices": {str(k): float(v) for k, v in signals.competitor_prices.items()},
    }


@router.post("/rules/{rule_id}/test", response_model=RuleTestResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def test_rule(
    request: Request,
    rule_id: UUID,
    data: RuleTestRequest = None,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Test a pricing rule without creating a recommendation."""
    rule = await db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")

    product = await db.get(Product, rule.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Build signals
    if data and data.mock_signals:
        signals = _build_signals_from_mock(data.mock_signals)
    else:
        signal_processor = SignalProcessor(db)
        signals = await signal_processor.gather_signals(product)

    # Evaluate rule
    rule_evaluator = RuleEvaluator(db)
    match_details = rule_evaluator._evaluate_rule(rule, product, signals)

    # Calculate price
    calculated_price = None
    change_percent = None
    reason = None

    if match_details:
        rec_service = RecommendationService(db)
        calculated_price = rec_service._calculate_new_price(product, rule, signals)

        if calculated_price:
            calculated_price = rec_service._apply_boundaries(calculated_price, product, rule)
            if product.current_price and product.current_price != 0:
                change_percent = ((calculated_price - product.current_price) / product.current_price) * 100
                change_percent = change_percent.quantize(Decimal("0.01"))
            else:
                change_percent = Decimal("0")
            reason = (
                f"Rule would change price from ${product.current_price} to ${calculated_price} ({change_percent:+.2f}%)"
            )
    else:
        reason = "Rule conditions not met"

    return RuleTestResponse(
        rule_id=rule.id,
        rule_name=rule.name,
        would_trigger=match_details is not None,
        match_details=match_details,
        signals_used=_signals_to_dict(signals),
        calculated_price=calculated_price,
        change_percent=change_percent,
        reason=reason,
    )


@router.post("/simulate", response_model=SimulationResponse)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def simulate_pricing(
    request: Request,
    data: SimulationRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Simulate pricing for a product - evaluate all rules without creating recommendations."""
    product = await db.get(Product, data.product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")

    # Build signals
    if data.mock_signals:
        signals = _build_signals_from_mock(data.mock_signals)
    else:
        signal_processor = SignalProcessor(db)
        signals = await signal_processor.gather_signals(product)

    # Get all active rules
    rule_evaluator = RuleEvaluator(db)
    all_rules = await rule_evaluator.get_active_rules(product.id, current_user.id)

    rec_service = RecommendationService(db)
    triggered_rules = []
    signals_dict = _signals_to_dict(signals)

    for rule in all_rules:
        match_details = rule_evaluator._evaluate_rule(rule, product, signals)

        calculated_price = None
        change_percent = None
        reason = None

        if match_details:
            calculated_price = rec_service._calculate_new_price(product, rule, signals)
            if calculated_price:
                calculated_price = rec_service._apply_boundaries(calculated_price, product, rule)
                if product.current_price and product.current_price != 0:
                    change_percent = ((calculated_price - product.current_price) / product.current_price) * 100
                    change_percent = change_percent.quantize(Decimal("0.01"))
                else:
                    change_percent = Decimal("0")
                reason = f"Would change price to ${calculated_price} ({change_percent:+.2f}%)"
        else:
            reason = "Conditions not met"

        triggered_rules.append(
            RuleTestResponse(
                rule_id=rule.id,
                rule_name=rule.name,
                would_trigger=match_details is not None,
                match_details=match_details,
                signals_used=signals_dict,
                calculated_price=calculated_price,
                change_percent=change_percent,
                reason=reason,
            )
        )

    # Best recommendation (highest priority triggered rule)
    best_recommendation = None
    for tr in triggered_rules:
        if tr.would_trigger and tr.calculated_price:
            best_recommendation = {
                "rule_id": str(tr.rule_id),
                "rule_name": tr.rule_name,
                "recommended_price": float(tr.calculated_price),
                "change_percent": float(tr.change_percent) if tr.change_percent else 0,
            }
            break

    return SimulationResponse(
        product_id=product.id,
        product_name=product.name,
        current_price=product.current_price,
        rules_evaluated=len(all_rules),
        rules_triggered=sum(1 for tr in triggered_rules if tr.would_trigger),
        triggered_rules=triggered_rules,
        best_recommendation=best_recommendation,
    )
