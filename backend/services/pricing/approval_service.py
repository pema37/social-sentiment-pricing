# backend/services/pricing/approval_service.py
"""
Approval Service - Handles approval workflow and price application.

FIX APPLIED: Replaced all datetime.now(timezone.utc) with datetime.utcnow()
to fix PostgreSQL TIMESTAMP WITHOUT TIME ZONE compatibility issues.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from models.product import Product
from models.pricing_rule import PricingRule
from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.price_history import PriceHistory, ChangeReason
from models.pricing_settings import PricingSettings
from models.integration import Integration, ProductIntegrationLink, IntegrationStatus


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
        """Approve a recommendation."""
        
        recommendation = await self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status != RecommendationStatus.PENDING:
            raise ValueError(f"Cannot approve recommendation with status: {recommendation.status}")
        
        # Compare naive datetimes (DB stores without timezone)
        if recommendation.valid_until < datetime.utcnow():
            recommendation.status = RecommendationStatus.EXPIRED
            self.db.add(recommendation)
            await self.db.commit()
            raise ValueError("Recommendation has expired")
        
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
            raise ValueError(f"Cannot reject recommendation with status: {recommendation.status}")
        
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
        """Apply an approved recommendation - update product and push to e-commerce."""
        
        recommendation = await self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status not in [
            RecommendationStatus.APPROVED,
            RecommendationStatus.AUTO_APPROVED
        ]:
            raise ValueError(f"Cannot apply recommendation with status: {recommendation.status}")
        
        # Get product
        product = await self.db.get(Product, recommendation.product_id)
        if not product:
            raise ValueError("Product not found")
        
        # Store old price
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
        platform_result = await self._push_to_ecommerce(product, user_id)
        
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
        recommendation: PriceRecommendation,
        user_id: UUID
    ) -> PriceRecommendation:
        """Auto-approve and immediately apply a recommendation."""
        
        # Check daily limit
        if not await self._check_daily_limit(user_id):
            return recommendation  # Leave as pending
        
        # Approve
        recommendation = await self.approve(recommendation.id, user_id, auto=True)
        
        # Apply
        recommendation = await self.apply_price(recommendation.id, user_id)
        
        return recommendation
    
    async def process_auto_approvals(self, user_id: UUID) -> list[PriceRecommendation]:
        """Process all pending recommendations eligible for auto-approval."""
        
        settings = await self._get_user_settings(user_id)
        if not settings or not settings.auto_approve_enabled:
            return []
        
        # Check blackout hours
        if self._in_blackout_period(settings):
            return []
        
        # Get pending recommendations that don't require approval
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.requires_approval == False)
            .where(PriceRecommendation.valid_until > datetime.utcnow())
        )
        
        result = await self.db.execute(stmt)
        pending = list(result.scalars().all())
        applied: list[PriceRecommendation] = []
        
        for recommendation in pending:
            if not await self._check_daily_limit(user_id):
                break  # Hit daily limit
            
            try:
                result_rec = await self.auto_approve_and_apply(recommendation, user_id)
                applied.append(result_rec)
            except Exception:
                continue  # Skip failed ones
        
        return applied
    
    async def _get_recommendation(
        self,
        recommendation_id: UUID,
        user_id: UUID
    ) -> PriceRecommendation:
        """Get recommendation and verify ownership."""
        
        recommendation = await self.db.get(PriceRecommendation, recommendation_id)
        
        if not recommendation:
            raise ValueError("Recommendation not found")
        
        if recommendation.user_id != user_id:
            raise ValueError("Recommendation not found")
        
        return recommendation
    
    async def _get_user_settings(self, user_id: UUID) -> Optional[PricingSettings]:
        """Get user's pricing settings."""
        stmt = select(PricingSettings).where(PricingSettings.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    async def _check_daily_limit(self, user_id: UUID) -> bool:
        """Check if user has reached daily auto-change limit."""
        
        settings = await self._get_user_settings(user_id)
        if not settings:
            return False
        
        # Count today's auto-applied recommendations
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        stmt = (
            select(func.count(PriceRecommendation.id))
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.AUTO_APPROVED)
            .where(PriceRecommendation.applied_at >= today_start)
        )
        
        result = await self.db.execute(stmt)
        count = result.scalar() or 0
        
        return count < settings.max_auto_changes_per_day
    
    def _in_blackout_period(self, settings: PricingSettings) -> bool:
        """Check if current time is in blackout period."""
        
        if settings.blackout_hours_start is None or settings.blackout_hours_end is None:
            return False
        
        current_hour = datetime.utcnow().hour
        
        start = settings.blackout_hours_start
        end = settings.blackout_hours_end
        
        # Handle overnight blackouts (e.g., 22:00 - 06:00)
        if start > end:
            return current_hour >= start or current_hour < end
        else:
            return start <= current_hour < end
    
    async def _push_to_ecommerce(self, product: Product, user_id: UUID) -> dict:
        """Push price update to connected e-commerce platform."""
        from core.encryption import decrypt_token
        from services.integration.shopify_service import ShopifyService
        from services.integration.woocommerce_service import WooCommerceService
        from services.integration.base import PriceUpdateRequest, PriceUpdateResult
        
        try:
            # Get product integration link
            stmt = (
                select(ProductIntegrationLink)
                .where(ProductIntegrationLink.product_id == product.id)
                .where(ProductIntegrationLink.sync_enabled == True)
            )
            result = await self.db.execute(stmt)
            link = result.scalars().first()
            
            if not link:
                return {"platform": None, "success": False, "error": "Product not linked to any platform"}
            
            # Get the integration
            integration = await self.db.get(Integration, link.integration_id)
            
            if not integration:
                return {"platform": None, "success": False, "error": "Integration not found"}
            
            if integration.status != IntegrationStatus.ACTIVE:
                return {"platform": integration.platform.value, "success": False, "error": f"Integration status: {integration.status.value}"}
            
            # Decrypt access token
            try:
                access_token = decrypt_token(integration.access_token_encrypted)
            except Exception as e:
                return {"platform": integration.platform.value, "success": False, "error": f"Failed to decrypt token: {str(e)}"}
            
            # Build price update request
            request = PriceUpdateRequest(
                external_product_id=link.external_product_id,
                external_variant_id=link.external_variant_id,
                new_price=float(product.current_price),
            )
            
            # Call appropriate service
            if integration.platform.value == "shopify":
                service = ShopifyService()
                response = await service.update_price(
                    store_url=integration.store_url,
                    access_token=access_token,
                    request=request
                )
            elif integration.platform.value == "woocommerce":
                service = WooCommerceService()
                response = await service.update_price(
                    store_url=integration.store_url,
                    access_token=access_token,
                    request=request
                )
            else:
                return {"platform": integration.platform.value, "success": False, "error": "Unsupported platform"}
            
            # Update link metadata
            if response.result == PriceUpdateResult.SUCCESS:
                link.last_price_push_at = datetime.utcnow()
                link.external_price = float(product.current_price)
                link.updated_at = datetime.utcnow()
                self.db.add(link)
            
            return {
                "platform": integration.platform.value,
                "success": response.result == PriceUpdateResult.SUCCESS,
                "external_id": link.external_product_id,
                "new_price": float(product.current_price),
                "old_price": response.old_price,
                "error": response.error,
            }
            
        except Exception as e:
            return {"platform": None, "success": False, "error": str(e)}
    
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
        
        # By status - build dict with all status values
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
                # Skip problematic status values
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
        avg_confidence_applied: Optional[float] = None
        if avg_confidence is not None:
            avg_confidence_applied = float(avg_confidence)
        
        # Auto vs manual approval ratio
        auto = by_status.get("auto_approved", 0)
        manual = by_status.get("approved", 0)
        auto_approval_ratio: float = 0.0
        if (auto + manual) > 0:
            auto_approval_ratio = float(auto) / float(auto + manual)
        
        return {
            "total": total,
            "by_status": by_status,
            "avg_confidence_applied": avg_confidence_applied,
            "auto_approval_ratio": auto_approval_ratio,
        }
    

    