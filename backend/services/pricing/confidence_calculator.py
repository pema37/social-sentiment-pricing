# backend/services/pricing/confidence_calculator.py
"""
Confidence Calculator - Calculates confidence scores for price recommendations.
"""

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from .rule_evaluator import MarketSignals


class ConfidenceCalculator:
    """
    Calculates confidence score (0.0-1.0) based on:
    - Data quality: How much data do we have?
    - Signal agreement: Do all signals point same direction?
    - Historical accuracy: How well has this rule type performed?
    - Market stability: How volatile is the market?
    """
    
    MIN_MENTIONS_FOR_HIGH_CONFIDENCE = 100
    MIN_MENTIONS_FOR_MEDIUM_CONFIDENCE = 25
    
    # Volatility thresholds
    LOW_VOLATILITY_THRESHOLD = Decimal("0.05")    # <5% = stable
    HIGH_VOLATILITY_THRESHOLD = Decimal("0.15")   # >15% = volatile
    
    def __init__(self, db: Session = None):
        self.db = db
    
    def calculate(
        self,
        signals: MarketSignals,
        price_impacts: dict,
        triggered_rule_type: Optional[str] = None,
        user_id: Optional[UUID] = None,
        product_id: Optional[UUID] = None
    ) -> Decimal:
        """Calculate overall confidence score."""
        
        data_quality = self._score_data_quality(signals)
        signal_agreement = self._score_signal_agreement(price_impacts)
        rule_confidence = self._score_rule_confidence(triggered_rule_type, signals)
        historical_accuracy = self._score_historical_accuracy(triggered_rule_type, user_id)
        market_stability = self._score_market_stability(product_id)
        
        # Weighted average (5 factors)
        confidence = (
            data_quality * Decimal("0.25") +
            signal_agreement * Decimal("0.25") +
            rule_confidence * Decimal("0.15") +
            historical_accuracy * Decimal("0.15") +
            market_stability * Decimal("0.20")
        )
        
        confidence = max(Decimal("0.0"), min(Decimal("1.0"), confidence))
        return confidence.quantize(Decimal("0.01"))
    
    def _score_data_quality(self, signals: MarketSignals) -> Decimal:
        """Score based on amount and completeness of data."""
        score = Decimal("0.0")
        
        if signals.mention_count_24h >= self.MIN_MENTIONS_FOR_HIGH_CONFIDENCE:
            score += Decimal("0.4")
        elif signals.mention_count_24h >= self.MIN_MENTIONS_FOR_MEDIUM_CONFIDENCE:
            score += Decimal("0.25")
        elif signals.mention_count_24h > 0:
            score += Decimal("0.1")
        
        if signals.sentiment_score is not None:
            score += Decimal("0.2")
            if signals.sentiment_change_24h is not None:
                score += Decimal("0.1")
        
        if signals.competitor_prices:
            if len(signals.competitor_prices) >= 3:
                score += Decimal("0.3")
            elif len(signals.competitor_prices) >= 1:
                score += Decimal("0.2")
        
        return min(score, Decimal("1.0"))
    
    def _score_signal_agreement(self, price_impacts: dict) -> Decimal:
        """Score based on whether signals agree on direction."""
        contributions = []
        
        for key, impact in price_impacts.items():
            if key == "total_contribution_percent":
                continue
            if isinstance(impact, dict) and "contribution_percent" in impact:
                contributions.append(impact["contribution_percent"])
        
        if not contributions:
            return Decimal("0.5")
        
        positive = sum(1 for c in contributions if c > 0)
        negative = sum(1 for c in contributions if c < 0)
        
        total = len(contributions)
        
        if positive == total or negative == total:
            return Decimal("1.0")
        
        majority = max(positive, negative)
        agreement_ratio = majority / total
        
        if agreement_ratio >= 0.75:
            return Decimal("0.8")
        elif agreement_ratio >= 0.5:
            return Decimal("0.6")
        else:
            return Decimal("0.3")
    
    def _score_rule_confidence(
        self,
        rule_type: Optional[str],
        signals: MarketSignals
    ) -> Decimal:
        """Score based on rule type and supporting data."""
        
        if rule_type is None:
            return Decimal("0.5")
        
        if rule_type == "sentiment_threshold":
            if signals.mention_count_24h >= self.MIN_MENTIONS_FOR_HIGH_CONFIDENCE:
                return Decimal("0.9")
            elif signals.mention_count_24h >= self.MIN_MENTIONS_FOR_MEDIUM_CONFIDENCE:
                return Decimal("0.7")
            return Decimal("0.5")
        
        elif rule_type == "competitor_relative":
            if signals.competitor_prices:
                return Decimal("0.95")
            return Decimal("0.3")
        
        elif rule_type == "time_based":
            return Decimal("1.0")
        
        elif rule_type == "volume_surge":
            if signals.mention_baseline > 0:
                surge_ratio = signals.mention_count_24h / signals.mention_baseline
                if surge_ratio >= 3.0:
                    return Decimal("0.9")
                elif surge_ratio >= 2.0:
                    return Decimal("0.75")
                return Decimal("0.6")
            return Decimal("0.5")
        
        elif rule_type == "viral_detection":
            if signals.viral_reach >= 100000:
                return Decimal("0.9")
            elif signals.viral_reach >= 50000:
                return Decimal("0.75")
            return Decimal("0.6")
        
        return Decimal("0.5")
    
    def _score_historical_accuracy(
        self,
        rule_type: Optional[str],
        user_id: Optional[UUID]
    ) -> Decimal:
        """Score based on historical accuracy of this rule type."""
        
        if not self.db or not rule_type or not user_id:
            return Decimal("0.5")
        
        from services.pricing.outcome_service import OutcomeService
        
        service = OutcomeService(self.db)
        return service.get_historical_accuracy_for_rule_type(user_id, rule_type)
    
    def _score_market_stability(self, product_id: Optional[UUID]) -> Decimal:
        """
        Score based on market stability (price and sentiment volatility).
        
        Low volatility = high confidence (stable market)
        High volatility = low confidence (unpredictable market)
        """
        if not self.db or not product_id:
            return Decimal("0.5")
        
        price_volatility = self._calculate_price_volatility(product_id)
        sentiment_volatility = self._calculate_sentiment_volatility(product_id)
        
        # Combine volatilities (price weighted more)
        combined_volatility = (
            price_volatility * Decimal("0.6") +
            sentiment_volatility * Decimal("0.4")
        )
        
        # Convert volatility to stability score (inverse relationship)
        if combined_volatility <= self.LOW_VOLATILITY_THRESHOLD:
            return Decimal("1.0")  # Very stable
        elif combined_volatility >= self.HIGH_VOLATILITY_THRESHOLD:
            return Decimal("0.3")  # Very volatile
        else:
            # Linear interpolation between thresholds
            range_size = self.HIGH_VOLATILITY_THRESHOLD - self.LOW_VOLATILITY_THRESHOLD
            position = (combined_volatility - self.LOW_VOLATILITY_THRESHOLD) / range_size
            score = Decimal("1.0") - (position * Decimal("0.7"))
            return score.quantize(Decimal("0.01"))
    
    def _calculate_price_volatility(self, product_id: UUID, days: int = 14) -> Decimal:
        """
        Calculate price volatility as coefficient of variation.
        Returns value between 0 and 1 (capped).
        """
        from models.price_history import PriceHistory
        
        cutoff = datetime.now(UTC) - timedelta(days=days)
        
        history = self.db.exec(
            select(PriceHistory)
            .where(
                PriceHistory.product_id == product_id,
                PriceHistory.created_at >= cutoff
            )
            .order_by(PriceHistory.created_at.desc())
        ).all()
        
        if len(history) < 3:
            return Decimal("0.05")  # Not enough data, assume stable
        
        # Get price changes
        prices = [h.new_price for h in history]
        
        # Calculate mean
        mean_price = sum(prices) / len(prices)
        if mean_price == 0:
            return Decimal("0.05")
        
        # Calculate standard deviation
        variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
        std_dev = variance ** Decimal("0.5")
        
        # Coefficient of variation
        cv = std_dev / mean_price
        
        # Cap at 0.5 (50% volatility is extreme)
        return min(cv, Decimal("0.5")).quantize(Decimal("0.01"))
    
    def _calculate_sentiment_volatility(self, product_id: UUID, days: int = 7) -> Decimal:
        """
        Calculate sentiment volatility from recent sentiment scores.
        Returns value between 0 and 1 (capped).
        """
        from models.sentiment import Sentiment
        
        cutoff = datetime.now(UTC) - timedelta(days=days)
        
        sentiments = self.db.exec(
            select(Sentiment)
            .where(
                Sentiment.product_id == product_id,
                Sentiment.analyzed_at >= cutoff
            )
            .order_by(Sentiment.analyzed_at.desc())
            .limit(100)
        ).all()
        
        if len(sentiments) < 5:
            return Decimal("0.05")  # Not enough data, assume stable
        
        scores = [s.compound_score for s in sentiments]
        
        # Calculate mean
        mean_score = sum(scores) / len(scores)
        
        # Calculate standard deviation
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        std_dev = variance ** Decimal("0.5")
        
        # Sentiment is -1 to 1, so normalize std_dev
        # Max possible std_dev is ~1 (if scores swing from -1 to 1)
        volatility = std_dev / Decimal("2")  # Normalize to 0-0.5 range
        
        return min(volatility, Decimal("0.5")).quantize(Decimal("0.01"))
    
    def get_confidence_breakdown(
        self,
        signals: MarketSignals,
        price_impacts: dict,
        triggered_rule_type: Optional[str] = None,
        user_id: Optional[UUID] = None,
        product_id: Optional[UUID] = None
    ) -> dict:
        """Get detailed breakdown of confidence calculation."""
        
        data_quality = self._score_data_quality(signals)
        signal_agreement = self._score_signal_agreement(price_impacts)
        rule_confidence = self._score_rule_confidence(triggered_rule_type, signals)
        historical_accuracy = self._score_historical_accuracy(triggered_rule_type, user_id)
        market_stability = self._score_market_stability(product_id)
        
        overall = self.calculate(signals, price_impacts, triggered_rule_type, user_id, product_id)
        
        # Get volatility details if available
        price_volatility = None
        sentiment_volatility = None
        if self.db and product_id:
            price_volatility = float(self._calculate_price_volatility(product_id))
            sentiment_volatility = float(self._calculate_sentiment_volatility(product_id))
        
        return {
            "overall": float(overall),
            "components": {
                "data_quality": {
                    "score": float(data_quality),
                    "weight": 0.25,
                    "factors": {
                        "mention_count_24h": signals.mention_count_24h,
                        "has_sentiment": signals.sentiment_score is not None,
                        "competitor_count": len(signals.competitor_prices),
                    }
                },
                "signal_agreement": {
                    "score": float(signal_agreement),
                    "weight": 0.25,
                },
                "rule_confidence": {
                    "score": float(rule_confidence),
                    "weight": 0.15,
                    "rule_type": triggered_rule_type,
                },
                "historical_accuracy": {
                    "score": float(historical_accuracy),
                    "weight": 0.15,
                },
                "market_stability": {
                    "score": float(market_stability),
                    "weight": 0.20,
                    "price_volatility": price_volatility,
                    "sentiment_volatility": sentiment_volatility,
                }
            }
        }


