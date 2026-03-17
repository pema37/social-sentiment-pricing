"""
Auto-Approval Service - Handles automatic approval processing.

Processes pending recommendations that meet auto-approval criteria.

FIX (2026-01-28) Bug #2: Use SettingsService.get_or_create() instead of
direct SELECT to ensure default settings exist for new users. Previously,
new users without a PricingSettings row would never get auto-approvals.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import func, select

from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.pricing_settings import PricingSettings

logger = logging.getLogger(__name__)


class AutoApprovalService:
    """Handles auto-approval eligibility and batch processing."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_pending(self, user_id: UUID) -> list[PriceRecommendation]:
        """
        Process all pending recommendations eligible for auto-approval.

        Re-evaluates eligibility based on current settings.
        Uses atomic auto_approve_and_apply() so failures don't leave
        recommendations stuck in intermediate states.
        """
        from services.pricing.approval_service import ApprovalService
        from services.pricing.settings_service import SettingsService

        # =====================================================================
        # BUGFIX (2026-01-28): Use get_or_create() to ensure settings exist
        # =====================================================================
        # Previously used self._get_settings() which returned None for new users,
        # causing auto-approval to silently skip all recommendations.
        # Now uses SettingsService.get_or_create() which creates default settings
        # (auto_approve_enabled=True) for new users.
        # =====================================================================
        settings_service = SettingsService(self.db)
        settings = await settings_service.get_or_create(user_id)

        if not settings.auto_approve_enabled:
            logger.info(f"Auto-approve explicitly disabled for user {user_id}")
            return []

        # Extract settings values upfront (avoid lazy loading issues)
        max_increase = float(settings.auto_approve_max_increase)
        max_decrease = float(settings.auto_approve_max_decrease)
        min_confidence = float(settings.auto_approve_min_confidence)
        require_above_price = (
            float(settings.require_approval_above_price) if settings.require_approval_above_price else None
        )

        # Check blackout hours
        if self._in_blackout_period(settings):
            logger.info(f"In blackout period for user {user_id}")
            return []

        # Get ALL pending recommendations
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until > datetime.now(UTC))
        )
        result = await self.db.execute(stmt)
        pending = list(result.scalars().all())

        logger.info(f"Found {len(pending)} pending recommendations for user {user_id}")

        if not pending:
            return []

        # Extract recommendation data upfront to avoid greenlet issues
        recommendations_data = [
            {
                "id": rec.id,
                "change_percent": float(rec.change_percent),
                "confidence_score": float(rec.confidence_score),
                "current_price": float(rec.current_price),
            }
            for rec in pending
        ]

        applied: list[PriceRecommendation] = []
        approval_service = ApprovalService(self.db)

        for rec_data in recommendations_data:
            rec_id = rec_data["id"]

            # Check daily limit
            if not await self._check_daily_limit(user_id, settings):
                logger.info(f"Hit daily limit for user {user_id}")
                break

            # Check eligibility
            if not self._is_eligible(rec_data, max_increase, max_decrease, min_confidence, require_above_price):
                logger.debug(
                    f"Recommendation {rec_id} not eligible: "
                    f"change={rec_data['change_percent']:.1f}%, "
                    f"conf={rec_data['confidence_score']:.2f}"
                )
                continue

            try:
                # Use atomic auto_approve_and_apply
                result_rec = await approval_service.auto_approve_and_apply(rec_id, user_id)
                applied.append(result_rec)
                logger.info(f"Auto-applied recommendation {rec_id}")
            except Exception as e:
                # Recommendation stays PENDING, can be retried later
                logger.warning(f"Failed to auto-apply recommendation {rec_id}: {e}")
                continue

        logger.info(f"Auto-applied {len(applied)} of {len(pending)} recommendations for user {user_id}")
        return applied

    def _is_eligible(
        self,
        rec_data: dict,
        max_increase: float,
        max_decrease: float,
        min_confidence: float,
        require_above_price: float | None,
    ) -> bool:
        """
        Check if a recommendation is eligible for auto-approval.

        Uses plain Python values to avoid ORM lazy loading issues.
        """
        change_percent = rec_data["change_percent"]
        confidence_score = rec_data["confidence_score"]
        current_price = rec_data["current_price"]

        # Check confidence threshold
        if confidence_score < min_confidence:
            return False

        # Check increase threshold
        if change_percent > 0 and change_percent > max_increase:
            return False

        # Check decrease threshold
        if change_percent < 0 and abs(change_percent) > max_decrease:
            return False

        # Check high-value product threshold
        if require_above_price is not None:
            if current_price > require_above_price:
                return False

        return True

    async def _check_daily_limit(self, user_id: UUID, settings: PricingSettings) -> bool:
        """Check if user has reached daily auto-change limit."""
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
        within_limit = count < limit

        if not within_limit:
            logger.debug(f"User {user_id} at daily limit: {count}/{limit}")

        return within_limit

    def _in_blackout_period(self, settings: PricingSettings) -> bool:
        """Check if current time is in blackout period."""
        if settings.blackout_hours_start is None or settings.blackout_hours_end is None:
            return False

        current_hour = datetime.now(UTC).hour
        start = settings.blackout_hours_start
        end = settings.blackout_hours_end

        # Handle overnight blackouts (e.g., 22:00 - 06:00)
        if start > end:
            return current_hour >= start or current_hour < end
        else:
            return start <= current_hour < end
