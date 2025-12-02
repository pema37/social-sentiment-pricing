# backend/services/pricing/approval_service.py
"""
Approval Service - Handles approval workflow and price application.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select, func

from backend.models.product import Product
from backend.models.pricing_rule import PricingRule
from backend.models.price_recommendation import PriceRecommendation, RecommendationStatus
from backend.models.price_history import PriceHistory
from backend.models.pricing_settings import PricingSettings
from backend.models.integration import Integration, ProductIntegrationLink, IntegrationStatus


class ApprovalService:
    """Handles recommendation approval, rejection, and price application."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def approve(
        self,
        recommendation_id: UUID,
        user_id: UUID,
        auto: bool = False
    ) -> PriceRecommendation:
        """Approve a recommendation."""
        
        recommendation = self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status != RecommendationStatus.PENDING:
            raise ValueError(f"Cannot approve recommendation with status: {recommendation.status}")
        
        # Handle timezone-naive datetime from DB
        valid_until = recommendation.valid_until
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        
        if valid_until < datetime.now(timezone.utc):
            recommendation.status = RecommendationStatus.EXPIRED
            self.db.add(recommendation)
            self.db.commit()
            raise ValueError("Recommendation has expired")
        
        recommendation.status = (
            RecommendationStatus.AUTO_APPROVED if auto 
            else RecommendationStatus.APPROVED
        )
        recommendation.reviewed_by = user_id
        recommendation.reviewed_at = datetime.now(timezone.utc)
        
        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(recommendation)
        
        return recommendation
    
    def reject(
        self,
        recommendation_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None
    ) -> PriceRecommendation:
        """Reject a recommendation."""
        
        recommendation = self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status != RecommendationStatus.PENDING:
            raise ValueError(f"Cannot reject recommendation with status: {recommendation.status}")
        
        recommendation.status = RecommendationStatus.REJECTED
        recommendation.reviewed_by = user_id
        recommendation.reviewed_at = datetime.now(timezone.utc)
        recommendation.rejection_reason = reason
        
        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(recommendation)
        
        return recommendation
    
    def apply_price(
        self,
        recommendation_id: UUID,
        user_id: UUID
    ) -> PriceRecommendation:
        """Apply an approved recommendation - update product and push to e-commerce."""
        
        recommendation = self._get_recommendation(recommendation_id, user_id)
        
        if recommendation.status not in [
            RecommendationStatus.APPROVED,
            RecommendationStatus.AUTO_APPROVED
        ]:
            raise ValueError(f"Cannot apply recommendation with status: {recommendation.status}")
        
        # Get product
        product = self.db.get(Product, recommendation.product_id)
        if not product:
            raise ValueError("Product not found")
        
        # Store old price
        old_price = product.current_price
        
        # Update product price
        product.current_price = recommendation.recommended_price
        product.updated_at = datetime.now(timezone.utc)
        self.db.add(product)
        
        # Create price history record
        history = PriceHistory(
            user_id=user_id,
            product_id=product.id,
            old_price=old_price,
            new_price=recommendation.recommended_price,
            change_percent=recommendation.change_percent,
            change_reason="recommendation_applied",
            recommendation_id=recommendation.id,
        )
        self.db.add(history)
        
        # Push to e-commerce platform
        platform_result = self._push_to_ecommerce_sync(product, user_id)
        
        # Update recommendation status
        recommendation.status = RecommendationStatus.APPLIED
        recommendation.applied_at = datetime.now(timezone.utc)
        recommendation.applied_to_platform = platform_result.get("platform")
        self.db.add(recommendation)
        
        self.db.commit()
        self.db.refresh(recommendation)
        
        return recommendation
    
    def auto_approve_and_apply(
        self,
        recommendation: PriceRecommendation,
        user_id: UUID
    ) -> PriceRecommendation:
        """Auto-approve and immediately apply a recommendation."""
        
        # Check daily limit
        if not self._check_daily_limit(user_id):
            return recommendation  # Leave as pending
        
        # Approve
        recommendation = self.approve(recommendation.id, user_id, auto=True)
        
        # Apply
        recommendation = self.apply_price(recommendation.id, user_id)
        
        return recommendation
    
    def process_auto_approvals(self, user_id: UUID) -> list[PriceRecommendation]:
        """Process all pending recommendations eligible for auto-approval."""
        
        settings = self._get_user_settings(user_id)
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
            .where(PriceRecommendation.valid_until > datetime.now(timezone.utc))
        )
        
        pending = list(self.db.exec(stmt).all())
        applied = []
        
        for recommendation in pending:
            if not self._check_daily_limit(user_id):
                break  # Hit daily limit
            
            try:
                result = self.auto_approve_and_apply(recommendation, user_id)
                applied.append(result)
            except Exception:
                continue  # Skip failed ones
        
        return applied
    
    def _get_recommendation(
        self,
        recommendation_id: UUID,
        user_id: UUID
    ) -> PriceRecommendation:
        """Get recommendation and verify ownership."""
        
        recommendation = self.db.get(PriceRecommendation, recommendation_id)
        
        if not recommendation:
            raise ValueError("Recommendation not found")
        
        if recommendation.user_id != user_id:
            raise ValueError("Recommendation not found")
        
        return recommendation
    
    def _get_user_settings(self, user_id: UUID) -> Optional[PricingSettings]:
        """Get user's pricing settings."""
        stmt = select(PricingSettings).where(PricingSettings.user_id == user_id)
        return self.db.exec(stmt).first()
    
    def _check_daily_limit(self, user_id: UUID) -> bool:
        """Check if user has reached daily auto-change limit."""
        
        settings = self._get_user_settings(user_id)
        if not settings:
            return False
        
        # Count today's auto-applied recommendations
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        stmt = (
            select(func.count(PriceRecommendation.id))
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.AUTO_APPROVED)
            .where(PriceRecommendation.applied_at >= today_start)
        )
        
        count = self.db.exec(stmt).first() or 0
        
        return count < settings.max_auto_changes_per_day
    
    def _in_blackout_period(self, settings: PricingSettings) -> bool:
        """Check if current time is in blackout period."""
        
        if settings.blackout_hours_start is None or settings.blackout_hours_end is None:
            return False
        
        current_hour = datetime.now(timezone.utc).hour
        
        start = settings.blackout_hours_start
        end = settings.blackout_hours_end
        
        # Handle overnight blackouts (e.g., 22:00 - 06:00)
        if start > end:
            return current_hour >= start or current_hour < end
        else:
            return start <= current_hour < end
    
    def _push_to_ecommerce_sync(self, product: Product, user_id: UUID) -> dict:
        """Sync wrapper for async e-commerce push."""
        try:
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, use thread executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._push_to_ecommerce(product, user_id)
                    )
                    return future.result(timeout=30)
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                return asyncio.run(self._push_to_ecommerce(product, user_id))
        except Exception as e:
            return {"platform": None, "success": False, "error": str(e)}
    
    async def _push_to_ecommerce(self, product: Product, user_id: UUID) -> dict:
        """Push price update to connected e-commerce platform."""
        from backend.core.encryption import decrypt_token
        from backend.services.integration.shopify_service import ShopifyService
        from backend.services.integration.woocommerce_service import WooCommerceService
        from backend.services.integration.base import PriceUpdateRequest, PriceUpdateResult
        
        # Get product integration link
        stmt = (
            select(ProductIntegrationLink)
            .where(ProductIntegrationLink.product_id == product.id)
            .where(ProductIntegrationLink.sync_enabled == True)
        )
        link = self.db.exec(stmt).first()
        
        if not link:
            return {"platform": None, "success": False, "error": "Product not linked to any platform"}
        
        # Get the integration
        integration = self.db.get(Integration, link.integration_id)
        
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
        try:
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
                link.last_price_push_at = datetime.now(timezone.utc)
                link.external_price = float(product.current_price)
                link.updated_at = datetime.now(timezone.utc)
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
            return {"platform": integration.platform.value, "success": False, "error": str(e)}
    
    def get_approval_stats(self, user_id: UUID, days: int = 30) -> dict:
        """Get approval statistics for a user."""
        
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Total recommendations
        stmt_total = (
            select(func.count(PriceRecommendation.id))
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.created_at >= since)
        )
        total = self.db.exec(stmt_total).first() or 0
        
        # By status
        stats = {"total": total, "by_status": {}}
        
        for status in RecommendationStatus:
            stmt = (
                select(func.count(PriceRecommendation.id))
                .where(PriceRecommendation.user_id == user_id)
                .where(PriceRecommendation.status == status)
                .where(PriceRecommendation.created_at >= since)
            )
            count = self.db.exec(stmt).first() or 0
            stats["by_status"][status.value] = count
        
        # Average confidence of applied
        stmt_conf = (
            select(func.avg(PriceRecommendation.confidence_score))
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.APPLIED)
            .where(PriceRecommendation.created_at >= since)
        )
        avg_confidence = self.db.exec(stmt_conf).first()
        stats["avg_confidence_applied"] = float(avg_confidence) if avg_confidence else None
        
        # Auto vs manual approval ratio
        auto = stats["by_status"].get("auto_approved", 0)
        manual = stats["by_status"].get("approved", 0)
        stats["auto_approval_ratio"] = auto / (auto + manual) if (auto + manual) > 0 else 0
        
        return stats
