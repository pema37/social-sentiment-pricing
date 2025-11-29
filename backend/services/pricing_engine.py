# backend/services/pricing_engine.py

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional

from backend.models.product import Product


class PricingEngine:
    """
    Calculates price suggestions based on sentiment analysis.
    
    Formula:
        price_change = base_price * sentiment_score * sentiment_multiplier
        suggested_price = current_price + price_change
    
    Constrained by min_price and max_price boundaries.
    """

    def __init__(
        self,
        default_multiplier: Decimal = Decimal("0.1"),
        min_change_percent: Decimal = Decimal("1.0"),
        max_change_percent: Decimal = Decimal("15.0")
    ):
        self.default_multiplier = default_multiplier
        self.min_change_percent = min_change_percent
        self.max_change_percent = max_change_percent

    def calculate_suggestion(
        self,
        product: Product,
        sentiment_score: Decimal,
        mention_volume: int = 0
    ) -> Dict:
        """
        Calculate a price suggestion based on sentiment.
        
        Args:
            product: The product to price
            sentiment_score: Compound sentiment (-1 to +1)
            mention_volume: Number of mentions analyzed
            
        Returns:
            {
                "product_id": str,
                "current_price": Decimal,
                "suggested_price": Decimal,
                "change_percent": Decimal,
                "reasoning": str,
                "confidence": Decimal,
                "factors": dict
            }
        """
        current_price = product.current_price
        base_price = product.base_price
        multiplier = product.sentiment_multiplier or self.default_multiplier

        # Calculate raw price change
        price_change = base_price * sentiment_score * multiplier

        # Calculate percentage change
        if current_price > 0:
            change_percent = (price_change / current_price) * 100
        else:
            change_percent = Decimal("0")

        # Clamp change to min/max percent
        change_percent = self._clamp_change(change_percent)

        # Calculate suggested price
        suggested_price = current_price * (1 + change_percent / 100)

        # Apply min/max price boundaries
        suggested_price = self._apply_boundaries(
            suggested_price,
            product.min_price,
            product.max_price
        )

        # Round to 2 decimal places
        suggested_price = suggested_price.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # Recalculate actual change after boundaries
        if current_price > 0:
            actual_change_percent = ((suggested_price - current_price) / current_price) * 100
        else:
            actual_change_percent = Decimal("0")

        actual_change_percent = actual_change_percent.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # Calculate confidence based on mention volume
        confidence = self._calculate_confidence(mention_volume)

        # Generate reasoning
        reasoning = self._generate_reasoning(
            sentiment_score,
            mention_volume,
            actual_change_percent
        )

        return {
            "product_id": product.id,
            "current_price": current_price,
            "suggested_price": suggested_price,
            "change_percent": actual_change_percent,
            "reasoning": reasoning,
            "confidence": confidence,
            "factors": {
                "sentiment_score": sentiment_score,
                "mention_volume": mention_volume,
                "multiplier": multiplier,
                "trend": self._get_trend(sentiment_score)
            }
        }

    def _clamp_change(self, change_percent: Decimal) -> Decimal:
        """Clamp change to configured min/max."""
        if abs(change_percent) < self.min_change_percent:
            return Decimal("0")
        if change_percent > self.max_change_percent:
            return self.max_change_percent
        if change_percent < -self.max_change_percent:
            return -self.max_change_percent
        return change_percent

    def _apply_boundaries(
        self,
        price: Decimal,
        min_price: Optional[Decimal],
        max_price: Optional[Decimal]
    ) -> Decimal:
        """Apply min/max price boundaries."""
        if min_price and price < min_price:
            return min_price
        if max_price and price > max_price:
            return max_price
        return price

    def _calculate_confidence(self, mention_volume: int) -> Decimal:
        """
        Calculate confidence score based on data volume.
        More mentions = higher confidence.
        """
        if mention_volume == 0:
            return Decimal("0.1")
        elif mention_volume < 10:
            return Decimal("0.3")
        elif mention_volume < 50:
            return Decimal("0.5")
        elif mention_volume < 100:
            return Decimal("0.7")
        elif mention_volume < 500:
            return Decimal("0.85")
        else:
            return Decimal("0.95")

    def _get_trend(self, sentiment_score: Decimal) -> str:
        """Determine trend from sentiment score."""
        if sentiment_score > Decimal("0.1"):
            return "rising"
        elif sentiment_score < Decimal("-0.1"):
            return "falling"
        return "stable"

    def _generate_reasoning(
        self,
        sentiment_score: Decimal,
        mention_volume: int,
        change_percent: Decimal
    ) -> str:
        """Generate human-readable reasoning for the suggestion."""
        if mention_volume == 0:
            return "Insufficient data. No recent mentions found for analysis."

        sentiment_desc = "Positive" if sentiment_score > 0 else "Negative"
        if abs(sentiment_score) < Decimal("0.1"):
            sentiment_desc = "Neutral"

        if change_percent == 0:
            return (
                f"{sentiment_desc} sentiment ({sentiment_score:+.2f}) detected "
                f"across {mention_volume} mentions. Change too small to recommend adjustment."
            )

        direction = "increase" if change_percent > 0 else "decrease"
        return (
            f"{sentiment_desc} sentiment ({sentiment_score:+.2f}) detected "
            f"across {mention_volume} mentions. Market momentum suggests "
            f"price {direction} opportunity."
        )


# Singleton instance
pricing_engine = PricingEngine()

