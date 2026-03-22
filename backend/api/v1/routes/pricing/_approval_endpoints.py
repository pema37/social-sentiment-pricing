# backend/api/v1/routes/pricing/_approval_endpoints.py
"""
Approval workflow endpoints: approve, reject, apply.
These are write operations that modify recommendation status and push prices.

FIX (2026-01-27): Added structured error responses with error codes and
user-friendly messages for better UX.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from core.rate_limit import ANALYSIS_RATE_LIMIT, WRITE_RATE_LIMIT, limiter
from db.session import get_session
from models.user import User
from schemas.pricing import (
    PriceRecommendationResponse,
    RecommendationApprove,
    RecommendationReject,
)
from services.pricing.approval_service import ApprovalError, ApprovalService

from ._helpers import approval_error_to_http

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/recommendations/{recommendation_id}/approve", response_model=PriceRecommendationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def approve_recommendation(
    request: Request,
    recommendation_id: UUID,
    data: RecommendationApprove = None,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Approve a pending recommendation AND apply the price change.

    This is an atomic operation - either both approval and price push succeed,
    or everything is rolled back.

    Possible error codes:
    - DAILY_LIMIT_REACHED: User hit their daily approval limit
    - NO_ACTIVE_INTEGRATION_LINK: Product not linked to any store
    - PLATFORM_PUSH_FAILED: Store API returned an error
    - RECOMMENDATION_EXPIRED: Recommendation is past its valid_until date
    - INVALID_STATUS: Recommendation is not in PENDING status
    - NOT_FOUND: Recommendation doesn't exist or belongs to another user
    """
    service = ApprovalService(db)

    try:
        # Use atomic auto_approve_and_apply for single-commit behavior
        recommendation = await service.auto_approve_and_apply(recommendation_id, current_user.id)
        logger.info(f"Recommendation {recommendation_id} approved and applied by user {current_user.id}")
        return recommendation

    except ApprovalError as e:
        logger.warning(f"Approval failed for {recommendation_id}: [{e.error_code}] {e.message}")
        raise approval_error_to_http(e)

    except ValueError as e:
        # Legacy error handling (should not hit this path anymore)
        error_msg = str(e)
        logger.warning(f"Approval failed for {recommendation_id}: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)


@router.post("/recommendations/{recommendation_id}/reject", response_model=PriceRecommendationResponse)
@limiter.limit(WRITE_RATE_LIMIT)
async def reject_recommendation(
    request: Request,
    recommendation_id: UUID,
    data: RecommendationReject,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Reject a pending recommendation.

    Requires a reason for rejection which is stored for analytics.
    """
    service = ApprovalService(db)

    try:
        recommendation = await service.reject(recommendation_id, current_user.id, data.reason)
        logger.info(f"Recommendation {recommendation_id} rejected by user {current_user.id}: {data.reason}")
        return recommendation

    except ApprovalError as e:
        raise approval_error_to_http(e)

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
    """
    Apply an already-approved recommendation (push price to e-commerce).

    Note: The /approve endpoint now auto-applies, so this endpoint is mainly
    for edge cases where a recommendation was approved but not applied.
    """
    service = ApprovalService(db)

    try:
        recommendation = await service.apply_price(recommendation_id, current_user.id)
        logger.info(f"Recommendation {recommendation_id} applied by user {current_user.id}")
        return recommendation

    except ApprovalError as e:
        raise approval_error_to_http(e)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/recommendations/process-auto-approvals")
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def process_auto_approvals(
    request: Request,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Process all existing PENDING recommendations for auto-approval.

    This checks each pending recommendation against the user's auto-approval
    settings (confidence threshold, max change percent) and auto-applies
    those that qualify.
    """
    service = ApprovalService(db)

    try:
        applied = await service.process_auto_approvals(current_user.id)

        results = []
        for rec in applied:
            results.append(
                {
                    "recommendation_id": str(rec.id),
                    "product_id": str(rec.product_id),
                    "status": rec.status.value if hasattr(rec.status, "value") else rec.status,
                    "recommended_price": str(rec.recommended_price),
                    "change_percent": str(rec.change_percent),
                }
            )

        failures = service.last_auto_approval_failures
        logger.info(
            f"Auto-approval processed {len(applied)} recommendations "
            f"({len(failures)} failed) for user {current_user.id}"
        )

        return {
            "message": f"Applied {len(applied)} recommendations",
            "applied_count": len(applied),
            "failed_count": len(failures),
            "results": results,
            "failures": failures,
        }

    except Exception as e:
        logger.error(f"Auto-approval failed for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
