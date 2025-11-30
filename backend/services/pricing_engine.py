# backend/services/pricing_engine.py

"""
Enhanced Pricing Engine with Competitor Analysis

This is the upgraded pricing engine that factors in:
1. Social sentiment (Phase 1)
2. Competitor pricing (Phase 2)

The engine provides weighted suggestions based on multiple market signals.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.models.product import Product


@dataclass
class CompetitorPriceData:
    """Competitor price information for pricing decisions."""
    competitor_name: str
    competitor_price: Decimal
    price_difference: Decimal  # positive = we're higher
    price_difference_percent: Decimal
    last_updated: datetime
    is_promotion: bool = False


@dataclass
class PriceSuggestion:
    """Complete price suggestion with all factors."""
    product_id: str
    current_price: Decimal
    suggested_price: Decimal
    change_percent: Decimal
    reasoning: str
    confidence: Decimal
    factors: Dict
    competitor_analysis: Optional[Dict] = None


class PricingEngine:
    """
    Intelligent pricing engine that combines sentiment and competitor data.
    
    Weighting Strategy:
    - Sentiment weight: How much social sentiment affects price (default 60%)
    - Competitor weight: How much competitor prices affect price (default 40%)
    
    These weights can be adjusted per product or globally.
    """

    def __init__(
        self,
        default_multiplier: Decimal = Decimal("0.1"),
        min_change_percent: Decimal = Decimal("1.0"),
        max_change_percent: Decimal = Decimal("15.0"),
        sentiment_weight: Decimal = Decimal("0.6"),
        competitor_weight: Decimal = Decimal("0.4"),
    ):
        self.default_multiplier = default_multiplier
        self.min_change_percent = min_change_percent
        self.max_change_percent = max_change_percent
        self.sentiment_weight = sentiment_weight
        self.competitor_weight = competitor_weight

    def calculate_suggestion(
        self,
        product: Product,
        sentiment_score: Decimal,
        mention_volume: int = 0,
        competitor_prices: Optional[List[CompetitorPriceData]] = None,
    ) -> Dict:
        """
        Calculate a price suggestion based on sentiment and competitor data.
        
        Args:
            product: The product to price
            sentiment_score: Compound sentiment (-1 to +1)
            mention_volume: Number of mentions analyzed
            competitor_prices: List of competitor price data (optional)
            
        Returns:
            Complete suggestion with reasoning and factors
        """
        current_price = product.current_price
        base_price = product.base_price
        multiplier = product.sentiment_multiplier or self.default_multiplier

        # ============================================================
        # PHASE 1: Sentiment-based adjustment
        # ============================================================
        sentiment_adjustment = self._calculate_sentiment_adjustment(
            base_price=base_price,
            current_price=current_price,
            sentiment_score=sentiment_score,
            multiplier=multiplier,
        )

        # ============================================================
        # PHASE 2: Competitor-based adjustment
        # ============================================================
        competitor_adjustment = Decimal("0")
        competitor_analysis = None

        if competitor_prices:
            competitor_adjustment, competitor_analysis = self._calculate_competitor_adjustment(
                current_price=current_price,
                competitor_prices=competitor_prices,
            )

        # ============================================================
        # Combine adjustments with weights
        # ============================================================
        if competitor_prices:
            # Use weighted average when we have competitor data
            combined_adjustment = (
                sentiment_adjustment * self.sentiment_weight +
                competitor_adjustment * self.competitor_weight
            )
        else:
            # Sentiment only when no competitor data
            combined_adjustment = sentiment_adjustment

        # Calculate percentage change
        if current_price > 0:
            change_percent = (combined_adjustment / current_price) * 100
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

        # Calculate confidence
        confidence = self._calculate_confidence(
            mention_volume=mention_volume,
            has_competitor_data=bool(competitor_prices),
            competitor_count=len(competitor_prices) if competitor_prices else 0,
        )

        # Generate reasoning
        reasoning = self._generate_reasoning(
            sentiment_score=sentiment_score,
            mention_volume=mention_volume,
            change_percent=actual_change_percent,
            competitor_analysis=competitor_analysis,
        )

        return {
            "product_id": str(product.id),
            "current_price": current_price,
            "suggested_price": suggested_price,
            "change_percent": actual_change_percent,
            "reasoning": reasoning,
            "confidence": confidence,
            "factors": {
                "sentiment_score": sentiment_score,
                "mention_volume": mention_volume,
                "multiplier": multiplier,
                "trend": self._get_trend(sentiment_score),
                "sentiment_weight": self.sentiment_weight,
                "competitor_weight": self.competitor_weight if competitor_prices else Decimal("0"),
                "sentiment_adjustment_raw": sentiment_adjustment,
                "competitor_adjustment_raw": competitor_adjustment,
            },
            "competitor_analysis": competitor_analysis,
        }

    def _calculate_sentiment_adjustment(
        self,
        base_price: Decimal,
        current_price: Decimal,
        sentiment_score: Decimal,
        multiplier: Decimal,
    ) -> Decimal:
        """Calculate price adjustment from sentiment alone."""
        return base_price * sentiment_score * multiplier

    def _calculate_competitor_adjustment(
        self,
        current_price: Decimal,
        competitor_prices: List[CompetitorPriceData],
    ) -> tuple[Decimal, Dict]:
        """
        Calculate price adjustment based on competitor positioning.
        
        Strategy:
        - If we're significantly higher than average → suggest decrease
        - If we're significantly lower than average → suggest increase (capture margin)
        - If competitors are running promotions → be cautious about increases
        """
        if not competitor_prices:
            return Decimal("0"), None

        # Calculate competitor price statistics
        prices = [cp.competitor_price for cp in competitor_prices]
        avg_competitor_price = sum(prices) / len(prices)
        min_competitor_price = min(prices)
        max_competitor_price = max(prices)

        # How much higher/lower are we vs average?
        price_gap = current_price - avg_competitor_price
        price_gap_percent = (price_gap / avg_competitor_price * 100) if avg_competitor_price > 0 else Decimal("0")

        # Determine our market position
        if current_price <= min_competitor_price:
            position = "lowest"
        elif current_price >= max_competitor_price:
            position = "highest"
        else:
            position = "middle"

        # Check for active promotions
        promotion_count = sum(1 for cp in competitor_prices if cp.is_promotion)
        promotion_pressure = promotion_count / len(competitor_prices)

        # Calculate adjustment
        # Target: aim for slightly below average (competitive but profitable)
        target_price = avg_competitor_price * Decimal("0.98")  # 2% below average
        adjustment = target_price - current_price

        # Reduce adjustment if competitors have promotions (don't chase temporary drops)
        if promotion_pressure > 0.5:
            adjustment = adjustment * Decimal("0.5")

        # Build analysis object
        analysis = {
            "competitor_count": len(competitor_prices),
            "average_price": avg_competitor_price.quantize(Decimal("0.01")),
            "min_price": min_competitor_price,
            "max_price": max_competitor_price,
            "your_position": position,
            "price_gap": price_gap.quantize(Decimal("0.01")),
            "price_gap_percent": price_gap_percent.quantize(Decimal("0.01")),
            "active_promotions": promotion_count,
            "promotion_pressure": Decimal(str(promotion_pressure)).quantize(Decimal("0.01")),
            "competitors": [
                {
                    "name": cp.competitor_name,
                    "price": cp.competitor_price,
                    "difference": cp.price_difference.quantize(Decimal("0.01")),
                    "is_promotion": cp.is_promotion,
                }
                for cp in competitor_prices
            ],
        }

        return adjustment, analysis

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

    def _calculate_confidence(
        self,
        mention_volume: int,
        has_competitor_data: bool,
        competitor_count: int,
    ) -> Decimal:
        """
        Calculate confidence score based on data quality.
        
        More data = higher confidence.
        """
        # Base confidence from sentiment volume
        if mention_volume == 0:
            sentiment_confidence = Decimal("0.1")
        elif mention_volume < 10:
            sentiment_confidence = Decimal("0.3")
        elif mention_volume < 50:
            sentiment_confidence = Decimal("0.5")
        elif mention_volume < 100:
            sentiment_confidence = Decimal("0.7")
        elif mention_volume < 500:
            sentiment_confidence = Decimal("0.85")
        else:
            sentiment_confidence = Decimal("0.95")

        # Boost confidence if we have competitor data
        if has_competitor_data:
            competitor_boost = min(Decimal("0.15"), Decimal(str(competitor_count)) * Decimal("0.05"))
            confidence = min(Decimal("0.99"), sentiment_confidence + competitor_boost)
        else:
            confidence = sentiment_confidence

        return confidence.quantize(Decimal("0.01"))

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
        change_percent: Decimal,
        competitor_analysis: Optional[Dict],
    ) -> str:
        """Generate human-readable reasoning for the suggestion."""
        parts = []

        # Sentiment part
        if mention_volume == 0:
            parts.append("Limited sentiment data available.")
        else:
            sentiment_desc = "Positive" if sentiment_score > 0 else "Negative"
            if abs(sentiment_score) < Decimal("0.1"):
                sentiment_desc = "Neutral"
            parts.append(
                f"{sentiment_desc} sentiment ({sentiment_score:+.2f}) "
                f"from {mention_volume} mentions."
            )

        # Competitor part
        if competitor_analysis:
            position = competitor_analysis["your_position"]
            gap = competitor_analysis["price_gap_percent"]
            
            if position == "highest":
                parts.append(f"Currently priced highest among {competitor_analysis['competitor_count']} competitors ({gap:+.1f}% vs average).")
            elif position == "lowest":
                parts.append(f"Currently priced lowest among {competitor_analysis['competitor_count']} competitors ({gap:+.1f}% vs average).")
            else:
                parts.append(f"Competitively positioned ({gap:+.1f}% vs {competitor_analysis['competitor_count']} competitors).")

            if competitor_analysis["active_promotions"] > 0:
                parts.append(f"Note: {competitor_analysis['active_promotions']} competitor(s) running promotions.")

        # Recommendation part
        if change_percent == 0:
            parts.append("No price adjustment recommended at this time.")
        else:
            direction = "increase" if change_percent > 0 else "decrease"
            parts.append(f"Suggested {direction} of {abs(change_percent):.1f}%.")

        return " ".join(parts)

    # ============================================================
    # Competitor-specific analysis methods
    # ============================================================

    def get_competitive_position(
        self,
        current_price: Decimal,
        competitor_prices: List[CompetitorPriceData],
    ) -> Dict:
        """
        Analyze competitive positioning without making a price suggestion.
        Useful for dashboards and reports.
        """
        if not competitor_prices:
            return {
                "position": "no_data",
                "message": "No competitor data available",
            }

        prices = [cp.competitor_price for cp in competitor_prices]
        avg_price = sum(prices) / len(prices)
        
        sorted_all = sorted(prices + [current_price])
        rank = sorted_all.index(current_price) + 1
        total = len(sorted_all)

        return {
            "your_price": current_price,
            "competitor_count": len(competitor_prices),
            "average_competitor_price": avg_price.quantize(Decimal("0.01")),
            "min_competitor_price": min(prices),
            "max_competitor_price": max(prices),
            "your_rank": rank,
            "total_in_market": total,
            "percentile": ((total - rank) / total * 100) if total > 0 else 0,
            "vs_average_percent": ((current_price - avg_price) / avg_price * 100).quantize(Decimal("0.01")),
        }

    def detect_price_war(
        self,
        competitor_prices: List[CompetitorPriceData],
        lookback_days: int = 7,
    ) -> Dict:
        """
        Detect if competitors are engaged in aggressive pricing.
        
        Indicators:
        - Multiple recent price drops
        - Prices below apparent cost
        - Rapid back-and-forth changes
        """
        if not competitor_prices:
            return {"detected": False, "reason": "No competitor data"}

        promotion_count = sum(1 for cp in competitor_prices if cp.is_promotion)
        promotion_rate = promotion_count / len(competitor_prices)

        # Simple heuristic: >50% of competitors on promotion suggests price war
        if promotion_rate > 0.5:
            return {
                "detected": True,
                "severity": "high" if promotion_rate > 0.75 else "medium",
                "promotion_rate": promotion_rate,
                "recommendation": "Hold prices steady. Avoid chasing temporary promotions.",
            }

        return {
            "detected": False,
            "promotion_rate": promotion_rate,
            "recommendation": "Normal market conditions.",
        }


# Singleton instance for easy imports
pricing_engine = PricingEngine()

