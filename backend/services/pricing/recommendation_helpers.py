# backend/services/pricing/recommendation_helpers.py
"""
Recommendation Helpers - Price calculation, boundaries, and reasoning generation.

Pure functions for price calculation logic, separated from orchestration.
"""

from decimal import ROUND_HALF_UP, Decimal

from models.pricing_rule import PricingRule, RuleAction
from models.product import Product

from .rule_evaluator import MarketSignals


class PriceCalculator:
    """Handles price calculations based on rules."""

    @staticmethod
    def calculate_new_price(product: Product, rule: PricingRule, signals: MarketSignals) -> Decimal | None:
        """Calculate new price based on rule action."""
        current = product.current_price

        action_handlers = {
            RuleAction.INCREASE_PERCENT: lambda: current * (1 + rule.action_value / 100),
            RuleAction.DECREASE_PERCENT: lambda: current * (1 - rule.action_value / 100),
            RuleAction.SET_ABSOLUTE: lambda: rule.action_value,
            RuleAction.MATCH_COMPETITOR: lambda: PriceCalculator._match_competitor(rule, signals),
            RuleAction.UNDERCUT_COMPETITOR: lambda: PriceCalculator._undercut_competitor(rule, signals),
        }

        handler = action_handlers.get(rule.action)
        if handler:
            return handler()
        return None

    @staticmethod
    def _match_competitor(rule: PricingRule, signals: MarketSignals) -> Decimal | None:
        """Match competitor price exactly."""
        if rule.competitor_id and rule.competitor_id in signals.competitor_prices:
            return signals.competitor_prices[rule.competitor_id]
        return None

    @staticmethod
    def _undercut_competitor(rule: PricingRule, signals: MarketSignals) -> Decimal | None:
        """Price below competitor by specified margin."""
        if rule.competitor_id and rule.competitor_id in signals.competitor_prices:
            competitor_price = signals.competitor_prices[rule.competitor_id]
            margin = rule.competitor_margin_percent or Decimal("5.0")
            return competitor_price * (1 - margin / 100)
        return None


class BoundaryEnforcer:
    """Enforces price boundaries and constraints."""

    @staticmethod
    def apply_boundaries(price: Decimal, product: Product, rule: PricingRule) -> Decimal:
        """Apply min/max boundaries and max change limits."""
        # Rule boundaries override product boundaries
        min_price = rule.min_price or product.min_price
        max_price = rule.max_price or product.max_price

        # Apply min/max
        if min_price and price < min_price:
            price = min_price
        if max_price and price > max_price:
            price = max_price

        # Apply max change percent
        price = BoundaryEnforcer._apply_max_change(price, product, rule)

        # Round to 2 decimal places
        return price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _apply_max_change(price: Decimal, product: Product, rule: PricingRule) -> Decimal:
        """Ensure price doesn't exceed max allowed change."""
        max_change = rule.max_change_percent / 100
        min_allowed = product.current_price * (1 - max_change)
        max_allowed = product.current_price * (1 + max_change)
        return max(min_allowed, min(max_allowed, price))

    @staticmethod
    def calculate_change_percent(current: Decimal, new: Decimal) -> Decimal:
        """Calculate percentage change between prices."""
        change = ((new - current) / current) * 100
        return change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class ReasoningGenerator:
    """Generates human-readable recommendation explanations."""

    @staticmethod
    def generate(
        product: Product,
        rule: PricingRule,
        match_details: dict,
        new_price: Decimal,
        change_percent: Decimal,
        signals: MarketSignals,
    ) -> str:
        """Generate human-readable reasoning for recommendation."""
        direction = "increase" if change_percent > 0 else "decrease"
        abs_change = abs(change_percent)

        base = (
            f"Recommending {abs_change}% price {direction} for {product.name} "
            f"(${product.current_price} → ${new_price}). "
        )

        rule_type = match_details.get("rule_type", "")
        detail = ReasoningGenerator._get_rule_type_detail(rule_type, match_details, rule)

        return base + detail

    @staticmethod
    def _get_rule_type_detail(rule_type: str, match_details: dict, rule: PricingRule) -> str:
        """Get rule-specific explanation detail."""
        generators = {
            "sentiment_threshold": ReasoningGenerator._sentiment_detail,
            "competitor_relative": ReasoningGenerator._competitor_detail,
            "time_based": ReasoningGenerator._time_based_detail,
            "volume_surge": ReasoningGenerator._volume_detail,
            "viral_detection": ReasoningGenerator._viral_detail,
        }

        generator = generators.get(rule_type)
        if generator:
            return generator(match_details)

        return f"Rule '{rule.name}' triggered."

    @staticmethod
    def _sentiment_detail(details: dict) -> str:
        sentiment = details.get("sentiment_score", 0)
        threshold = details.get("threshold", 0)
        direction = "above" if details.get("direction") == "above" else "below"
        return f"Sentiment score ({sentiment:.2f}) is {direction} threshold ({threshold})."

    @staticmethod
    def _competitor_detail(details: dict) -> str:
        comp_price = details.get("competitor_price", 0)
        return f"Adjusting relative to competitor price (${comp_price:.2f})."

    @staticmethod
    def _time_based_detail(details: dict) -> str:
        days = details.get("allowed_days", [])
        return f"Time-based rule active ({', '.join(days)})."

    @staticmethod
    def _volume_detail(details: dict) -> str:
        count = details.get("mention_count", 0)
        threshold = details.get("threshold", 0)
        return f"Volume surge detected ({count} mentions, threshold: {threshold})."

    @staticmethod
    def _viral_detail(details: dict) -> str:
        reach = details.get("reach", 0)
        return f"Viral content detected (reach: {reach:,})."
