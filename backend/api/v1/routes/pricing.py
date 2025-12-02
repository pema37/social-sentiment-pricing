# backend/api/v1/routes/pricing.py
"""
Pricing API - Rules, recommendations, and approval workflow.
"""

from typing import Optional
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from backend.db.session import get_session
from backend.core.deps import get_current_user
from backend.models.user import User
from backend.models.product import Product
from backend.models.pricing_rule import PricingRule
from backend.models.price_recommendation import PriceRecommendation, RecommendationStatus
from backend.models.pricing_settings import PricingSettings
from backend.services.pricing.recommendation_service import RecommendationService
from backend.services.pricing.approval_service import ApprovalService
from backend.services.pricing.signal_processor import SignalProcessor
from backend.services.pricing.rule_evaluator import RuleEvaluator, MarketSignals
from backend.services.pricing.outcome_service import OutcomeService 
from backend.models.recommendation_outcome import OutcomeLabel
from backend.schemas.pricing import (
    PricingRuleCreate,
    PricingRuleUpdate,
    PricingRuleResponse,
    PriceRecommendationResponse,
    RecommendationApprove,
    RecommendationReject,
    PricingSettingsUpdate,
    PricingSettingsResponse,
    RuleTestRequest,
    RuleTestResponse,
    SimulationRequest,
    SimulationResponse,
    OutcomeRecordRequest,
    OutcomeResponse,
    RulePerformanceResponse,
    AccuracyStatsResponse,
)

router = APIRouter(prefix="/pricing", tags=["pricing"])


# ═══════════════════════════════════════════════════════════════
# PRICING RULES
# ═══════════════════════════════════════════════════════════════

