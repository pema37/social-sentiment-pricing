# backend/api/v1/routes/pricing/recommendations.py
"""
Price recommendations and approval workflow endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlmodel import select

from db.session import get_session
from core.deps import get_current_user
from core.rate_limit import limiter, WRITE_RATE_LIMIT, ANALYSIS_RATE_LIMIT
from models.user import User
from models.product import Product
from models.pricing_rule import PricingRule
from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.competitor_product import CompetitorProduct
from models.competitor import Competitor
from services.pricing.recommendation_service import RecommendationService
from services.pricing.approval_service import ApprovalService
from services.pricing.signal_processor import SignalProcessor
from services.pricing.rule_evaluator import RuleEvaluator
from schemas.common import PaginatedResponse, PaginationParams
from schemas.pricing import (
    PriceRecommendationResponse,
    RecommendationApprove,
    RecommendationReject,
)
from datetime import datetime, timedelta

router = APIRouter()


# ============================================================
# NEW: Diagnostic endpoint to debug why recommendations aren't generated
# ============================================================

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
        diagnosis["competitors"].append({
            "competitor_id": str(competitor.id),
            "competitor_name": competitor.name,
            "competitor_product_name": cp.competitor_product_name,
            "current_price": str(cp.current_price) if cp.current_price else None,
            "last_checked_at": cp.last_checked_at.isoformat() if cp.last_checked_at else None,
        })
        
        if not cp.current_price:
            diagnosis["issues"].append(
                f"NO_COMPETITOR_PRICE: Competitor '{competitor.name}' has no price set"
            )
    
    # Check pricing rules for this product
    stmt = (
        select(PricingRule)
        .where(PricingRule.product_id == product_id)
        .where(PricingRule.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    rules = list(result.scalars().all())
    
    if not rules:
        diagnosis["issues"].append("NO_RULES: No pricing rules configured for this product")
    
    active_rules = [r for r in rules if r.is_active]
    if rules and not active_rules:
        diagnosis["issues"].append("NO_ACTIVE_RULES: Rules exist but none are active")
    
    for rule in rules:
        rule_info = {
            "id": str(rule.id),
            "name": rule.name,
            "rule_type": rule.rule_type.value if hasattr(rule.rule_type, 'value') else rule.rule_type,
            "is_active": rule.is_active,
            "priority": rule.priority,
            "action": rule.action.value if hasattr(rule.action, 'value') else rule.action,
            "action_value": str(rule.action_value),
            "cooldown_hours": rule.cooldown_hours,
            "last_triggered_at": rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        }
        
        # Check if rule is in cooldown
        if rule.last_triggered_at:
            cooldown_until = rule.last_triggered_at + timedelta(hours=rule.cooldown_hours)
            if datetime.utcnow() < cooldown_until:
                rule_info["in_cooldown"] = True
                rule_info["cooldown_until"] = cooldown_until.isoformat()
                diagnosis["issues"].append(
                    f"RULE_COOLDOWN: Rule '{rule.name}' is in cooldown until {cooldown_until.isoformat()}"
                )
        
        # Check competitor rule has valid competitor_id
        if rule.rule_type == "competitor_relative" or (hasattr(rule.rule_type, 'value') and rule.rule_type.value == "competitor_relative"):
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
                        f"COMPETITOR_NOT_LINKED: Rule '{rule.name}' references competitor {rule.competitor_id} "
                        f"but no CompetitorProduct links that competitor to this product"
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
        diagnosis["issues"].append(f"SIGNAL_ERROR: {str(e)}")
    
    # Try to generate recommendation and capture why it fails
    try:
        service = RecommendationService(db)
        recommendation = await service.generate_recommendation(product, current_user.id)
        
        if recommendation:
            diagnosis["recommendations"].append({
                "id": str(recommendation.id),
                "current_price": str(recommendation.current_price),
                "recommended_price": str(recommendation.recommended_price),
                "change_percent": str(recommendation.change_percent),
                "confidence_score": str(recommendation.confidence_score),
                "status": recommendation.status.value if hasattr(recommendation.status, 'value') else recommendation.status,
            })
        else:
            diagnosis["issues"].append(
                "NO_RECOMMENDATION_GENERATED: RecommendationService returned None. "
                "This means no rule matched or the calculated price equals current price."
            )
    except Exception as e:
        diagnosis["issues"].append(f"GENERATION_ERROR: {str(e)}")
    
    # Summary
    diagnosis["summary"] = {
        "has_competitors": len(diagnosis["competitors"]) > 0,
        "has_active_rules": len([r for r in diagnosis["rules"] if r.get("is_active")]) > 0,
        "has_competitor_prices": bool(diagnosis["signals"].get("competitor_prices")),
        "issue_count": len(diagnosis["issues"]),
        "can_generate": len(diagnosis["issues"]) == 0 or len(diagnosis["recommendations"]) > 0,
    }
    
    return diagnosis


# ============================================================
# NEW: Generate recommendations for ALL products at once
# ============================================================

@router.post("/recommendations/generate-all")
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def generate_all_recommendations(
    request: Request,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Generate recommendations for all products with active rules.
    
    Useful for:
    - Initial setup/testing
    - Manual trigger instead of waiting for scheduled task
    - Demo purposes
    """
    # Get all products with active rules for this user
    stmt = (
        select(Product)
        .join(PricingRule, PricingRule.product_id == Product.id)
        .where(Product.user_id == current_user.id)
        .where(PricingRule.is_active == True)
        .distinct()
    )
    
    result = await db.execute(stmt)
    products = list(result.scalars().all())
    
    if not products:
        return {
            "message": "No products with active pricing rules found",
            "products_checked": 0,
            "recommendations_created": 0,
            "results": []
        }
    
    results = []
    recommendations_created = 0
    
    service = RecommendationService(db)
    
    for product in products:
        try:
            recommendation = await service.generate_recommendation(product, current_user.id)
            
            if recommendation:
                recommendations_created += 1
                results.append({
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "success": True,
                    "recommendation_id": str(recommendation.id),
                    "current_price": str(product.current_price),
                    "recommended_price": str(recommendation.recommended_price),
                    "change_percent": str(recommendation.change_percent),
                })
            else:
                results.append({
                    "product_id": str(product.id),
                    "product_name": product.name,
                    "success": True,
                    "recommendation_id": None,
                    "message": "No rule matched or no price change needed"
                })
        except Exception as e:
            results.append({
                "product_id": str(product.id),
                "product_name": product.name,
                "success": False,
                "error": str(e)
            })
    
    return {
        "message": f"Processed {len(products)} products, created {recommendations_created} recommendations",
        "products_checked": len(products),
        "recommendations_created": recommendations_created,
        "results": results
    }


