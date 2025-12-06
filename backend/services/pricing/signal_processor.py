# backend/services/pricing/signal_processor.py
"""
Signal Processor - Gathers and processes market signals for pricing decisions.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from backend.models.product import Product
from backend.models.sentiment import Sentiment
from backend.models.social_mention import SocialMention
from backend.models.competitor_product import CompetitorProduct

from .rule_evaluator import MarketSignals


class SignalProcessor:
    """Gathers all market signals for a product."""
    
    # Trend detection thresholds
    TRENDING_GROWTH_THRESHOLD = Decimal("0.5")  # 50% growth = trending
    STRONG_TREND_THRESHOLD = Decimal("1.0")     # 100% growth = strong trend
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def gather_signals(self, product: Product) -> MarketSignals:
        """Gather all market signals for a product."""
        
        sentiment_score, sentiment_change = await self._get_sentiment_signals(product.id)
        mention_count, mention_baseline = await self._get_volume_signals(product.id)
        viral_detected, viral_reach, viral_engagement, viral_sentiment = await self._get_viral_signals(product.id)
        competitor_prices = await self._get_competitor_prices(product.id)
        
        # Get trend signals
        trend_data = await self._get_trend_signals(product.id)
        
        return MarketSignals(
            sentiment_score=sentiment_score,
            sentiment_change_24h=sentiment_change,
            mention_count_24h=mention_count,
            mention_baseline=mention_baseline,
            viral_detected=viral_detected,
            viral_reach=viral_reach,
            viral_engagement=viral_engagement,
            viral_sentiment=viral_sentiment,
            competitor_prices=competitor_prices,
            # Trend signals
            trend_direction=trend_data["direction"],
            trend_strength=trend_data["strength"],
            trend_velocity=trend_data["velocity"],
            mention_growth_rate=trend_data["mention_growth_rate"],
            sentiment_momentum=trend_data["sentiment_momentum"],
            is_trending=trend_data["is_trending"],
        )
    
    async def _get_sentiment_signals(self, product_id: UUID) -> tuple[Optional[Decimal], Optional[Decimal]]:
        """Get current sentiment and 24h change."""
        
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_48h = now - timedelta(hours=48)
        
        # Current sentiment (last 24h average)
        current_stmt = select(func.avg(Sentiment.compound_score)).where(
            Sentiment.product_id == product_id,
            Sentiment.analyzed_at >= last_24h
        )
        result = await self.db.execute(current_stmt)
        current_avg = result.scalar()
        
        if current_avg is None:
            return None, None
        
        current_score = Decimal(str(current_avg)).quantize(Decimal("0.001"))
        
        # Previous 24h sentiment
        prev_stmt = select(func.avg(Sentiment.compound_score)).where(
            Sentiment.product_id == product_id,
            Sentiment.analyzed_at >= last_48h,
            Sentiment.analyzed_at < last_24h
        )
        result = await self.db.execute(prev_stmt)
        prev_avg = result.scalar()
        
        if prev_avg is None:
            return current_score, None
        
        prev_score = Decimal(str(prev_avg)).quantize(Decimal("0.001"))
        change = current_score - prev_score
        
        return current_score, change.quantize(Decimal("0.001"))
    
    def calculate_price_impact(self, signals: MarketSignals, product: Product) -> dict:
        """Calculate price impact factors from signals."""
        impacts = {}
        
        # Sentiment impact
        if signals.sentiment_score is not None:
            sentiment_impact = (signals.sentiment_score - Decimal("0.5")) * Decimal("10")  # -5 to +5%
            impacts["sentiment"] = float(sentiment_impact)
        
        # Volume impact
        if signals.mention_baseline > 0:
            volume_ratio = signals.mention_count_24h / signals.mention_baseline
            volume_impact = (Decimal(str(volume_ratio)) - 1) * Decimal("5")  # % impact
            impacts["volume"] = float(volume_impact)
        
        # Viral impact
        if signals.viral_detected:
            impacts["viral"] = 5.0  # +5% for viral content
        
        # Trend impact
        if signals.is_trending:
            impacts["trend"] = float(signals.trend_strength * Decimal("3"))
        
        return impacts

    async def _get_volume_signals(self, product_id: UUID) -> tuple[int, int]:
        """Get mention count and baseline."""
        
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        # Count last 24h
        count_stmt = select(func.count(SocialMention.id)).where(
            SocialMention.product_id == product_id,
            SocialMention.published_at >= last_24h
        )
        result = await self.db.execute(count_stmt)
        count_24h = result.scalar() or 0
        
        # Average daily count over last 7 days
        baseline_stmt = select(func.count(SocialMention.id)).where(
            SocialMention.product_id == product_id,
            SocialMention.published_at >= last_7d,
            SocialMention.published_at < last_24h
        )
        result = await self.db.execute(baseline_stmt)
        total_6d = result.scalar() or 0
        baseline = total_6d // 6 if total_6d > 0 else 0
        
        return count_24h, baseline
    
    async def _get_viral_signals(self, product_id: UUID) -> tuple[bool, int, int, Optional[Decimal]]:
        """Detect viral content."""
        
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        
        # Find high-engagement posts
        stmt = select(SocialMention).where(
            SocialMention.product_id == product_id,
            SocialMention.published_at >= last_24h
        ).order_by(SocialMention.engagement_count.desc()).limit(10)
        
        result = await self.db.execute(stmt)
        top_posts = list(result.scalars().all())
        
        if not top_posts:
            return False, 0, 0, None
        
        total_reach = sum(p.author_followers or 0 for p in top_posts)
        total_engagement = sum(p.engagement_count or 0 for p in top_posts)
        
        # Viral threshold: reach > 10000 or engagement > 1000
        viral_detected = total_reach > 10000 or total_engagement > 1000
        
        # Get sentiment of viral posts
        viral_sentiment = None
        if viral_detected and top_posts:
            sentiments = []
            for post in top_posts[:5]:
                sent_stmt = select(Sentiment).where(
                    Sentiment.product_id == product_id
                ).order_by(Sentiment.analyzed_at.desc()).limit(1)
                result = await self.db.execute(sent_stmt)
                sent = result.scalars().first()
                if sent:
                    sentiments.append(sent.compound_score)
            
            if sentiments:
                viral_sentiment = sum(sentiments) / len(sentiments)
        
        return viral_detected, total_reach, total_engagement, viral_sentiment
    
    async def _get_competitor_prices(self, product_id: UUID) -> dict[UUID, Decimal]:
        """Get current competitor prices for the product."""
        
        stmt = select(CompetitorProduct).where(
            CompetitorProduct.product_id == product_id,
            CompetitorProduct.is_active == True
        )
        
        result = await self.db.execute(stmt)
        competitor_products = result.scalars().all()
        
        prices = {}
        for cp in competitor_products:
            if cp.current_price:
                prices[cp.competitor_id] = cp.current_price
        
        return prices
    
    async def _get_trend_signals(self, product_id: UUID) -> dict:
        """
        Calculate trend signals for a product.
        
        Analyzes:
        - Mention growth rate (comparing periods)
        - Sentiment momentum (direction of sentiment change)
        - Overall trend strength and direction
        """
        
        # Get mentions by day for the last 7 days
        daily_mentions = await self._get_daily_mention_counts(product_id, days=7)
        
        # Get sentiment by day
        daily_sentiment = await self._get_daily_sentiment(product_id, days=7)
        
        # Calculate mention growth rate
        mention_growth_rate = self._calculate_growth_rate(daily_mentions)
        
        # Calculate sentiment momentum
        sentiment_momentum = self._calculate_momentum(daily_sentiment)
        
        # Determine trend direction and strength
        trend_direction, trend_strength = self._determine_trend(
            mention_growth_rate, sentiment_momentum
        )
        
        # Calculate velocity (rate of acceleration)
        trend_velocity = self._calculate_velocity(daily_mentions)
        
        # Is it trending?
        is_trending = mention_growth_rate >= self.TRENDING_GROWTH_THRESHOLD
        
        return {
            "direction": trend_direction,
            "strength": trend_strength,
            "velocity": trend_velocity,
            "mention_growth_rate": mention_growth_rate,
            "sentiment_momentum": sentiment_momentum,
            "is_trending": is_trending,
        }
    
    async def _get_daily_mention_counts(self, product_id: UUID, days: int = 7) -> list[int]:
        """Get mention counts for each of the last N days."""
        
        now = datetime.utcnow()
        counts = []
        
        for i in range(days):
            day_end = now - timedelta(days=i)
            day_start = now - timedelta(days=i+1)
            
            stmt = select(func.count(SocialMention.id)).where(
                SocialMention.product_id == product_id,
                SocialMention.published_at >= day_start,
                SocialMention.published_at < day_end
            )
            result = await self.db.execute(stmt)
            count = result.scalar() or 0
            counts.append(count)
        
        # Reverse so oldest is first
        return list(reversed(counts))
    
    async def _get_daily_sentiment(self, product_id: UUID, days: int = 7) -> list[Optional[Decimal]]:
        """Get average sentiment for each of the last N days."""
        
        now = datetime.utcnow()
        sentiments = []
        
        for i in range(days):
            day_end = now - timedelta(days=i)
            day_start = now - timedelta(days=i+1)
            
            stmt = select(func.avg(Sentiment.compound_score)).where(
                Sentiment.product_id == product_id,
                Sentiment.analyzed_at >= day_start,
                Sentiment.analyzed_at < day_end
            )
            result = await self.db.execute(stmt)
            avg = result.scalar()
            
            if avg is not None:
                sentiments.append(Decimal(str(avg)).quantize(Decimal("0.001")))
            else:
                sentiments.append(None)
        
        return list(reversed(sentiments))
    
    def _calculate_growth_rate(self, daily_counts: list[int]) -> Decimal:
        """
        Calculate growth rate comparing recent period to earlier period.
        Returns percentage change as Decimal.
        """
        if len(daily_counts) < 4:
            return Decimal("0")
        
        # Compare last 3 days to previous 3 days
        recent = sum(daily_counts[-3:])
        earlier = sum(daily_counts[-6:-3]) if len(daily_counts) >= 6 else sum(daily_counts[:3])
        
        if earlier == 0:
            if recent > 0:
                return Decimal("1.0")  # 100% growth from nothing
            return Decimal("0")
        
        growth = Decimal(str((recent - earlier) / earlier))
        return growth.quantize(Decimal("0.01"))
    
    def _calculate_momentum(self, daily_values: list[Optional[Decimal]]) -> Decimal:
        """
        Calculate momentum (direction and acceleration of change).
        Returns value between -1 and 1.
        """
        # Filter out None values
        valid_values = [v for v in daily_values if v is not None]
        
        if len(valid_values) < 3:
            return Decimal("0")
        
        # Calculate day-over-day changes
        changes = []
        for i in range(1, len(valid_values)):
            change = valid_values[i] - valid_values[i-1]
            changes.append(change)
        
        if not changes:
            return Decimal("0")
        
        # Average change direction
        avg_change = sum(changes) / len(changes)
        
        # Normalize to -1 to 1 range (assuming max change of 0.5 per day)
        momentum = avg_change / Decimal("0.5")
        momentum = max(Decimal("-1"), min(Decimal("1"), momentum))
        
        return momentum.quantize(Decimal("0.01"))
    
    def _calculate_velocity(self, daily_counts: list[int]) -> Decimal:
        """
        Calculate velocity (rate of acceleration).
        Returns value between 0 and 1.
        """
        if len(daily_counts) < 4:
            return Decimal("0")
        
        # Calculate day-over-day growth rates
        growth_rates = []
        for i in range(1, len(daily_counts)):
            if daily_counts[i-1] > 0:
                rate = (daily_counts[i] - daily_counts[i-1]) / daily_counts[i-1]
                growth_rates.append(rate)
        
        if len(growth_rates) < 2:
            return Decimal("0")
        
        # Calculate acceleration (change in growth rate)
        accelerations = []
        for i in range(1, len(growth_rates)):
            acc = growth_rates[i] - growth_rates[i-1]
            accelerations.append(acc)
        
        if not accelerations:
            return Decimal("0")
        
        avg_acceleration = sum(accelerations) / len(accelerations)
        
        # Normalize to 0-1 range
        velocity = Decimal(str(abs(avg_acceleration)))
        velocity = min(velocity, Decimal("1"))
        
        return velocity.quantize(Decimal("0.01"))
    
    def _determine_trend(
        self,
        growth_rate: Decimal,
        sentiment_momentum: Decimal
    ) -> tuple[str, Decimal]:
        """
        Determine overall trend direction and strength.
        
        Returns:
            (direction, strength) where direction is "up", "down", or "stable"
            and strength is 0-1.
        """
        # Combine growth rate and sentiment
        combined = (growth_rate * Decimal("0.7")) + (sentiment_momentum * Decimal("0.3"))
        
        # Determine direction
        if combined >= Decimal("0.1"):
            direction = "up"
        elif combined <= Decimal("-0.1"):
            direction = "down"
        else:
            direction = "stable"
        
        # Calculate strength (absolute value, capped at 1)
        strength = abs(combined)
        strength = min(strength, Decimal("1"))
        
        return direction, strength.quantize(Decimal("0.01"))