@router.post("/rules", response_model=PricingRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    data: PricingRuleCreate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new pricing rule."""
    
    # Verify product ownership
    product = db.get(Product, data.product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")
    
    rule = PricingRule(
        user_id=current_user.id,
        **data.model_dump()
    )
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return rule


@router.get("/rules", response_model=list[PricingRuleResponse])
def list_rules(
    product_id: Optional[UUID] = Query(default=None),
    is_active: Optional[bool] = Query(default=None),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List pricing rules."""
    
    stmt = select(PricingRule).where(PricingRule.user_id == current_user.id)
    
    if product_id:
        stmt = stmt.where(PricingRule.product_id == product_id)
    if is_active is not None:
        stmt = stmt.where(PricingRule.is_active == is_active)
    
    stmt = stmt.order_by(PricingRule.priority.desc())
    
    return list(db.exec(stmt).all())


@router.get("/rules/{rule_id}", response_model=PricingRuleResponse)
def get_rule(
    rule_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific pricing rule."""
    
    rule = db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return rule


@router.patch("/rules/{rule_id}", response_model=PricingRuleResponse)
def update_rule(
    rule_id: UUID,
    data: PricingRuleUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update a pricing rule."""
    
    rule = db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a pricing rule."""
    
    rule = db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(rule)
    db.commit()


# ═══════════════════════════════════════════════════════════════
# RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════

@router.post("/recommendations/generate/{product_id}", response_model=Optional[PriceRecommendationResponse])
def generate_recommendation(
    product_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger recommendation generation for a product."""
    
    product = db.get(Product, product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")
    
    service = RecommendationService(db)
    recommendation = service.generate_recommendation(product, current_user.id)
    
    if not recommendation:
        return None
    
    return recommendation


@router.get("/recommendations", response_model=list[PriceRecommendationResponse])
def list_recommendations(
    status: Optional[RecommendationStatus] = Query(default=None),
    product_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List price recommendations."""
    
    stmt = select(PriceRecommendation).where(
        PriceRecommendation.user_id == current_user.id
    )
    
    if status:
        stmt = stmt.where(PriceRecommendation.status == status)
    if product_id:
        stmt = stmt.where(PriceRecommendation.product_id == product_id)
    
    stmt = stmt.order_by(PriceRecommendation.created_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    
    return list(db.exec(stmt).all())


@router.get("/recommendations/pending", response_model=list[PriceRecommendationResponse])
def list_pending_recommendations(
    product_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List pending recommendations (approval queue)."""
    
    service = RecommendationService(db)
    return service.get_pending_recommendations(
        current_user.id, product_id, limit, offset
    )


@router.get("/recommendations/{recommendation_id}", response_model=PriceRecommendationResponse)
def get_recommendation(
    recommendation_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific recommendation."""
    
    recommendation = db.get(PriceRecommendation, recommendation_id)
    if not recommendation or recommendation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    
    return recommendation


@router.post("/recommendations/{recommendation_id}/approve", response_model=PriceRecommendationResponse)
def approve_recommendation(
    recommendation_id: UUID,
    data: RecommendationApprove = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending recommendation."""
    
    service = ApprovalService(db)
    
    try:
        return service.approve(recommendation_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recommendations/{recommendation_id}/reject", response_model=PriceRecommendationResponse)
def reject_recommendation(
    recommendation_id: UUID,
    data: RecommendationReject,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Reject a pending recommendation."""
    
    service = ApprovalService(db)
    
    try:
        return service.reject(recommendation_id, current_user.id, data.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recommendations/{recommendation_id}/apply", response_model=PriceRecommendationResponse)
def apply_recommendation(
    recommendation_id: UUID,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Apply an approved recommendation (push price to e-commerce)."""
    
    service = ApprovalService(db)
    
    try:
        return service.apply_price(recommendation_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════

@router.get("/settings", response_model=PricingSettingsResponse)
def get_settings(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get pricing settings for current user."""
    
    stmt = select(PricingSettings).where(PricingSettings.user_id == current_user.id)
    settings = db.exec(stmt).first()
    
    # Create default settings if none exist
    if not settings:
        settings = PricingSettings(user_id=current_user.id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return settings


@router.patch("/settings", response_model=PricingSettingsResponse)
def update_settings(
    data: PricingSettingsUpdate,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update pricing settings."""
    
    stmt = select(PricingSettings).where(PricingSettings.user_id == current_user.id)
    settings = db.exec(stmt).first()
    
    if not settings:
        settings = PricingSettings(user_id=current_user.id)
    
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings, key, value)
    
    db.add(settings)
    db.commit()
    db.refresh(settings)
    
    return settings


# ═══════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
def get_pricing_stats(
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get pricing statistics."""
    
    service = ApprovalService(db)
    return service.get_approval_stats(current_user.id, days)


# ═══════════════════════════════════════════════════════════════
# RULE TESTING & SIMULATION
# ═══════════════════════════════════════════════════════════════

@router.post("/rules/{rule_id}/test", response_model=RuleTestResponse)
def test_rule(
    rule_id: UUID,
    data: RuleTestRequest = None,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Test a pricing rule without creating a recommendation.
    
    Use mock_signals to test with specific values, or leave empty to use real data.
    """
    # Get rule
    rule = db.get(PricingRule, rule_id)
    if not rule or rule.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    # Get product
    product = db.get(Product, rule.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Build signals
    if data and data.mock_signals:
        # Use mock signals
        mock = data.mock_signals
        competitor_prices = {}
        if mock.competitor_prices:
            for k, v in mock.competitor_prices.items():
                try:
                    competitor_prices[UUID(k)] = v
                except ValueError:
                    pass  # Skip invalid UUID keys
        
        signals = MarketSignals(
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
    else:
        # Use real signals
        signal_processor = SignalProcessor(db)
        signals = signal_processor.gather_signals(product)

    # Evaluate rule
    rule_evaluator = RuleEvaluator(db)
    match_details = rule_evaluator._evaluate_rule(rule, product, signals)
    
    # Calculate what price would be
    calculated_price = None
    change_percent = None
    reason = None
    
    if match_details:
        rec_service = RecommendationService(db)
        calculated_price = rec_service._calculate_new_price(product, rule, signals)
        
        if calculated_price:
            calculated_price = rec_service._apply_boundaries(calculated_price, product, rule)
            change_percent = ((calculated_price - product.current_price) / product.current_price) * 100
            change_percent = change_percent.quantize(Decimal("0.01"))
            reason = f"Rule would change price from ${product.current_price} to ${calculated_price} ({change_percent:+.2f}%)"
    else:
        reason = "Rule conditions not met"
    
    # Build signals dict for response
    signals_used = {
        "sentiment_score": float(signals.sentiment_score) if signals.sentiment_score else None,
        "sentiment_change_24h": float(signals.sentiment_change_24h) if signals.sentiment_change_24h else None,
        "mention_count_24h": signals.mention_count_24h,
        "mention_baseline": signals.mention_baseline,
        "viral_detected": signals.viral_detected,
        "viral_reach": signals.viral_reach,
        "viral_engagement": signals.viral_engagement,
        "viral_sentiment": float(signals.viral_sentiment) if signals.viral_sentiment else None,
        "competitor_prices": {str(k): float(v) for k, v in signals.competitor_prices.items()},
    }
    
    return RuleTestResponse(
        rule_id=rule.id,
        rule_name=rule.name,
        would_trigger=match_details is not None,
        match_details=match_details,
        signals_used=signals_used,
        calculated_price=calculated_price,
        change_percent=change_percent,
        reason=reason,
    )


@router.post("/simulate", response_model=SimulationResponse)
def simulate_pricing(
    data: SimulationRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Simulate pricing for a product - evaluate all rules without creating recommendations.
    
    Returns which rules would trigger and what the resulting price would be.
    """
    # Get product
    product = db.get(Product, data.product_id)
    if not product or product.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Build signals
    if data.mock_signals:
        mock = data.mock_signals
        competitor_prices = {}
        if mock.competitor_prices:
            for k, v in mock.competitor_prices.items():
                try:
                    competitor_prices[UUID(k)] = v
                except ValueError:
                    pass  # Skip invalid UUID keys
        
        signals = MarketSignals(
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
    else:
        signal_processor = SignalProcessor(db)
        signals = signal_processor.gather_signals(product)
    
    # Get all active rules
    rule_evaluator = RuleEvaluator(db)
    all_rules = rule_evaluator.get_active_rules(product.id, current_user.id)
    
    rec_service = RecommendationService(db)
    triggered_rules = []
    
    signals_dict = {
        "sentiment_score": float(signals.sentiment_score) if signals.sentiment_score else None,
        "sentiment_change_24h": float(signals.sentiment_change_24h) if signals.sentiment_change_24h else None,
        "mention_count_24h": signals.mention_count_24h,
        "mention_baseline": signals.mention_baseline,
        "viral_detected": signals.viral_detected,
        "viral_reach": signals.viral_reach,
        "viral_engagement": signals.viral_engagement,
        "viral_sentiment": float(signals.viral_sentiment) if signals.viral_sentiment else None,
        "competitor_prices": {str(k): float(v) for k, v in signals.competitor_prices.items()},
    }
    
    for rule in all_rules:
        match_details = rule_evaluator._evaluate_rule(rule, product, signals)
        
        calculated_price = None
        change_percent = None
        reason = None
        
        if match_details:
            calculated_price = rec_service._calculate_new_price(product, rule, signals)
            if calculated_price:
                calculated_price = rec_service._apply_boundaries(calculated_price, product, rule)
                change_percent = ((calculated_price - product.current_price) / product.current_price) * 100
                change_percent = change_percent.quantize(Decimal("0.01"))
                reason = f"Would change price to ${calculated_price} ({change_percent:+.2f}%)"
        else:
            reason = "Conditions not met"
        
        triggered_rules.append(RuleTestResponse(
            rule_id=rule.id,
            rule_name=rule.name,
            would_trigger=match_details is not None,
            match_details=match_details,
            signals_used=signals_dict,
            calculated_price=calculated_price,
            change_percent=change_percent,
            reason=reason,
        ))
    
    # Build best recommendation (highest priority triggered rule)
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


# ═══════════════════════════════════════════════════════════════
# OUTCOME TRACKING
# ═══════════════════════════════════════════════════════════════

@router.post("/outcomes/{recommendation_id}/record", response_model=OutcomeResponse)
def record_outcome(
    recommendation_id: UUID,
    data: OutcomeRecordRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Record the outcome/performance of an applied recommendation."""
    
    service = OutcomeService(db)
    
    try:
        return service.record_outcome(
            recommendation_id=recommendation_id,
            user_id=current_user.id,
            sales_count_before=data.sales_count_before,
            units_sold_before=data.units_sold_before,
            revenue_before=data.revenue_before,
            sales_count_after=data.sales_count_after,
            units_sold_after=data.units_sold_after,
            revenue_after=data.revenue_after,
            measurement_window_hours=data.measurement_window_hours,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/outcomes", response_model=list[OutcomeResponse])
def list_outcomes(
    product_id: Optional[UUID] = Query(default=None),
    rule_id: Optional[UUID] = Query(default=None),
    outcome_label: Optional[OutcomeLabel] = Query(default=None),
    days: int = Query(default=30, le=365),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List recommendation outcomes."""
    
    service = OutcomeService(db)
    return service.get_outcomes(
        user_id=current_user.id,
        product_id=product_id,
        rule_id=rule_id,
        outcome_label=outcome_label,
        days=days,
        limit=limit,
        offset=offset,
    )


@router.get("/outcomes/accuracy", response_model=AccuracyStatsResponse)
def get_accuracy_stats(
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get overall accuracy statistics for recommendations."""
    
    service = OutcomeService(db)
    return service.get_accuracy_stats(current_user.id, days)


@router.get("/rules/{rule_id}/performance", response_model=RulePerformanceResponse)
def get_rule_performance(
    rule_id: UUID,
    days: int = Query(default=90, le=365),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get performance statistics for a specific pricing rule."""
    
    service = OutcomeService(db)
    
    try:
        return service.get_rule_performance(rule_id, current_user.id, days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
