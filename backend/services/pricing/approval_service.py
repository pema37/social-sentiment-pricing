# backend/services/pricing/approval_service.py
"""
Approval Service - Core approval workflow and price application.

FIX (2025-01-07): Made auto_approve_and_apply() atomic - single commit at the end.
FIX (2025-01-25): Extracted e-commerce push to EcommercePushService.
FIX (2025-01-25): Now pushes to ALL active platforms, not just the first one.
FIX (2026-01-27): Fixed _check_daily_limit() bug - was returning False when no settings exist.
FIX (2026-01-27): Added clearer error messages for common failure scenarios.
"""

from datetime import datetime, timedelta
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
        """
        recommendation = await self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status != RecommendationStatus.PENDING:
            raise ApprovalError(
                f"Cannot approve recommendation with status: {recommendation.status}",
                "INVALID_STATUS"
            )
        
        if recommendation.valid_until < datetime.utcnow():
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
        recommendation.reviewed_at = datetime.utcnow()
        
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
        recommendation.reviewed_at = datetime.utcnow()
        recommendation.rejection_reason = reason
        
        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)
        
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
        product.updated_at = datetime.utcnow()
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
        recommendation.applied_at = datetime.utcnow()
        recommendation.applied_to_platform = platform_result.get("platform")
        self.db.add(recommendation)
        
        await self.db.commit()
        await self.db.refresh(recommendation)
        
        return recommendation
    
    async def auto_approve_and_apply(
        self,
        recommendation_id: UUID,
        user_id: UUID
    ) -> PriceRecommendation:
        """
        Auto-approve and immediately apply a recommendation - ATOMIC TRANSACTION.
        
        Ensures either:
        - Both approval AND price push succeed (commit once at the end)
        - OR everything is rolled back (nothing committed)
        """
        from services.pricing.ecommerce_push_service import EcommercePushService
        
        # Check daily limit first
        limit_ok, limit_msg = await self._check_daily_limit(user_id)
        if not limit_ok:
            raise ApprovalError(limit_msg, "DAILY_LIMIT_REACHED")
        
        recommendation = await self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status != RecommendationStatus.PENDING:
            raise ApprovalError(
                f"Cannot approve: recommendation status is '{recommendation.status}', expected 'PENDING'",
                "INVALID_STATUS"
            )
        
        if recommendation.valid_until < datetime.utcnow():
            recommendation.status = RecommendationStatus.EXPIRED
            self.db.add(recommendation)
            await self.db.commit()
            raise ApprovalError(
                "This recommendation has expired. Please generate a new one.",
                "RECOMMENDATION_EXPIRED"
            )
        
        product = await self.db.get(Product, recommendation.product_id)
        if not product:
            raise ApprovalError("Product not found", "PRODUCT_NOT_FOUND")
        
        old_price = product.current_price
        
        # ═══════════════════════════════════════════════════════════════════════
        # ATOMIC TRANSACTION - ALL CHANGES, SINGLE COMMIT
        # ═══════════════════════════════════════════════════════════════════════
        
        # Step 1: Update product price (not committed yet)
        product.current_price = recommendation.recommended_price
        product.updated_at = datetime.utcnow()
        self.db.add(product)
        
        # Step 2: Push to e-commerce BEFORE committing
        push_service = EcommercePushService(self.db)
        platform_result = await push_service.push_price(product)
        
        if not platform_result.get("success"):
            product.current_price = old_price
            await self.db.rollback()
            
            error_msg = platform_result.get("error", "Unknown error")
            error_code = platform_result.get("error_code", "PLATFORM_PUSH_FAILED")
            logger.warning(
                f"Auto-apply failed for recommendation {recommendation_id}: "
                f"[{error_code}] {error_msg}"
            )
            
            # Provide helpful message based on error type
            if error_code == "NO_ACTIVE_INTEGRATION_LINK":
                raise ApprovalError(
                    "This product isn't linked to your store. Go to Integrations → Sync Products to link it.",
                    error_code
                )
            raise ApprovalError(f"Failed to push price to platform: {error_msg}", error_code)
        
        # Step 3: Create price history
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
        
        # Step 4: Update recommendation - go straight to APPLIED
        recommendation.status = RecommendationStatus.APPLIED
        recommendation.reviewed_by = user_id
        recommendation.reviewed_at = datetime.utcnow()
        recommendation.applied_at = datetime.utcnow()
        recommendation.applied_to_platform = platform_result.get("platform")
        self.db.add(recommendation)
        
        # Step 5: SINGLE COMMIT
        await self.db.commit()
        await self.db.refresh(recommendation)
        
        logger.info(
            f"Auto-applied recommendation {recommendation_id}: "
            f"${old_price} -> ${recommendation.recommended_price} "
            f"(pushed to {platform_result.get('platform')})"
        )
        
        return recommendation
    
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
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
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
        since = datetime.utcnow() - timedelta(days=days)
        
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
    

    