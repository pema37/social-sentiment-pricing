# backend/services/pricing/rule_evaluator.py
"""
Rule Evaluator - Evaluates pricing rules against market signals.

Updated to support rule scoping:
- applies_to_all_products: Rule applies to all user's products
- applies_to_products: Rule applies to specific product IDs
- applies_to_categories: Rule applies to products in specific categories
- product_id: Legacy single-product targeting (still supported)

PATCHED 2026-01-07: Fixed duplicate competitor UUID issue
- Added name-based competitor matching when UUID doesn't match directly
- Handles cases where multiple competitor entries exist with same name (e.g., "Amazon")
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.competitor import Competitor
from models.pricing_rule import PricingRule, RuleType
from models.product import Product

logger = logging.getLogger(__name__)


@dataclass
class MarketSignals:
    """All market signals used for rule evaluation."""

    # Sentiment signals
    sentiment_score: Decimal | None = None
    sentiment_change_24h: Decimal | None = None

    # Volume signals
    mention_count_24h: int = 0
    mention_baseline: int = 0  # Average daily mentions over past 7 days

    # Viral signals
    viral_detected: bool = False
    viral_reach: int = 0
    viral_engagement: int = 0
    viral_sentiment: Decimal | None = None

    # Competitor signals
    competitor_prices: dict[UUID, Decimal] = field(default_factory=dict)

    # Trend signals
    trend_direction: str | None = None  # "up", "down", "stable"
    trend_strength: Decimal = Decimal("0")  # 0-1 scale
    trend_velocity: Decimal = Decimal("0")  # Rate of change
    mention_growth_rate: Decimal = Decimal("0")  # % change in mentions
    sentiment_momentum: Decimal = Decimal("0")  # Sentiment trend direction
    is_trending: bool = False  # Is this product currently trending?


class RuleEvaluator:
    """Evaluates pricing rules against market signals."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_rules(
        self, product_id: UUID, user_id: UUID, product_category: str | None = None
    ) -> list[PricingRule]:
        """
        Get all active rules that apply to a product, ordered by priority.

        A rule applies to a product if ANY of these conditions are true:
        1. applies_to_all_products is True
        2. product_id matches the rule's product_id (legacy)
        3. product_id is in applies_to_products list
        4. product_category is in applies_to_categories list
        """

        # Build query for rules that could apply to this product
        stmt = (
            select(PricingRule)
            .where(PricingRule.user_id == user_id, PricingRule.is_active == True)
            .order_by(PricingRule.priority.desc())
        )

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
        self, rule: PricingRule, product_id: UUID, product_id_str: str, product_category: str | None
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
        self, product: Product, user_id: UUID, signals: MarketSignals
    ) -> tuple[PricingRule | None, dict | None]:
        """Find the highest priority rule that matches current signals."""

        # Get rules with category context
        rules = await self.get_active_rules(product.id, user_id, product.category)

        for rule in rules:
            # Check cooldown
            if rule.last_triggered_at:
                last_triggered = rule.last_triggered_at.replace(tzinfo=UTC)
                cooldown_until = last_triggered + timedelta(hours=rule.cooldown_hours)
                if datetime.now(UTC) < cooldown_until:
                    continue

            # PATCHED: Now async to support name-based competitor matching
            match_details = await self._evaluate_rule(rule, product, signals)
            if match_details:
                return rule, match_details

        return None, None

    async def _evaluate_rule(self, rule: PricingRule, product: Product, signals: MarketSignals) -> dict | None:
        """Evaluate a single rule. Returns match details if triggered, None otherwise."""

        if rule.rule_type == RuleType.SENTIMENT_THRESHOLD:
            return self._eval_sentiment_threshold(rule, signals)

        elif rule.rule_type == RuleType.COMPETITOR_RELATIVE:
            # PATCHED: Now async to support name-based matching
            return await self._eval_competitor_relative(rule, signals)

        elif rule.rule_type == RuleType.TIME_BASED:
            return self._eval_time_based(rule)

        elif rule.rule_type == RuleType.VOLUME_SURGE:
            return self._eval_volume_surge(rule, signals)

        elif rule.rule_type == RuleType.VIRAL_DETECTION:
            return self._eval_viral_detection(rule, signals)

        return None

    def _eval_sentiment_threshold(self, rule: PricingRule, signals: MarketSignals) -> dict | None:
        """Evaluate sentiment threshold rule."""

        if signals.sentiment_score is None:
            return None

        threshold = rule.sentiment_threshold
        if threshold is None:
            return None  # Cannot evaluate without a threshold

        direction = rule.sentiment_direction or "above"

        triggered = False
        if (direction == "above" and signals.sentiment_score >= threshold) or (
            direction == "below" and signals.sentiment_score <= threshold
        ):
            triggered = True

        if triggered:
            return {
                "rule_type": "sentiment_threshold",
                "sentiment_score": float(signals.sentiment_score),
                "threshold": float(threshold),
                "direction": direction,
            }

        return None

    async def _eval_competitor_relative(self, rule: PricingRule, signals: MarketSignals) -> dict | None:
        """
        Evaluate competitor-relative pricing rule.

        PATCHED: Now matches by competitor NAME when UUID doesn't match directly.
        This handles cases where duplicate competitor entries exist (e.g., multiple "Amazon" UUIDs).
        """

        # If a specific competitor is set on the rule
        if rule.competitor_id:
            # First try direct UUID match (fast path)
            if rule.competitor_id in signals.competitor_prices:
                competitor_price = signals.competitor_prices[rule.competitor_id]
                logger.debug(f"Competitor rule matched by UUID: {rule.competitor_id}")
                return {
                    "rule_type": "competitor_relative",
                    "competitor_id": str(rule.competitor_id),
                    "competitor_price": float(competitor_price),
                    "margin_percent": float(rule.competitor_margin_percent or 0),
                    "price_position": rule.price_position,
                }

            # UUID didn't match - try matching by competitor NAME
            # This handles duplicate competitor entries (e.g., multiple "Amazon" UUIDs)
            logger.debug(
                f"Competitor UUID {rule.competitor_id} not in signals, "
                f"attempting name-based match. Available: {list(signals.competitor_prices.keys())}"
            )
            matched = await self._match_competitor_by_name(rule.competitor_id, signals.competitor_prices)
            if matched:
                logger.info(
                    f"Competitor rule matched by NAME: rule uses {rule.competitor_id}, "
                    f"matched to {matched['competitor_id']} ({matched['name']})"
                )
                return {
                    "rule_type": "competitor_relative",
                    "competitor_id": str(matched["competitor_id"]),
                    "competitor_price": float(matched["price"]),
                    "margin_percent": float(rule.competitor_margin_percent or 0),
                    "price_position": rule.price_position,
                    "matched_by": "name",  # Flag for debugging
                    "original_competitor_id": str(rule.competitor_id),  # For audit trail
                }

        # If no specific competitor, check if ANY competitor price is available
        if not rule.competitor_id and signals.competitor_prices:
            # Use the lowest competitor price
            min_price = min(signals.competitor_prices.values())
            min_competitor_id = [k for k, v in signals.competitor_prices.items() if v == min_price][0]
            logger.debug(f"Competitor rule using lowest price from {min_competitor_id}: ${min_price}")
            return {
                "rule_type": "competitor_relative",
                "competitor_id": str(min_competitor_id),
                "competitor_price": float(min_price),
                "margin_percent": float(rule.competitor_margin_percent or 0),
                "price_position": rule.price_position,
            }

        logger.debug(
            f"Competitor rule not matched: competitor_id={rule.competitor_id}, available={list(signals.competitor_prices.keys())}"
        )
        return None

    async def _match_competitor_by_name(
        self, rule_competitor_id: UUID, available_competitor_prices: dict[UUID, Decimal]
    ) -> dict | None:
        """
        Find a matching competitor by name when UUIDs don't match directly.

        This handles the case where:
        - Rule targets competitor_id A (name="Amazon")
        - Product's competitor data uses competitor_id B (name="Amazon")
        - UUIDs differ but they're the same logical competitor

        Returns:
            {"competitor_id": UUID, "price": Decimal, "name": str} or None
        """
        if not available_competitor_prices:
            return None

        # Get the name of the rule's target competitor
        stmt = select(Competitor.name).where(Competitor.id == rule_competitor_id)
        result = await self.db.execute(stmt)
        target_name = result.scalar()

        if not target_name:
            logger.warning(f"Competitor {rule_competitor_id} not found in database")
            return None

        # Normalize for comparison (lowercase, strip whitespace)
        target_name_normalized = target_name.lower().strip()
        logger.debug(f"Looking for competitor name match: '{target_name}'")

        # Get names for all available competitor prices
        available_ids = list(available_competitor_prices.keys())
        stmt = select(Competitor.id, Competitor.name).where(Competitor.id.in_(available_ids))
        result = await self.db.execute(stmt)
        available_competitors = result.all()

        # Find matching competitor by name
        for comp_id, comp_name in available_competitors:
            if comp_name and comp_name.lower().strip() == target_name_normalized:
                logger.debug(f"Found name match: {comp_id} ('{comp_name}')")
                return {
                    "competitor_id": comp_id,
                    "price": available_competitor_prices[comp_id],
                    "name": comp_name,
                }

        logger.debug(f"No name match found for '{target_name}' among {[c[1] for c in available_competitors]}")
        return None

    def _eval_time_based(self, rule: PricingRule) -> dict | None:
        """Evaluate time-based rule."""

        now = datetime.now(UTC)

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

    def _eval_volume_surge(self, rule: PricingRule, signals: MarketSignals) -> dict | None:
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

    def _eval_viral_detection(self, rule: PricingRule, signals: MarketSignals) -> dict | None:
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