# ============================================================
# Existing endpoints below
# ============================================================

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

@router.get("/recommendations/stats")
async def get_recommendation_stats(
    request: Request,
    days: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get recommendation statistics."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Count by status
    stats = {}
    for rec_status in RecommendationStatus:
        stmt = (
            select(func.count(PriceRecommendation.id))
            .where(PriceRecommendation.user_id == current_user.id)
            .where(PriceRecommendation.status == rec_status)
            .where(PriceRecommendation.created_at >= since)
        )
        result = await db.execute(stmt)
        stats[rec_status.value] = result.scalar() or 0
    
    # Calculate totals matching frontend interface
    total_generated = sum(stats.values())
    total_applied = stats.get("applied", 0)
    total_rejected = stats.get("rejected", 0)
    total_expired = stats.get("expired", 0)
    total_pending = stats.get("pending", 0)
    
    # Approval rate
    decided = total_applied + total_rejected
    approval_rate = (total_applied / decided * 100) if decided > 0 else 0
    
    # Average confidence
    stmt_conf = (
        select(func.avg(PriceRecommendation.confidence_score))
        .where(PriceRecommendation.user_id == current_user.id)
        .where(PriceRecommendation.created_at >= since)
    )
    result = await db.execute(stmt_conf)
    avg_confidence = result.scalar()
    
    # Average price change percent
    stmt_change = (
        select(func.avg(
            (PriceRecommendation.recommended_price - PriceRecommendation.current_price) 
            / PriceRecommendation.current_price * 100
        ))
        .where(PriceRecommendation.user_id == current_user.id)
        .where(PriceRecommendation.current_price > 0)
        .where(PriceRecommendation.created_at >= since)
    )
    result = await db.execute(stmt_change)
    avg_price_change = result.scalar()
    
    return {
        "total_generated": total_generated,
        "total_applied": total_applied,
        "total_rejected": total_rejected,
        "total_expired": total_expired,
        "total_pending": total_pending,
        "approval_rate": round(approval_rate, 1),
        "avg_confidence": round(float(avg_confidence), 2) if avg_confidence else None,
        "avg_price_change_percent": round(float(avg_price_change), 2) if avg_price_change else None,
    }

@router.get("/recommendations", response_model=PaginatedResponse[PriceRecommendationResponse])
async def list_recommendations(
    request: Request,
    status: Optional[RecommendationStatus] = Query(default=None),
    product_id: Optional[UUID] = Query(default=None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List price recommendations."""
    query = select(PriceRecommendation).where(
        PriceRecommendation.user_id == current_user.id
    )
    
    if status:
        query = query.where(PriceRecommendation.status == status)
    if product_id:
        query = query.where(PriceRecommendation.product_id == product_id)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    
    # Paginate
    query = query.order_by(PriceRecommendation.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    items = list(result.scalars().all())
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/recommendations/pending", response_model=PaginatedResponse[PriceRecommendationResponse])
async def list_pending_recommendations(
    request: Request,
    product_id: Optional[UUID] = Query(default=None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List pending recommendations (approval queue)."""
    query = select(PriceRecommendation).where(
        PriceRecommendation.user_id == current_user.id,
        PriceRecommendation.status == RecommendationStatus.PENDING,
    )
    
    if product_id:
        query = query.where(PriceRecommendation.product_id == product_id)
    
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()
    
    query = query.order_by(PriceRecommendation.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    
    result = await db.execute(query)
    items = list(result.scalars().all())
    total_pages = (total + pagination.page_size - 1) // pagination.page_size
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pages=total_pages,
    )


@router.get("/recommendations/{recommendation_id}", response_model=PriceRecommendationResponse)
async def get_recommendation(
    request: Request,
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a specific recommendation."""
    recommendation = await db.get(PriceRecommendation, recommendation_id)
    if not recommendation or recommendation.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return recommendation


@router.post("/recommendations/{recommendation_id}/approve", response_model=PriceRecommendationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def approve_recommendation(
    request: Request,
    recommendation_id: UUID,
    data: RecommendationApprove = None,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending recommendation."""
    service = ApprovalService(db)
    try:
        return await service.approve(recommendation_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recommendations/{recommendation_id}/reject", response_model=PriceRecommendationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def reject_recommendation(
    request: Request,
    recommendation_id: UUID,
    data: RecommendationReject,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Reject a pending recommendation."""
    service = ApprovalService(db)
    try:
        return await service.reject(recommendation_id, current_user.id, data.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recommendations/{recommendation_id}/apply", response_model=PriceRecommendationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def apply_recommendation(
    request: Request,
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Apply an approved recommendation (push price to e-commerce)."""
    service = ApprovalService(db)
    try:
        return await service.apply_price(recommendation_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    