# backend/services/pricing/rule_evaluator.py
"""
Rule Evaluator - Evaluates pricing rules against market signals.

Updated to support rule scoping:
- applies_to_all_products: Rule applies to all user's products
- applies_to_products: Rule applies to specific product IDs
- applies_to_categories: Rule applies to products in specific categories
- product_id: Legacy single-product targeting (still supported)
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.pricing_rule import PricingRule, RuleType
from models.product import Product


@dataclass
class MarketSignals:
    """All market signals used for rule evaluation."""
    
    # Sentiment signals
    sentiment_score: Optional[Decimal] = None
    sentiment_change_24h: Optional[Decimal] = None
    
    # Volume signals
    mention_count_24h: int = 0
    mention_baseline: int = 0  # Average daily mentions over past 7 days
    
    # Viral signals
    viral_detected: bool = False
    viral_reach: int = 0
    viral_engagement: int = 0
    viral_sentiment: Optional[Decimal] = None
    
    # Competitor signals
    competitor_prices: dict[UUID, Decimal] = field(default_factory=dict)
    
    # Trend signals
    trend_direction: Optional[str] = None  # "up", "down", "stable"
    trend_strength: Decimal = Decimal("0")  # 0-1 scale
    trend_velocity: Decimal = Decimal("0")  # Rate of change
    mention_growth_rate: Decimal = Decimal("0")  # % change in mentions
    sentiment_momentum: Decimal = Decimal("0")  # Sentiment trend direction
    is_trending: bool = False  # Is this product currently trending?


class RuleEvaluator:
    """Evaluates pricing rules against market signals."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_active_rules(self, product_id: UUID, user_id: UUID, product_category: Optional[str] = None) -> list[PricingRule]:
        """
        Get all active rules that apply to a product, ordered by priority.
        
        A rule applies to a product if ANY of these conditions are true:
        1. applies_to_all_products is True
        2. product_id matches the rule's product_id (legacy)
        3. product_id is in applies_to_products list
        4. product_category is in applies_to_categories list
        """
        
        # Build query for rules that could apply to this product
        stmt = select(PricingRule).where(
            PricingRule.user_id == user_id,
            PricingRule.is_active == True
        ).order_by(PricingRule.priority.desc())
        
        result = await self.db.execute(stmt)
        all_rules = list(result.scalars().all())
        
        # Filter rules that apply to this product
        applicable_rules = []
        product_id_str = str(product_id)
        
        for rule in all_rules:
            # Check if rule applies to this product
            if self._rule_applies_to_product(rule, product_id, product_id_str, product_category):
                applicable_rules.append(rule)
        
        return applicable_rules
    
    def _rule_applies_to_product(
        self, 
        rule: PricingRule, 
        product_id: UUID, 
        product_id_str: str,
        product_category: Optional[str]
    ) -> bool:
        """Check if a rule applies to a specific product."""
        
        # 1. Check applies_to_all_products flag
        if rule.applies_to_all_products:
            return True
        
        # 2. Check legacy single product_id
        if rule.product_id and rule.product_id == product_id:
            return True
        
        # 3. Check applies_to_products list
        if rule.applies_to_products:
            if product_id_str in rule.applies_to_products:
                return True
        
        # 4. Check applies_to_categories list
        if rule.applies_to_categories and product_category:
            if product_category in rule.applies_to_categories:
                return True
        
        return False
    
    async def find_matching_rule(
        self,
        product: Product,
        user_id: UUID,
        signals: MarketSignals
    ) -> tuple[Optional[PricingRule], Optional[dict]]:
        """Find the highest priority rule that matches current signals."""
        
        # Get rules with category context
        rules = await self.get_active_rules(product.id, user_id, product.category)
        
        for rule in rules:
            # Check cooldown
            if rule.last_triggered_at:                
                last_triggered = rule.last_triggered_at.replace(tzinfo=timezone.utc)
                cooldown_until = last_triggered + timedelta(hours=rule.cooldown_hours)
                if datetime.now(timezone.utc) < cooldown_until:
                    continue
            
            match_details = self._evaluate_rule(rule, product, signals)
            if match_details:
                return rule, match_details
        
        return None, None
    
    def _evaluate_rule(
        self,
        rule: PricingRule,
        product: Product,
        signals: MarketSignals
    ) -> Optional[dict]:
        """Evaluate a single rule. Returns match details if triggered, None otherwise."""
        
        if rule.rule_type == RuleType.SENTIMENT_THRESHOLD:
            return self._eval_sentiment_threshold(rule, signals)
        
        elif rule.rule_type == RuleType.COMPETITOR_RELATIVE:
            return self._eval_competitor_relative(rule, signals)
        
        elif rule.rule_type == RuleType.TIME_BASED:
            return self._eval_time_based(rule)
        
        elif rule.rule_type == RuleType.VOLUME_SURGE:
            return self._eval_volume_surge(rule, signals)
        
        elif rule.rule_type == RuleType.VIRAL_DETECTION:
            return self._eval_viral_detection(rule, signals)
        
        return None
    
    def _eval_sentiment_threshold(
        self,
        rule: PricingRule,
        signals: MarketSignals
    ) -> Optional[dict]:
        """Evaluate sentiment threshold rule."""
        
        if signals.sentiment_score is None:
            return None
        
        threshold = rule.sentiment_threshold
        if threshold is None:
            return None  # Cannot evaluate without a threshold
            
        direction = rule.sentiment_direction or "above"
        
        triggered = False
        if direction == "above" and signals.sentiment_score >= threshold:
            triggered = True
        elif direction == "below" and signals.sentiment_score <= threshold:
            triggered = True
        
        if triggered:
            return {
                "rule_type": "sentiment_threshold",
                "sentiment_score": float(signals.sentiment_score),
                "threshold": float(threshold),
                "direction": direction,
            }
        
        return None
    
    def _eval_competitor_relative(
        self,
        rule: PricingRule,
        signals: MarketSignals
    ) -> Optional[dict]:
        """Evaluate competitor-relative pricing rule."""
        
        # If a specific competitor is set, use that
        if rule.competitor_id and rule.competitor_id in signals.competitor_prices:
            competitor_price = signals.competitor_prices[rule.competitor_id]
            return {
                "rule_type": "competitor_relative",
                "competitor_id": str(rule.competitor_id),
                "competitor_price": float(competitor_price),
                "margin_percent": float(rule.competitor_margin_percent or 0),
                "price_position": rule.price_position,
            }
        
        # If no specific competitor, check if ANY competitor price is available
        if not rule.competitor_id and signals.competitor_prices:
            # Use the first/lowest competitor price
            min_price = min(signals.competitor_prices.values())
            min_competitor_id = [k for k, v in signals.competitor_prices.items() if v == min_price][0]
            return {
                "rule_type": "competitor_relative",
                "competitor_id": str(min_competitor_id),
                "competitor_price": float(min_price),
                "margin_percent": float(rule.competitor_margin_percent or 0),
                "price_position": rule.price_position,
            }
        
        return None
    
    def _eval_time_based(self, rule: PricingRule) -> Optional[dict]:
        """Evaluate time-based rule."""
        
        now = datetime.now(timezone.utc)
        
        # Check day of week
        if rule.time_days:
            days = [d.strip().lower() for d in rule.time_days.split(",")]
            current_day = now.strftime("%A").lower()
            if current_day not in days:
                return None
        
        # Check time range
        if rule.time_start and rule.time_end:
            current_time = now.strftime("%H:%M")
            if not (rule.time_start <= current_time <= rule.time_end):
                return None
        
        return {
            "rule_type": "time_based",
            "current_time": now.isoformat(),
            "time_days": rule.time_days,
            "time_start": rule.time_start,
            "time_end": rule.time_end,
        }
    
    def _eval_volume_surge(
        self,
        rule: PricingRule,
        signals: MarketSignals
    ) -> Optional[dict]:
        """Evaluate volume surge rule."""
        
        if signals.mention_baseline == 0:
            return None
        
        surge_ratio = signals.mention_count_24h / signals.mention_baseline
        threshold_ratio = (rule.volume_threshold or 200) / 100
        
        if surge_ratio >= threshold_ratio:
            return {
                "rule_type": "volume_surge",
                "mention_count_24h": signals.mention_count_24h,
                "baseline": signals.mention_baseline,
                "surge_ratio": float(surge_ratio),
                "threshold_ratio": float(threshold_ratio),
            }
        
        return None
    
    def _eval_viral_detection(
        self,
        rule: PricingRule,
        signals: MarketSignals
    ) -> Optional[dict]:
        """Evaluate viral detection rule."""
        
        if not signals.viral_detected:
            return None
        
        reach_ok = signals.viral_reach >= (rule.viral_threshold_reach or 0)
        engagement_ok = signals.viral_engagement >= (rule.viral_threshold_engagement or 0)
        
        sentiment_ok = True
        if rule.viral_sentiment_min and signals.viral_sentiment:
            sentiment_ok = signals.viral_sentiment >= rule.viral_sentiment_min
        
        if reach_ok and engagement_ok and sentiment_ok:
            return {
                "rule_type": "viral_detection",
                "viral_reach": signals.viral_reach,
                "viral_engagement": signals.viral_engagement,
                "viral_sentiment": float(signals.viral_sentiment) if signals.viral_sentiment else None,
            }
        
        return None
    
    