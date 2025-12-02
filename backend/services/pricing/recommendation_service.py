# backend/services/pricing/recommendation_service.py
"""
Recommendation Service - Generates price recommendations based on rules and signals.
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from backend.models.product import Product
from backend.models.pricing_rule import PricingRule, RuleAction
from backend.models.price_recommendation import PriceRecommendation, RecommendationStatus
from backend.models.pricing_settings import PricingSettings
from .rule_evaluator import RuleEvaluator, MarketSignals
from .signal_processor import SignalProcessor
from .confidence_calculator import ConfidenceCalculator


class RecommendationService:
    """Generates and manages price recommendations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.rule_evaluator = RuleEvaluator(db)
        self.signal_processor = SignalProcessor(db)
        self.confidence_calculator = ConfidenceCalculator()
    
    def generate_recommendation(
        self,
        product: Product,
        user_id: UUID
    ) -> Optional[PriceRecommendation]:
        """Generate a price recommendation for a product."""
        
        # Gather market signals
        signals = self.signal_processor.gather_signals(product)
        
        # Find matching rule
        result = self.rule_evaluator.find_matching_rule(product, user_id, signals) 

        if not result:
            return None
        
        # Use highest priority triggered rule
        rule, match_details = result

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
        settings = self._get_user_settings(user_id)
        valid_hours = settings.recommendation_valid_hours if settings else 48
        valid_until = datetime.now(timezone.utc) + timedelta(hours=valid_hours)
        
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
        rule.last_triggered_at = datetime.now(timezone.utc)
        self.db.add(rule)
        
        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(recommendation)
        
        return recommendation
    
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
        if product.cost is not None and product.cost > 0:
            settings = self._get_user_settings(product.user_id)
            min_margin = settings.min_margin_percent if settings else Decimal("10.0")
            
            margin_floor = product.cost * (1 + min_margin / 100)
            margin_floor = margin_floor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            # Use the higher of min_price and margin_floor
            if min_price is None or margin_floor > min_price:
                min_price = margin_floor
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
        
        if match_details["rule_type"] == "sentiment_threshold":
            sentiment = match_details["sentiment_score"]
            threshold = match_details["threshold"]
            dir_word = "above" if match_details["direction"] == "above" else "below"
            base += f"Sentiment score ({sentiment:.2f}) is {dir_word} threshold ({threshold})."
        
        elif match_details["rule_type"] == "competitor_relative":
            comp_price = match_details["competitor_price"]
            base += f"Adjusting relative to competitor price (${comp_price:.2f})."
        
        elif match_details["rule_type"] == "time_based":
            days = match_details["allowed_days"]
            base += f"Time-based rule active ({', '.join(days)})."
        
        elif match_details["rule_type"] == "volume_surge":
            count = match_details["mention_count"]
            threshold = match_details["threshold"]
            base += f"Volume surge detected ({count} mentions, threshold: {threshold})."
        
        elif match_details["rule_type"] == "viral_detection":
            reach = match_details["reach"]
            base += f"Viral content detected (reach: {reach:,})."
        
        return base
    
    def _get_user_settings(self, user_id: UUID) -> Optional[PricingSettings]:
        """Get user's pricing settings."""
        stmt = select(PricingSettings).where(PricingSettings.user_id == user_id)
        return self.db.exec(stmt).first()
    
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
            current_hour = datetime.now(timezone.utc).hour
            if settings.blackout_hours_start <= current_hour < settings.blackout_hours_end:
                return True
        
        return False
    
    def get_pending_recommendations(
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
            .where(PriceRecommendation.valid_until > datetime.now(timezone.utc))
        )
        
        if product_id:
            stmt = stmt.where(PriceRecommendation.product_id == product_id)
        
        stmt = stmt.order_by(PriceRecommendation.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)
        
        return list(self.db.exec(stmt).all())
    
    def expire_old_recommendations(self) -> int:
        """Mark expired recommendations. Returns count of expired."""
        
        stmt = (
            select(PriceRecommendation)
            .where(PriceRecommendation.status == RecommendationStatus.PENDING)
            .where(PriceRecommendation.valid_until <= datetime.now(timezone.utc))
        )
        
        expired = list(self.db.exec(stmt).all())
        
        for rec in expired:
            rec.status = RecommendationStatus.EXPIRED
            self.db.add(rec)
        
        self.db.commit()
        
        return len(expired)

