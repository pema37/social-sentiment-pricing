# backend/services/pricing/recommendation_service.py
"""
Recommendation Service - Generates price recommendations based on rules and signals.

Refactored: Orchestration layer that delegates to focused sub-services.

Dependencies:
- PriceSyncService: Fetches live prices from stores (Priority 1)
- SettingsService: Manages user settings with defaults (Priority 2)
- CompetitorFallbackService: Generates competitor-only recommendations
- PriceCalculator, BoundaryEnforcer, ReasoningGenerator: Calculation helpers

FIX (2026-01-28) Bug #1: Always refresh product from DB before generating
recommendations to ensure current_price reflects actual database state.
"""

import logging
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.product import Product
from models.pricing_rule import PricingRule
from models.price_recommendation import PriceRecommendation, RecommendationStatus

from .rule_evaluator import RuleEvaluator
from .signal_processor import SignalProcessor
from .confidence_calculator import ConfidenceCalculator
from .price_sync_service import PriceSyncService
from .settings_service import SettingsService
from .competitor_fallback import CompetitorFallbackService
from .recommendation_helpers import (
    PriceCalculator,
    BoundaryEnforcer,
    ReasoningGenerator,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    """Generates and manages price recommendations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        
        # Core evaluation services
        self.rule_evaluator = RuleEvaluator(db)
        self.signal_processor = SignalProcessor(db)
        self.confidence_calculator = ConfidenceCalculator()
        
        # Specialized sub-services
        self.price_sync = PriceSyncService(db)
        self.settings_service = SettingsService(db)
        self.competitor_fallback = CompetitorFallbackService(db)
    
    async def generate_recommendation(
        self,
        product: Product,
        user_id: UUID
    ) -> Optional[PriceRecommendation]:
        """
        Generate a price recommendation for a product.
        
        Flow:
        1. Refresh product from DB to ensure fresh data
        2. Sync live price from store (if connected)
        3. Check for existing pending recommendations
        4. Gather market signals
        5. Find matching pricing rule
        6. If no rule matches, try competitor fallback
        7. Calculate price and create recommendation
        8. Auto-apply if settings allow
        """
        # =============================================================
        # BUGFIX (2026-01-28): Always refresh product from DB first
        # =============================================================
        # The product object passed in may have stale data from earlier
        # in the request lifecycle. Refresh to ensure we have the actual
        # current_price from the database before any calculations.
        # =============================================================
        await self.db.refresh(product)
        logger.debug(
            f"Refreshed product {product.id} from DB: current_price=${product.current_price}"
        )
        
        # Step 2: Try to sync with live store price (may update DB + product object)
        price_synced = await self.price_sync.sync_product_price(product, user_id)
        if price_synced:
            logger.info(
                f"Product {product.id} price synced from store: ${product.current_price}"
            )
        
        # Step 3: Check for existing pending recommendation
        if await self._has_pending_recommendation(product.id, user_id):
            logger.debug(f"Product {product.id} already has pending recommendation")
            return None
        
        # Step 4: Gather market signals
        signals = await self.signal_processor.gather_signals(product)
        
        # Step 5: Find matching rule
        result = await self.rule_evaluator.find_matching_rule(product, user_id, signals)
        
        # Step 6: No rule matched - try competitor fallback
        if not result or result[0] is None:
            logger.info(f"No rule matched for product {product.id}, trying competitor fallback")
            return await self.competitor_fallback.generate(product, user_id, signals)
        
        rule, match_details = result
        
        # Step 7: Generate rule-based recommendation
        return await self._create_rule_based_recommendation(
            product, user_id, rule, match_details, signals
        )
    
    async def _has_pending_recommendation(
        self,
        product_id: UUID,
        user_id: UUID
    ) -> bool:
        """Check if pending recommendation already exists."""
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.product_id == product_id)
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until > datetime.now(UTC))
        )
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None
    
    async def _create_rule_based_recommendation(
        self,
        product: Product,
        user_id: UUID,
        rule: PricingRule,
        match_details: dict,
        signals
    ) -> Optional[PriceRecommendation]:
        """Create recommendation based on a matched pricing rule."""
        # Calculate new price
        new_price = PriceCalculator.calculate_new_price(product, rule, signals)
        
        if new_price is None or new_price == product.current_price:
            logger.debug(
                f"No price change needed for product {product.id}: "
                f"current=${product.current_price}, calculated=${new_price}"
            )
            return None
        
        # Apply boundaries
        new_price = BoundaryEnforcer.apply_boundaries(new_price, product, rule)
        change_percent = BoundaryEnforcer.calculate_change_percent(
            product.current_price, new_price
        )
        
        # Calculate confidence
        price_impacts = self.signal_processor.calculate_price_impact(signals, product)
        confidence = self.confidence_calculator.calculate(
            signals, price_impacts, rule.rule_type.value
        )
        
        # Build factors
        factors = {
            "match_details": match_details,
            "price_impacts": price_impacts,
            "confidence_breakdown": self.confidence_calculator.get_confidence_breakdown(
                signals, price_impacts, rule.rule_type.value
            ),
        }
        
        # Generate reasoning
        reasoning = ReasoningGenerator.generate(
            product, rule, match_details, new_price, change_percent, signals
        )
        
        # Get settings (Priority 2 fix ensures defaults exist)
        settings = await self.settings_service.get_or_create(user_id)
        valid_until = datetime.now(UTC) + timedelta(hours=settings.recommendation_valid_hours)
        
        # Check approval requirement
        requires_approval = self.settings_service.check_requires_approval(
            product, change_percent, confidence, settings
        )
        
        # Create recommendation
        # NOTE: current_price now guaranteed to be fresh from DB refresh above
        recommendation = PriceRecommendation(
            user_id=user_id,
            product_id=product.id,
            triggered_rule_id=rule.id,
            current_price=product.current_price,
            recommended_price=new_price,
            change_percent=change_percent,
            confidence_score=confidence,
            reasoning=reasoning,
            factors=factors,
            status=RecommendationStatus.PENDING,
            requires_approval=requires_approval,
            valid_until=valid_until,
        )
        
        logger.info(
            f"Creating recommendation for product {product.id}: "
            f"${product.current_price} → ${new_price} ({change_percent:+.1f}%), "
            f"confidence={confidence:.2f}, requires_approval={requires_approval}"
        )
        
        # Update rule's last_triggered_at
        rule.last_triggered_at = datetime.now(UTC)
        self.db.add(rule)
        
        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)
        
        # Auto-apply if eligible
        if not requires_approval and settings.auto_approve_enabled:
            await self._try_auto_apply(recommendation, user_id)
        
        return recommendation
    
    async def _try_auto_apply(
        self,
        recommendation: PriceRecommendation,
        user_id: UUID
    ) -> None:
        """Attempt to auto-approve and apply recommendation."""
        try:
            from services.pricing.approval_service import ApprovalService
            approval_service = ApprovalService(self.db)
            await approval_service.auto_approve_and_apply(recommendation.id, user_id)
            logger.info(f"Auto-applied recommendation {recommendation.id}")
        except Exception as e:
            logger.warning(f"Auto-apply failed for recommendation {recommendation.id}: {e}")
    
    # =========================================================================
    # Query Methods
    # =========================================================================
    
    async def get_pending_recommendations(
        self,
        user_id: UUID,
        product_id: Optional[UUID] = None,
        limit: int = 20,
        offset: int = 0
    ) -> list[PriceRecommendation]:
        """Get pending recommendations for a user."""
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until > datetime.now(UTC))
        )
        
        if product_id:
            stmt = stmt.where(PriceRecommendation.product_id == product_id)
        
        stmt = stmt.order_by(PriceRecommendation.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def expire_old_recommendations(self) -> int:
        """Mark expired recommendations. Returns count of expired."""
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until <= datetime.now(UTC))
        )
        
        result = await self.db.execute(stmt)
        expired = list(result.scalars().all())
        
        for rec in expired:
            rec.status = RecommendationStatus.EXPIRED
            self.db.add(rec)
        
        await self.db.commit()
        
        logger.info(f"Expired {len(expired)} old recommendations")
        return len(expired)




        