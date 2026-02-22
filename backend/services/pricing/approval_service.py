"""
Approval Service - Core approval workflow and price application.

FIX (2025-01-07): Made auto_approve_and_apply() atomic - single commit at the end.
FIX (2025-01-25): Extracted e-commerce push to EcommercePushService.
FIX (2025-01-25): Now pushes to ALL active platforms, not just the first one.
FIX (2026-01-27): Fixed _check_daily_limit() bug - was returning False when no settings exist.
FIX (2026-01-27): Added clearer error messages for common failure scenarios.
FIX (2026-02-17): Wired intelligence environment feedback loop — record_merchant_decision()
                   called on apply_price(), auto_approve_and_apply(), and reject().
FIX (2026-02-21): Restored missing auto_approve_and_apply() method — was lost during
                   2026-02-17 modularization refactor. This caused all auto-approval
                   attempts to silently fail with AttributeError, leaving recommendations
                   stuck in PENDING status. See BUG-002/003 in audit report.
"""

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from models.product import Product
from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.price_history import PriceHistory, ChangeReason
from models.pricing_settings import PricingSettings

logger = logging.getLogger(__name__)


class ApprovalError(Exception):
    """Custom exception for approval failures with error codes."""
    
    def __init__(self, message: str, error_code: str = "APPROVAL_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class ApprovalService:
    """Handles recommendation approval, rejection, and price application."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def approve(
        self,
        recommendation_id: UUID,
        user_id: UUID,
        auto: bool = False
    ) -> PriceRecommendation:
        """
        Approve a recommendation (manual approval only).
        
        For auto-approval with immediate application, use auto_approve_and_apply() instead.
        
        NOTE: No outcome is recorded here. The decision isn't final until
        apply_price() runs — the price hasn't changed yet, so there's
        nothing to measure. Outcome is recorded when price is actually applied.
        """
        recommendation = await self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status != RecommendationStatus.PENDING:
            raise ApprovalError(
                f"Cannot approve recommendation with status: {recommendation.status}",
                "INVALID_STATUS"
            )
        
        if recommendation.valid_until < datetime.now(UTC):
            recommendation.status = RecommendationStatus.EXPIRED
            self.db.add(recommendation)
            await self.db.commit()
            raise ApprovalError(
                "This recommendation has expired. Please generate a new one.",
                "RECOMMENDATION_EXPIRED"
            )
        
        recommendation.status = (
            RecommendationStatus.AUTO_APPROVED if auto 
            else RecommendationStatus.APPROVED
        )
        recommendation.reviewed_by = user_id
        recommendation.reviewed_at = datetime.now(UTC)
        
        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)
        
        return recommendation
    
    async def reject(
        self,
        recommendation_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None
    ) -> PriceRecommendation:
        """Reject a recommendation."""
        recommendation = await self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status != RecommendationStatus.PENDING:
            raise ApprovalError(
                f"Cannot reject recommendation with status: {recommendation.status}",
                "INVALID_STATUS"
            )
        
        recommendation.status = RecommendationStatus.REJECTED
        recommendation.reviewed_by = user_id
        recommendation.reviewed_at = datetime.now(UTC)
        recommendation.rejection_reason = reason
        
        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)
        
        # ── Intelligence Environment: record rejection ──
        # No price change to measure, but we track the decision for
        # merchant pattern analysis → Strategist guardrail calibration.
        await self._record_decision(
            recommendation_id=recommendation.id,
            user_id=user_id,
            merchant_decision="rejected",
        )
        
        return recommendation
    
    async def apply_price(
        self,
        recommendation_id: UUID,
        user_id: UUID
    ) -> PriceRecommendation:
        """
        Apply an approved recommendation - update product and push to e-commerce.
        
        Use this for manually approved recommendations.
        For auto-approval flow, use auto_approve_and_apply() instead.
        """
        from services.pricing.ecommerce_push_service import EcommercePushService
        
        recommendation = await self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status not in [
            RecommendationStatus.APPROVED,
            RecommendationStatus.AUTO_APPROVED
        ]:
            raise ApprovalError(
                f"Cannot apply recommendation with status: {recommendation.status}",
                "INVALID_STATUS"
            )
        
        product = await self.db.get(Product, recommendation.product_id)
        if not product:
            raise ApprovalError("Product not found", "PRODUCT_NOT_FOUND")
        
        old_price = product.current_price
        
        # Update product price
        product.current_price = recommendation.recommended_price
        product.updated_at = datetime.now(UTC)
        self.db.add(product)
        
        # Create price history record
        history = PriceHistory(
            user_id=user_id,
            product_id=product.id,
            old_price=old_price,
            new_price=recommendation.recommended_price,
            change_percent=recommendation.change_percent,
            change_reason=ChangeReason.RECOMMENDATION_APPLIED.value,
            recommendation_id=recommendation.id,
        )
        self.db.add(history)
        
        # Push to e-commerce platform
        push_service = EcommercePushService(self.db)
        platform_result = await push_service.push_price(product)
        
        if not platform_result.get("success"):
            product.current_price = old_price
            self.db.add(product)
            await self.db.rollback()
            
            error_msg = platform_result.get("error", "Unknown error pushing to platform")
            error_code = platform_result.get("error_code", "PLATFORM_PUSH_FAILED")
            raise ApprovalError(error_msg, error_code)
        
        # Update recommendation status
        recommendation.status = RecommendationStatus.APPLIED
        recommendation.applied_at = datetime.now(UTC)
        recommendation.applied_to_platform = platform_result.get("platform")
        self.db.add(recommendation)
        
        await self.db.commit()
        await self.db.refresh(recommendation)
        
        # ── Intelligence Environment: record merchant decision ──
        # Price is now applied and pushed — record the outcome for
        # feedback loop measurement at 7d/14d/30d windows.
        await self._record_decision(
            recommendation_id=recommendation.id,
            user_id=user_id,
            merchant_decision="accepted",
            actual_price_set=recommendation.recommended_price,
        )
        
        return recommendation
    
    # ──────────────────────────────────────────────────────────────────────
    # AUTO-APPROVE AND APPLY (RESTORED 2026-02-21)
    # ──────────────────────────────────────────────────────────────────────
    # This method was lost during the 2026-02-17 modularization refactor.
    # Without it, all callers (AutoApprovalService.process_pending,
    # process_auto_approvals, _approval_endpoints, recommendation_service,
    # competitor_fallback) hit AttributeError, silently caught by their
    # try/except blocks. Recommendations stayed PENDING forever.
    # ──────────────────────────────────────────────────────────────────────

    async def auto_approve_and_apply(
        self,
        recommendation_id: UUID,
        user_id: UUID,
    ) -> PriceRecommendation:
        """
        Atomically auto-approve AND apply a recommendation.

        Single transaction: approve -> update price -> push to platform -> commit.
        If push fails, everything rolls back and recommendation stays PENDING.

        Called by:
          - AutoApprovalService.process_pending()
          - self.process_auto_approvals()
          - _approval_endpoints.py (manual "approve & apply" button)
          - recommendation_service.py (post-generation auto-apply)
          - competitor_fallback.py (fallback pricing auto-apply)
        """
        from services.pricing.ecommerce_push_service import EcommercePushService
        
        # Step 0: Check daily auto-approval limit FIRST
        allowed, reason = await self._check_daily_limit(user_id)
        if not allowed:
            raise ApprovalError(reason, "DAILY_LIMIT_REACHED")
        recommendation = await self._get_recommendation(recommendation_id, user_id)

        if recommendation.status != RecommendationStatus.PENDING:
            raise ApprovalError(
                f"Cannot auto-apply recommendation with status: {recommendation.status}",
                "INVALID_STATUS"
            )

        if recommendation.valid_until < datetime.now(UTC):
            recommendation.status = RecommendationStatus.EXPIRED
            self.db.add(recommendation)
            await self.db.commit()
            raise ApprovalError("Recommendation has expired", "RECOMMENDATION_EXPIRED")

        product = await self.db.get(Product, recommendation.product_id)
        if not product:
            raise ApprovalError("Product not found", "PRODUCT_NOT_FOUND")

        old_price = product.current_price

        # Step 1: Update product price (not committed yet)
        product.current_price = recommendation.recommended_price
        product.updated_at = datetime.now(UTC)
        self.db.add(product)

        # Step 2: Create price history record
        history = PriceHistory(
            user_id=user_id,
            product_id=product.id,
            old_price=old_price,
            new_price=recommendation.recommended_price,
            change_percent=recommendation.change_percent,
            change_reason=ChangeReason.AUTO_APPROVED.value
                if hasattr(ChangeReason, 'AUTO_APPROVED')
                else ChangeReason.RECOMMENDATION_APPLIED.value,
            recommendation_id=recommendation.id,
        )
        self.db.add(history)

        # Step 3: Push to ALL active e-commerce platforms
        push_service = EcommercePushService(self.db)
        platform_result = await push_service.push_price(product)

        # Step 4: Check push result BEFORE marking as Applied
        if not platform_result.get("success"):
            # CRITICAL: Revert price and rollback entire transaction
            product.current_price = old_price
            self.db.add(product)
            await self.db.rollback()

            error_msg = platform_result.get("error", "Unknown error pushing to platform")
            error_code = platform_result.get("error_code", "PLATFORM_PUSH_FAILED")
            logger.error(
                f"Auto-apply push failed for recommendation {recommendation_id}: "
                f"[{error_code}] {error_msg}"
            )
            raise ApprovalError(error_msg, error_code)

        # Step 5: Mark as Applied ONLY after successful push
        recommendation.status = RecommendationStatus.APPLIED
        recommendation.reviewed_at = datetime.now(UTC)
        recommendation.applied_at = datetime.now(UTC)
        recommendation.applied_to_platform = platform_result.get("platform")
        self.db.add(recommendation)

        # Step 6: Single atomic commit — price + history + status all together
        await self.db.commit()
        await self.db.refresh(recommendation)

        logger.info(
            f"Auto-approved and applied recommendation {recommendation_id}: "
            f"${old_price} -> ${recommendation.recommended_price} "
            f"on {platform_result.get('platform')}"
        )

        # Step 7: Record decision for intelligence environment feedback loop
        await self._record_decision(
            recommendation_id=recommendation.id,
            user_id=user_id,
            merchant_decision="auto_applied",
            actual_price_set=recommendation.recommended_price,
        )

        return recommendation

    async def process_auto_approvals(self, user_id: UUID) -> list[PriceRecommendation]:
        """
        Process all PENDING recommendations against user's auto-approval settings.
        
        Checks each pending recommendation's confidence score and change percent
        against the user's thresholds. Those that qualify are auto-approved and
        applied atomically.
        
        Returns:
            List of recommendations that were successfully auto-applied.
        """
        settings = await self._get_user_settings(user_id)
        
        if not settings or not settings.auto_approve_enabled:
            logger.info(f"Auto-approval disabled for user {user_id}")
            return []
        
        # Get all pending recommendations for this user
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until >= datetime.now(UTC))
        )
        result = await self.db.execute(stmt)
        pending = list(result.scalars().all())
        
        if not pending:
            logger.info(f"No pending recommendations for user {user_id}")
            return []
        
        applied: list[PriceRecommendation] = []
        
        for rec in pending:
            # Check confidence threshold
            if float(rec.confidence_score) < float(settings.auto_approve_min_confidence):
                logger.debug(
                    f"Skipping {rec.id}: confidence {rec.confidence_score} "
                    f"< threshold {settings.auto_approve_min_confidence}"
                )
                continue
            
            # Check change percent against increase/decrease limits
            change = float(rec.change_percent)
            if change > 0 and change > float(settings.auto_approve_max_increase):
                logger.debug(
                    f"Skipping {rec.id}: increase {change}% "
                    f"> max {settings.auto_approve_max_increase}%"
                )
                continue
            if change < 0 and abs(change) > float(settings.auto_approve_max_decrease):
                logger.debug(
                    f"Skipping {rec.id}: decrease {abs(change)}% "
                    f"> max {settings.auto_approve_max_decrease}%"
                )
                continue
            
            # Qualifies — try to auto-approve and apply
            try:
                result_rec = await self.auto_approve_and_apply(rec.id, user_id)
                applied.append(result_rec)
            except ApprovalError as e:
                # Log and skip — don't let one failure block the rest
                logger.warning(
                    f"Auto-approval failed for {rec.id}: [{e.error_code}] {e.message}"
                )
                continue
            except Exception as e:
                logger.exception(f"Unexpected error auto-approving {rec.id}")
                continue
        
        logger.info(
            f"Auto-approval complete for user {user_id}: "
            f"{len(applied)}/{len(pending)} applied"
        )
        return applied
    
    
    async def _get_recommendation(
        self,
        recommendation_id: UUID,
        user_id: UUID
    ) -> PriceRecommendation:
        """Get recommendation and verify ownership."""
        recommendation = await self.db.get(PriceRecommendation, recommendation_id)
        
        if not recommendation:
            raise ApprovalError("Recommendation not found", "NOT_FOUND")
        
        if recommendation.user_id != user_id:
            raise ApprovalError("Recommendation not found", "NOT_FOUND")
        
        return recommendation
    
    async def _get_user_settings(self, user_id: UUID) -> Optional[PricingSettings]:
        """Get user's pricing settings."""
        stmt = select(PricingSettings).where(PricingSettings.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def _check_daily_limit(self, user_id: UUID) -> tuple[bool, str]:
        """
        Check if user has reached daily auto-change limit.
        
        Returns:
            tuple[bool, str]: (is_within_limit, message)
            
        FIX (2026-01-27): Previously returned False when no settings exist,
        which blocked ALL approvals. Now returns True (no limit) in that case.
        """
        settings = await self._get_user_settings(user_id)
        
        # FIX: No settings means no limit configured - allow unlimited approvals
        if not settings:
            logger.debug(f"No pricing settings for user {user_id}, allowing unlimited approvals")
            return True, "OK"
        
        # If limit is 0 or negative, treat as unlimited
        if settings.max_auto_changes_per_day <= 0:
            return True, "OK"
        
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        
        stmt = (
            select(func.count(PriceRecommendation.id))
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.APPLIED)
            .where(PriceRecommendation.applied_at >= today_start)
        )
        result = await self.db.execute(stmt)
        count = result.scalar() or 0
        
        limit = settings.max_auto_changes_per_day
        
        if count >= limit:
            return False, f"Daily limit reached ({count}/{limit}). Go to Settings → Pricing to increase your limit."
        
        return True, "OK"
    
    async def get_approval_stats(self, user_id: UUID, days: int = 30) -> dict:
        """Get approval statistics for a user."""
        since = datetime.now(UTC) - timedelta(days=days)
        
        # Total recommendations
        stmt_total = (
            select(func.count(PriceRecommendation.id))
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.created_at >= since)
        )
        result = await self.db.execute(stmt_total)
        total = result.scalar() or 0
        
        # By status
        by_status: dict[str, int] = {}
        for status in RecommendationStatus:
            try:
                status_value = status.value if hasattr(status, 'value') else str(status)
                stmt = (
                    select(func.count(PriceRecommendation.id))
                    .where(PriceRecommendation.user_id == user_id)
                    .where(PriceRecommendation.status == status)
                    .where(PriceRecommendation.created_at >= since)
                )
                result = await self.db.execute(stmt)
                count = result.scalar() or 0
                by_status[status_value] = count
            except Exception:
                continue
        
        # Average confidence of applied
        stmt_conf = (
            select(func.avg(PriceRecommendation.confidence_score))
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.APPLIED)
            .where(PriceRecommendation.created_at >= since)
        )
        result = await self.db.execute(stmt_conf)
        avg_confidence = result.scalar()
        avg_confidence_applied: Optional[float] = float(avg_confidence) if avg_confidence else None
        
        # Auto vs manual ratio
        auto = by_status.get("AUTO_APPROVED", 0)
        manual = by_status.get("APPROVED", 0)
        auto_approval_ratio = float(auto) / float(auto + manual) if (auto + manual) > 0 else 0.0
        
        return {
            "total": total,
            "by_status": by_status,
            "avg_confidence_applied": avg_confidence_applied,
            "auto_approval_ratio": auto_approval_ratio,
        }
    
    # ──────────────────────────────────────────────
    # INTELLIGENCE ENVIRONMENT: FEEDBACK LOOP HOOK
    # ──────────────────────────────────────────────

    async def _record_decision(
        self,
        recommendation_id: UUID,
        user_id: UUID,
        merchant_decision: str,
        actual_price_set: Optional[Decimal] = None,
    ) -> None:
        """
        Fire-and-forget: record merchant decision for the intelligence
        environment feedback loop. Failures are logged, never raised.
        
        Uses lazy import (same pattern as EcommercePushService) to
        avoid circular imports.
        """
        try:
            from services.pricing.outcome_service import OutcomeService
            outcome_svc = OutcomeService(self.db)
            await outcome_svc.record_merchant_decision(
                recommendation_id=recommendation_id,
                user_id=user_id,
                merchant_decision=merchant_decision,
                actual_price_set=actual_price_set,
            )
        except Exception as e:
            logger.warning(
                f"Failed to record outcome for recommendation "
                f"{recommendation_id}: {e}"
            )



            