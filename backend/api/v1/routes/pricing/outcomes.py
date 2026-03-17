# backend/api/v1/routes/pricing/outcomes.py
"""
Outcome tracking & intelligence environment endpoints.

Mounted at: /api/v1/outcomes (via main.py prefix)
All paths below are relative to that prefix.

Wires services to HTTP surface:
  - OutcomeService             → record, list, detail, accuracy, rule perf
  - OutcomeCalibrationService  → confidence calibration, elasticity, merchant patterns
  - OutcomeBenchmarkService    → category benchmarks, data gap failure rates
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.deps import get_current_user
from core.rate_limit import WRITE_RATE_LIMIT, limiter
from db.session import get_session
from models.price_recommendation import PriceRecommendation
from models.recommendation_outcome import OutcomeLabel, RecommendationOutcome
from models.user import User
from schemas.common import PaginatedResponse, PaginationParams
from schemas.pricing import (
    AccuracyStatsResponse,
    OutcomeRecordRequest,
    OutcomeResponse,
    RulePerformanceResponse,
)
from services.pricing.outcome_benchmarks import OutcomeBenchmarkService
from services.pricing.outcome_calibration import OutcomeCalibrationService
from services.pricing.outcome_service import OutcomeService

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# CORE OUTCOME CRUD
# ═══════════════════════════════════════════════════════════════


@router.post("/{recommendation_id}/record", response_model=OutcomeResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def record_outcome(
    request: Request,
    recommendation_id: UUID,
    data: OutcomeRecordRequest,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Record the outcome/performance of an applied recommendation."""
    service = OutcomeService(db)

    try:
        return await service.record_outcome(
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


@router.get("/", response_model=PaginatedResponse[OutcomeResponse])
async def list_outcomes(
    request: Request,
    product_id: UUID | None = Query(default=None),
    rule_id: UUID | None = Query(default=None),
    outcome_label: OutcomeLabel | None = Query(default=None),
    days: int = Query(default=30, le=365),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List recommendation outcomes."""
    cutoff = datetime.now(UTC) - timedelta(days=days)

    query = (
        select(RecommendationOutcome)
        .join(PriceRecommendation)
        .where(PriceRecommendation.user_id == current_user.id)
        .where(RecommendationOutcome.measured_at >= cutoff)
    )

    if product_id:
        query = query.where(PriceRecommendation.product_id == product_id)
    if rule_id:
        query = query.where(PriceRecommendation.rule_id == rule_id)
    if outcome_label:
        query = query.where(RecommendationOutcome.outcome_label == outcome_label)

    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    query = query.order_by(RecommendationOutcome.measured_at.desc())
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


# ═══════════════════════════════════════════════════════════════
# ANALYTICS: Accuracy & Rule Performance
#
# IMPORTANT: All static paths (/accuracy, /calibration, etc.)
# must be defined BEFORE /{outcome_id} or FastAPI will try
# to parse "accuracy" as a UUID and return 422.
# ═══════════════════════════════════════════════════════════════


@router.get("/accuracy", response_model=AccuracyStatsResponse)
async def get_accuracy_stats(
    request: Request,
    days: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get overall accuracy statistics for recommendations."""
    service = OutcomeService(db)
    return await service.get_accuracy_stats(current_user.id, days)


@router.get("/rules/{rule_id}/performance", response_model=RulePerformanceResponse)
async def get_rule_performance(
    request: Request,
    rule_id: UUID,
    days: int = Query(default=90, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get performance statistics for a specific pricing rule."""
    service = OutcomeService(db)

    try:
        return await service.get_rule_performance(rule_id, current_user.id, days)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# INTELLIGENCE ENVIRONMENT — CALIBRATION
# ═══════════════════════════════════════════════════════════════


@router.get("/calibration")
async def get_confidence_calibration(
    request: Request,
    product_category: str | None = Query(default=None),
    days: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Confidence calibration: predicted confidence vs actual outcome lift.

    Target: Pearson r > 0.7 by Month 12.
    """
    service = OutcomeCalibrationService(db)
    return await service.get_confidence_calibration(
        user_id=current_user.id,
        product_category=product_category,
        days=days,
    )


@router.get("/elasticity-accuracy")
async def get_elasticity_accuracy(
    request: Request,
    product_category: str | None = Query(default=None),
    days: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Compare predicted elasticity estimates with observed demand changes.

    When the Analyst consistently overestimates demand sensitivity,
    the category prior is updated via Bayesian posterior.
    """
    service = OutcomeCalibrationService(db)
    return await service.get_elasticity_accuracy(
        user_id=current_user.id,
        product_category=product_category,
        days=days,
    )


@router.get("/merchant-patterns")
async def get_merchant_patterns(
    request: Request,
    product_category: str | None = Query(default=None),
    days: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Merchant modification patterns.

    If merchants consistently reduce 10% suggestions to 5%, the
    Strategist learns to recommend smaller changes (preference prior).
    """
    service = OutcomeCalibrationService(db)
    return await service.get_merchant_modification_pattern(
        user_id=current_user.id,
        product_category=product_category,
        days=days,
    )


# ═══════════════════════════════════════════════════════════════
# INTELLIGENCE ENVIRONMENT — BENCHMARKS
# ═══════════════════════════════════════════════════════════════


@router.get("/benchmarks/{category}")
async def get_category_benchmarks(
    request: Request,
    category: str,
    days: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Cross-merchant category benchmarks (k-anonymity >= 5).

    Returns optimal price change ranges and success rates
    for a product category, aggregated across merchants.
    """
    service = OutcomeBenchmarkService(db)
    result = await service.get_category_benchmarks(
        product_category=category,
        days=days,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient data for category benchmarks. "
            "Requires 5+ merchants with outcome data in this category.",
        )

    return result


@router.get("/data-gaps")
async def get_data_gaps(
    request: Request,
    days: int = Query(default=90, ge=1, le=365),
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Data gap failure rates by category.

    Categories where low data_completeness correlates with failures.
    Tells Scout where to prioritize broader competitor coverage.
    """
    service = OutcomeBenchmarkService(db)
    return await service.get_data_gap_failure_rates(
        user_id=current_user.id,
        days=days,
    )


# ═══════════════════════════════════════════════════════════════
# OUTCOME DETAIL (must be LAST — /{outcome_id} catches all paths)
# ═══════════════════════════════════════════════════════════════


@router.get("/{outcome_id}", response_model=OutcomeResponse)
async def get_outcome_detail(
    request: Request,
    outcome_id: UUID,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get a single outcome by ID."""
    service = OutcomeService(db)
    outcome = await service.get_outcome_by_id(
        outcome_id=outcome_id,
        user_id=current_user.id,
    )
    if outcome is None:
        raise HTTPException(status_code=404, detail="Outcome not found")
    return outcome
