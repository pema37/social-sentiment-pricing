# backend/services/analysis/sentiment_aggregator.py

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.social_mention import SocialMention


class SentimentAggregator:
    """
    Aggregates sentiment data for products, calculating weighted averages,
    trends, and velocity metrics used by the pricing engine.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_product_sentiment(
        self,
        product_id: UUID,
        hours: int = 24
    ) -> Dict:
        """
        Get aggregated sentiment for a product over a time window.
        
        Returns:
            {
                "product_id": str,
                "period_hours": int,
                "mention_count": int,
                "avg_sentiment": float,
                "weighted_sentiment": float,
                "positive_count": int,
                "negative_count": int,
                "neutral_count": int,
                "positive_ratio": float,
                "negative_ratio": float,
                "sentiment_label": str,
                "top_topics": list,
                "computed_at": str
            }
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        result = await self.db.execute(
            select(SocialMention)
            .where(SocialMention.product_id == product_id)
            .where(SocialMention.processed == True)
            .where(SocialMention.collected_at >= cutoff)
        )
        mentions = list(result.scalars().all())
        
        if not mentions:
            return self._empty_aggregation(product_id, hours)
        
        return self._calculate_aggregation(mentions, product_id, hours)
    
    async def get_user_sentiment(
        self,
        user_id: UUID,
        hours: int = 24
    ) -> Dict:
        """Get aggregated sentiment across all products for a user."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        result = await self.db.execute(
            select(SocialMention)
            .where(SocialMention.user_id == user_id)
            .where(SocialMention.processed == True)
            .where(SocialMention.collected_at >= cutoff)
        )
        mentions = list(result.scalars().all())
        
        if not mentions:
            return self._empty_aggregation(None, hours)
        
        return self._calculate_aggregation(mentions, None, hours)
    
    async def get_sentiment_velocity(
        self,
        product_id: UUID,
        current_hours: int = 6,
        previous_hours: int = 6
    ) -> Dict:
        """
        Calculate sentiment velocity (rate of change).
        
        Compares current period vs previous period to detect trends.
        
        Returns:
            {
                "current_sentiment": float,
                "previous_sentiment": float,
                "velocity": float,  # positive = improving, negative = declining
                "trend": str,  # "improving", "stable", "declining"
                "volume_change": float  # % change in mention volume
            }
        """
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(hours=current_hours)
        previous_start = current_start - timedelta(hours=previous_hours)
        
        # Current period
        result = await self.db.execute(
            select(SocialMention)
            .where(SocialMention.product_id == product_id)
            .where(SocialMention.processed == True)
            .where(SocialMention.collected_at >= current_start)
        )
        current_mentions = list(result.scalars().all())
        
        # Previous period
        result = await self.db.execute(
            select(SocialMention)
            .where(SocialMention.product_id == product_id)
            .where(SocialMention.processed == True)
            .where(SocialMention.collected_at >= previous_start)
            .where(SocialMention.collected_at < current_start)
        )
        previous_mentions = list(result.scalars().all())
        
        current_sentiment = self._avg_sentiment(current_mentions)
        previous_sentiment = self._avg_sentiment(previous_mentions)
        
        # Calculate velocity
        if previous_sentiment is not None and current_sentiment is not None:
            velocity = (current_sentiment - previous_sentiment) / current_hours
        else:
            velocity = 0.0
        
        # Determine trend
        if velocity > 0.02:
            trend = "improving"
        elif velocity < -0.02:
            trend = "declining"
        else:
            trend = "stable"
        
        # Volume change
        prev_count = len(previous_mentions)
        curr_count = len(current_mentions)
        
        if prev_count > 0:
            volume_change = (curr_count - prev_count) / prev_count
        else:
            volume_change = 1.0 if curr_count > 0 else 0.0
        
        return {
            "current_sentiment": current_sentiment or 0.0,
            "previous_sentiment": previous_sentiment or 0.0,
            "velocity": round(velocity, 4),
            "trend": trend,
            "current_count": curr_count,
            "previous_count": prev_count,
            "volume_change": round(volume_change, 2)
        }
    
    async def get_sentiment_by_source(
        self,
        product_id: UUID,
        hours: int = 24
    ) -> Dict:
        """Get sentiment breakdown by source (reddit, twitter, etc.)."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        result = await self.db.execute(
            select(SocialMention)
            .where(SocialMention.product_id == product_id)
            .where(SocialMention.processed == True)
            .where(SocialMention.collected_at >= cutoff)
        )
        mentions = list(result.scalars().all())
        
        # Group by source
        by_source: Dict[str, List[SocialMention]] = {}
        for mention in mentions:
            source = mention.source
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(mention)
        
        # Calculate per-source metrics
        source_results = {}
        for source, source_mentions in by_source.items():
            agg = self._calculate_aggregation(source_mentions, product_id, hours)
            source_results[source] = {
                "mention_count": agg["mention_count"],
                "avg_sentiment": agg["avg_sentiment"],
                "sentiment_label": agg["sentiment_label"]
            }
        
        return source_results
    
    # === SYNC HELPER METHODS (pure computation, no I/O) ===
    
    def _calculate_aggregation(
        self,
        mentions: List[SocialMention],
        product_id: Optional[UUID],
        hours: int
    ) -> Dict:
        """Calculate aggregation metrics from a list of mentions."""
        sentiments = []
        weighted_sentiments = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        all_topics = []
        
        for mention in mentions:
            raw_data = mention.raw_data or {}
            sentiment_data = raw_data.get("sentiment", {})
            
            score = sentiment_data.get("compound", 0)
            label = sentiment_data.get("label", "neutral")
            topics = sentiment_data.get("topics", [])
            
            sentiments.append(score)
            
            # Weight by engagement
            weight = 1 + (mention.engagement_count or 0) * 0.01
            weighted_sentiments.append(score * weight)
            
            # Count labels
            if "positive" in label:
                positive_count += 1
            elif "negative" in label:
                negative_count += 1
            else:
                neutral_count += 1
            
            all_topics.extend(topics)
        
        total = len(mentions)
        avg_sentiment = sum(sentiments) / total if sentiments else 0
        
        total_weight = sum(1 + (m.engagement_count or 0) * 0.01 for m in mentions)
        weighted_sentiment = sum(weighted_sentiments) / total_weight if total_weight > 0 else 0
        
        # Determine overall label
        if avg_sentiment > 0.3:
            sentiment_label = "positive"
        elif avg_sentiment < -0.3:
            sentiment_label = "negative"
        else:
            sentiment_label = "neutral"
        
        # Get top topics
        topic_counts: Dict[str, int] = {}
        for topic in all_topics:
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        top_topics = sorted(topic_counts.keys(), key=lambda x: topic_counts[x], reverse=True)[:5]
        
        return {
            "product_id": str(product_id) if product_id else None,
            "period_hours": hours,
            "mention_count": total,
            "avg_sentiment": round(avg_sentiment, 3),
            "weighted_sentiment": round(weighted_sentiment, 3),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "positive_ratio": round(positive_count / total, 2) if total > 0 else 0,
            "negative_ratio": round(negative_count / total, 2) if total > 0 else 0,
            "sentiment_label": sentiment_label,
            "top_topics": top_topics,
            "computed_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _empty_aggregation(self, product_id: Optional[UUID], hours: int) -> Dict:
        """Return empty aggregation when no data exists."""
        return {
            "product_id": str(product_id) if product_id else None,
            "period_hours": hours,
            "mention_count": 0,
            "avg_sentiment": 0.0,
            "weighted_sentiment": 0.0,
            "positive_count": 0,
            "negative_count": 0,
            "neutral_count": 0,
            "positive_ratio": 0.0,
            "negative_ratio": 0.0,
            "sentiment_label": "neutral",
            "top_topics": [],
            "computed_at": datetime.now(timezone.utc).isoformat()
        }
    
    def _avg_sentiment(self, mentions: List[SocialMention]) -> Optional[float]:
        """Calculate average sentiment from mentions."""
        if not mentions:
            return None
        
        scores = []
        for mention in mentions:
            raw_data = mention.raw_data or {}
            sentiment_data = raw_data.get("sentiment", {})
            score = sentiment_data.get("compound", 0)
            scores.append(score)
        
        return sum(scores) / len(scores) if scores else None
    