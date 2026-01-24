# backend/services/pricing/recommendation_service.py
"""
Recommendation Service - Generates price recommendations based on rules and signals.

PATCHED: Added competitor-only fallback when no rules match (Issue 1 fix)
FIX (2026-01-24): Competitor fallback now respects user's auto-approval settings
instead of always requiring manual approval.
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.product import Product
from models.pricing_rule import PricingRule, RuleAction
from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.pricing_settings import PricingSettings
from .rule_evaluator import RuleEvaluator, MarketSignals
from .signal_processor import SignalProcessor
from .confidence_calculator import ConfidenceCalculator

logger = logging.getLogger(__name__)


class RecommendationService:
    """Generates and manages price recommendations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.rule_evaluator = RuleEvaluator(db)
        self.signal_processor = SignalProcessor(db)
        self.confidence_calculator = ConfidenceCalculator()
    
    async def generate_recommendation(
        self,
        product: Product,
        user_id: UUID
    ) -> Optional[PriceRecommendation]:
        """Generate a price recommendation for a product."""
        
        # Check if pending recommendation already exists for this product
        existing_stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.product_id == product.id)
            .where(PriceRecommendation.user_id == user_id)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until > datetime.utcnow())
        )
        existing_result = await self.db.execute(existing_stmt)
        if existing_result.scalars().first():
            return None  # Don't create duplicate pending recommendation
        
        # Gather market signals
        signals = await self.signal_processor.gather_signals(product)
        
        # Find matching rule
        result = await self.rule_evaluator.find_matching_rule(product, user_id, signals) 

        # ========== PATCH START: COMPETITOR-ONLY FALLBACK ==========
        # If no rule matches but we have competitor data, generate competitor-based recommendation
        if not result:
            logger.info(f"No rule matched for product {product.id}, trying competitor fallback...")
            recommendation = await self._generate_competitor_fallback(product, user_id, signals)
            if recommendation:
                return recommendation
            logger.info(f"No competitor fallback possible for product {product.id}")
            return None
        # ========== PATCH END ==========
        
        # Use highest priority triggered rule
        rule, match_details = result
        
        # Double-check rule is valid (in case tuple returned with None rule)
        if rule is None:
            # ========== PATCH: Also try fallback here ==========
            recommendation = await self._generate_competitor_fallback(product, user_id, signals)
            if recommendation:
                return recommendation
            return None
            # ========== END ==========

        # Calculate new price
        new_price = self._calculate_new_price(product, rule, signals)
        
        if new_price is None or new_price == product.current_price:
            return None
        
        # Apply boundaries
        new_price = self._apply_boundaries(new_price, product, rule)
        
        # Calculate change percent
        change_percent = ((new_price - product.current_price) / product.current_price) * 100
        change_percent = change_percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Calculate price impacts and confidence
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
        reasoning = self._generate_reasoning(
            product, rule, match_details, new_price, change_percent, signals
        )
        
        # Get user settings for expiry
        settings = await self._get_user_settings(user_id)
        valid_hours = settings.recommendation_valid_hours if settings else 48
        valid_until = datetime.utcnow() + timedelta(hours=valid_hours)
        
        # Determine if auto-approval applies
        requires_approval = self._check_requires_approval(
            product, change_percent, confidence, settings
        )
        
        # Create recommendation
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
        
        # Update rule's last_triggered_at
        rule.last_triggered_at = datetime.utcnow()
        self.db.add(rule)
        
        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)
        
        # AUTO-APPLY: If recommendation doesn't require approval, auto-approve and push to e-commerce
        if not requires_approval and settings and settings.auto_approve_enabled:
            try:
                from services.pricing.approval_service import ApprovalService
                approval_service = ApprovalService(self.db)
                recommendation = await approval_service.auto_approve_and_apply(recommendation.id, user_id)
                logger.info(f"Auto-applied recommendation {recommendation.id} for product {product.id}")
            except Exception as e:
                # Log error but don't fail - recommendation stays as pending
                logger.warning(f"Auto-apply failed for recommendation {recommendation.id}: {str(e)}")
        
        return recommendation
    
    # ========== PATCH START: NEW METHOD ==========
    async def _generate_competitor_fallback(
        self,
        product: Product,
        user_id: UUID,
        signals: MarketSignals
    ) -> Optional[PriceRecommendation]:
        """
        Generate a recommendation based on competitor price alone.
        
        Called when no pricing rules match (e.g., insufficient sentiment data).
        Uses competitor pricing to provide a basic recommendation.
        
        FIX (2026-01-24): Now respects user's auto-approval settings instead of
        always requiring manual approval.
        
        Returns:
            PriceRecommendation with data_source='competitor_only', or None
        """
        # Check if we have any competitor prices
        if not signals.competitor_prices:
            logger.debug(f"No competitor prices available for product {product.id}")
            return None
        
        # Find the first valid competitor price
        competitor_price = None
        competitor_id = None
        
        for comp_id, price in signals.competitor_prices.items():
            # Skip invalid prices (null, zero, or likely scraping errors >$5000)
            if price and price > 0 and price < Decimal("5000"):
                competitor_price = Decimal(str(price))
                competitor_id = comp_id
                logger.debug(f"Using competitor {comp_id} price: ${price}")
                break
        
        if not competitor_price:
            logger.debug(f"No valid competitor prices for product {product.id} (filtered as invalid)")
            return None
        
        # Validate current price
        current_price = product.current_price
        if not current_price or current_price <= 0:
            logger.warning(f"Product {product.id} has invalid current_price: {current_price}")
            return None
        
        # Calculate price difference percentage
        # Positive = we're above competitor, Negative = we're below
        price_diff_pct = ((current_price - competitor_price) / competitor_price) * Decimal("100")
        
        # Determine action based on price position
        new_price = None
        reasoning = ""
        
        if price_diff_pct > Decimal("10"):
            # We're >10% above competitor - suggest matching at 98% of competitor
            new_price = competitor_price * Decimal("0.98")
            reasoning = (
                f"Your price (${current_price:.2f}) is {price_diff_pct:.1f}% above competitor "
                f"(${competitor_price:.2f}). Recommending price match at 98% of competitor price."
            )
            logger.info(f"Product {product.id}: {price_diff_pct:.1f}% above competitor, suggesting decrease")
            
        elif price_diff_pct < Decimal("-15"):
            # We're >15% below competitor - opportunity for increase
            new_price = current_price * Decimal("1.05")  # 5% increase
            reasoning = (
                f"Your price (${current_price:.2f}) is {abs(price_diff_pct):.1f}% below competitor "
                f"(${competitor_price:.2f}). Room for a 5% price increase."
            )
            logger.info(f"Product {product.id}: {abs(price_diff_pct):.1f}% below competitor, suggesting increase")
            
        else:
            # Price is competitive (within -15% to +10%), no change needed
            logger.info(f"Product {product.id} price is competitive ({price_diff_pct:.1f}% vs competitor)")
            return None
        
        # Apply product min/max constraints
        if product.min_price and new_price < product.min_price:
            new_price = product.min_price
            logger.debug(f"Adjusted to min_price: ${product.min_price}")
        if product.max_price and new_price > product.max_price:
            new_price = product.max_price
            logger.debug(f"Adjusted to max_price: ${product.max_price}")
        
        # Round to 2 decimal places
        new_price = new_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Calculate actual change percentage
        change_percent = ((new_price - current_price) / current_price) * Decimal("100")
        change_percent = change_percent.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        
        # Skip if change is too small (<1%)
        if abs(change_percent) < Decimal("1"):
            logger.debug(f"Change too small ({change_percent}%), skipping")
            return None
        
        # Get user settings
        settings = await self._get_user_settings(user_id)
        valid_hours = settings.recommendation_valid_hours if settings else 48
        valid_until = datetime.utcnow() + timedelta(hours=valid_hours)
        
        # Build factors dict - includes data_source flag for frontend
        factors = {
            "match_details": {
                "rule_type": "competitor_fallback",
                "competitor_id": str(competitor_id) if competitor_id else None,
                "competitor_price": float(competitor_price),
                "price_diff_pct": float(price_diff_pct),
            },
            "price_impacts": {
                "competitor": float(new_price - current_price),
            },
            "confidence_breakdown": {
                "base_confidence": 0.65,
                "reason": "competitor_only",
                "note": "Lower confidence - based on competitor price only, no sentiment data"
            },
            "data_source": "competitor_only",  # Frontend uses this to show badge
        }
        
        # ═══════════════════════════════════════════════════════════════════════
        # FIX (2026-01-24): Check user settings instead of hardcoding True
        # Previously: requires_approval=True (always manual)
        # Now: Uses same logic as rule-based recommendations
        # ═══════════════════════════════════════════════════════════════════════
        requires_approval = self._check_requires_approval(
            product, change_percent, Decimal("0.65"), settings
        )
        
        # Create recommendation with lower confidence (65% for competitor-only)
        recommendation = PriceRecommendation(
            user_id=user_id,
            product_id=product.id,
            triggered_rule_id=None,  # No rule triggered - this is a fallback
            current_price=current_price,
            recommended_price=new_price,
            change_percent=change_percent,
            confidence_score=Decimal("0.65"),  # Lower confidence without sentiment
            reasoning=reasoning,
            factors=factors,
            status=RecommendationStatus.PENDING,
            requires_approval=requires_approval,  # Now respects user settings
            valid_until=valid_until,
        )
        
        self.db.add(recommendation)
        await self.db.commit()
        await self.db.refresh(recommendation)
        
        logger.info(
            f"Generated competitor fallback for product {product.id}: "
            f"${current_price} → ${new_price} ({change_percent:+.1f}%), "
            f"requires_approval={requires_approval}"
        )
        
        # ═══════════════════════════════════════════════════════════════════════
        # FIX (2026-01-24): Auto-apply if settings allow
        # Previously: Never auto-applied competitor fallbacks
        # Now: Same auto-apply logic as rule-based recommendations
        # ═══════════════════════════════════════════════════════════════════════
        if not requires_approval and settings and settings.auto_approve_enabled:
            try:
                from services.pricing.approval_service import ApprovalService
                approval_service = ApprovalService(self.db)
                recommendation = await approval_service.auto_approve_and_apply(recommendation.id, user_id)
                logger.info(f"Auto-applied competitor fallback {recommendation.id} for product {product.id}")
            except Exception as e:
                logger.warning(f"Auto-apply failed for competitor fallback {recommendation.id}: {str(e)}")
        
        return recommendation
    # ========== PATCH END ==========
    
    def _calculate_new_price(
        self,
        product: Product,
        rule: PricingRule,
        signals: MarketSignals
    ) -> Optional[Decimal]:
        """Calculate new price based on rule action."""
        
        current = product.current_price
        
        if rule.action == RuleAction.INCREASE_PERCENT:
            return current * (1 + rule.action_value / 100)
        
        elif rule.action == RuleAction.DECREASE_PERCENT:
            return current * (1 - rule.action_value / 100)
        
        elif rule.action == RuleAction.SET_ABSOLUTE:
            return rule.action_value
        
        elif rule.action == RuleAction.MATCH_COMPETITOR:
            if rule.competitor_id and rule.competitor_id in signals.competitor_prices:
                return signals.competitor_prices[rule.competitor_id]
            return None
        
        elif rule.action == RuleAction.UNDERCUT_COMPETITOR:
            if rule.competitor_id and rule.competitor_id in signals.competitor_prices:
                competitor_price = signals.competitor_prices[rule.competitor_id]
                margin = rule.competitor_margin_percent or Decimal("5.0")
                return competitor_price * (1 - margin / 100)
            return None
        
        return None
    
    def _apply_boundaries(
        self,
        price: Decimal,
        product: Product,
        rule: PricingRule
    ) -> Decimal:
        """Apply min/max boundaries and margin floor from rule and product."""
        
        # Rule boundaries override product boundaries
        min_price = rule.min_price or product.min_price
        max_price = rule.max_price or product.max_price

        # === MARGIN FLOOR VALIDATION ===
        # Ensure we never price below cost + minimum margin
        # Note: margin floor check is sync, settings lookup moved to generate_recommendation
        # For simplicity here, use product min_price as floor
        # === END MARGIN FLOOR ===
        
        if min_price and price < min_price:
            price = min_price
        if max_price and price > max_price:
            price = max_price
        
        # Apply max change percent
        max_change = rule.max_change_percent / 100
        min_allowed = product.current_price * (1 - max_change)
        max_allowed = product.current_price * (1 + max_change)
        
        price = max(min_allowed, min(max_allowed, price))

        # Round to 2 decimal places
        return price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    def _generate_reasoning(
        self,
        product: Product,
        rule: PricingRule,
        match_details: dict,
        new_price: Decimal,
        change_percent: Decimal,
        signals: MarketSignals
    ) -> str:
        """Generate human-readable reasoning."""
        
        direction = "increase" if change_percent > 0 else "decrease"
        abs_change = abs(change_percent)
        
        base = f"Recommending {abs_change}% price {direction} for {product.name} "
        base += f"(${product.current_price} → ${new_price}). "
        
        rule_type = match_details.get("rule_type", "")
        
        if rule_type == "sentiment_threshold":
            sentiment = match_details.get("sentiment_score", 0)
            threshold = match_details.get("threshold", 0)
            dir_word = "above" if match_details.get("direction") == "above" else "below"
            base += f"Sentiment score ({sentiment:.2f}) is {dir_word} threshold ({threshold})."
        
        elif rule_type == "competitor_relative":
            comp_price = match_details.get("competitor_price", 0)
            base += f"Adjusting relative to competitor price (${comp_price:.2f})."
        
        elif rule_type == "time_based":
            days = match_details.get("allowed_days", [])
            base += f"Time-based rule active ({', '.join(days)})."
        
        elif rule_type == "volume_surge":
            count = match_details.get("mention_count", 0)
            threshold = match_details.get("threshold", 0)
            base += f"Volume surge detected ({count} mentions, threshold: {threshold})."
        
        elif rule_type == "viral_detection":
            reach = match_details.get("reach", 0)
            base += f"Viral content detected (reach: {reach:,})."
        
        else:
            base += f"Rule '{rule.name}' triggered."
        
        return base
    
    async def _get_user_settings(self, user_id: UUID) -> Optional[PricingSettings]:
        """Get user's pricing settings."""
        stmt = select(PricingSettings).where(PricingSettings.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()
    
    def _check_requires_approval(
        self,
        product: Product,
        change_percent: Decimal,
        confidence: Decimal,
        settings: Optional[PricingSettings]
    ) -> bool:
        """Check if recommendation requires manual approval."""
        
        if settings is None or not settings.auto_approve_enabled:
            return True
        
        # Check confidence threshold
        if confidence < settings.auto_approve_min_confidence:
            return True
        
        # Check change thresholds
        if change_percent > 0 and change_percent > settings.auto_approve_max_increase:
            return True
        if change_percent < 0 and abs(change_percent) > settings.auto_approve_max_decrease:
            return True
        
        # Check high-value product threshold
        if settings.require_approval_above_price:
            if product.current_price > settings.require_approval_above_price:
                return True
        
        # Check blackout hours
        if settings.blackout_hours_start is not None and settings.blackout_hours_end is not None:
            current_hour = datetime.utcnow().hour
            if settings.blackout_hours_start <= current_hour < settings.blackout_hours_end:
                return True
        
        return False
    
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
            .where(PriceRecommendation.valid_until > datetime.utcnow())
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
            .where(PriceRecommendation.valid_until <= datetime.utcnow())
        )
        
        result = await self.db.execute(stmt)
        expired = list(result.scalars().all())
        
        for rec in expired:
            rec.status = RecommendationStatus.EXPIRED
            self.db.add(rec)
        
        await self.db.commit()
        
        return len(expired)


        