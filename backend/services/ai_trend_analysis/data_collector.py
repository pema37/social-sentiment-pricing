"""
Data collection methods for trend analysis.
Handles all database queries to gather analysis data.

FIX (2026-01-17): Converted from sync Session to async AsyncSession.
Changed all self.db.exec() to await self.db.execute() with proper
scalars() handling.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.competitor_product import CompetitorProduct
from models.product import Product
from models.sentiment import Sentiment
from models.social_mention import SocialMention


class DataCollector:
    """Collects data from database for trend analysis."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================
    # Product Data
    # ==========================================

    async def get_products(
        self,
        user_id: str,
        product_ids: list[str] | None = None,
    ) -> list[Product]:
        """Get products for analysis."""
        query = select(Product).where(Product.user_id == user_id)
        if product_ids:
            query = query.where(Product.id.in_(product_ids))

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ==========================================
    # Sentiment Data
    # ==========================================

    async def get_sentiment_history(
        self,
        user_id: str,
        days: int,
        product_ids: list[str] | None = None,
    ) -> list[dict]:
        """Get sentiment history for the specified period."""
        start_date = datetime.now(UTC) - timedelta(days=days)

        query = (
            select(Sentiment)
            .join(Product)
            .where(Product.user_id == user_id)
            .where(Sentiment.analyzed_at >= start_date)
            .order_by(Sentiment.analyzed_at.desc())
        )

        if product_ids:
            query = query.where(Sentiment.product_id.in_(product_ids))

        result = await self.db.execute(query)
        sentiments = result.scalars().all()

        return [
            {
                "product_id": str(s.product_id),
                "score": float(s.score) if s.score else 0,
                "magnitude": float(s.magnitude) if hasattr(s, "magnitude") and s.magnitude else 0,
                "created_at": s.analyzed_at,
            }
            for s in sentiments
        ]

    async def get_product_sentiment(self, product_id: str, days: int) -> dict:
        """Get sentiment data for a specific product."""
        start_date = datetime.now(UTC) - timedelta(days=days)

        result = await self.db.execute(
            select(Sentiment)
            .where(Sentiment.product_id == product_id)
            .where(Sentiment.analyzed_at >= start_date)
            .order_by(Sentiment.analyzed_at.desc())
        )
        sentiments = list(result.scalars().all())

        if not sentiments:
            return {
                "current": 0,
                "avg_7d": 0,
                "avg_30d": 0,
                "trend": "stable",
                "avg_volume": 0,
                "volume_change": 0,
            }

        scores = [float(s.score) if s.score else 0 for s in sentiments]
        current = scores[0] if scores else 0
        avg_7d = sum(scores[:7]) / min(7, len(scores)) if scores else 0
        avg_30d = sum(scores) / len(scores) if scores else 0

        # Determine trend
        trend = "stable"
        if len(scores) >= 7:
            recent = sum(scores[:7]) / 7
            older = sum(scores[7:14]) / min(7, len(scores[7:14])) if len(scores) > 7 else recent
            if recent > older + 0.1:
                trend = "rising"
            elif recent < older - 0.1:
                trend = "falling"

        return {
            "current": current,
            "avg_7d": avg_7d,
            "avg_30d": avg_30d,
            "trend": trend,
            "avg_volume": len(scores) / days if days > 0 else 0,
            "volume_change": 0,
        }

    # ==========================================
    # Mentions Data
    # ==========================================

    async def get_mentions_summary(
        self,
        user_id: str,
        days: int,
        product_ids: list[str] | None = None,
    ) -> list[dict]:
        """Get social mentions for the specified period."""
        start_date = datetime.now(UTC) - timedelta(days=days)

        query = (
            select(SocialMention)
            .join(Product)
            .where(Product.user_id == user_id)
            .where(SocialMention.collected_at >= start_date)
            .order_by(SocialMention.collected_at.desc())
        )

        if product_ids:
            query = query.where(SocialMention.product_id.in_(product_ids))

        result = await self.db.execute(query)
        mentions = result.scalars().all()

        return [
            {
                "product_id": str(m.product_id),
                "platform": m.platform,
                "content": m.content[:200] if m.content else "",
                "sentiment_score": float(m.sentiment_score) if m.sentiment_score else 0,
                "created_at": m.collected_at,
            }
            for m in mentions
        ]

    async def get_product_mentions(self, product_id: str, days: int) -> list:
        """Get mentions for a specific product."""
        start_date = datetime.now(UTC) - timedelta(days=days)

        result = await self.db.execute(
            select(SocialMention)
            .where(SocialMention.product_id == product_id)
            .where(SocialMention.collected_at >= start_date)
            .order_by(SocialMention.collected_at.desc())
        )
        return list(result.scalars().all())

    async def get_negative_mentions(self, user_id: str, days: int) -> list:
        """Get negative sentiment mentions."""
        start_date = datetime.now(UTC) - timedelta(days=days)

        result = await self.db.execute(
            select(SocialMention)
            .join(Product)
            .where(Product.user_id == user_id)
            .where(SocialMention.collected_at >= start_date)
            .join(Sentiment, Sentiment.product_id == SocialMention.product_id)
            .where(Sentiment.compound_score < -0.3)
            .order_by(Sentiment.compound_score.asc())
            .limit(50)
        )
        return list(result.scalars().all())

    # ==========================================
    # Competitor Data
    # ==========================================

    async def get_competitor_data(
        self,
        user_id: str,
        product_ids: list[str] | None = None,
    ) -> list[dict]:
        """Get competitor product data."""
        query = select(CompetitorProduct).join(Product).where(Product.user_id == user_id)

        if product_ids:
            query = query.where(CompetitorProduct.product_id.in_(product_ids))

        result = await self.db.execute(query)
        competitors = result.scalars().all()

        return [
            {
                "product_id": str(c.product_id),
                "competitor_name": c.competitor_name if hasattr(c, "competitor_name") else "Unknown",
                "competitor_price": float(c.price) if c.price else 0,
                "last_updated": c.updated_at,
            }
            for c in competitors
        ]

    async def get_product_competitors(self, product_id: str) -> list:
        """Get competitors for a specific product."""
        result = await self.db.execute(select(CompetitorProduct).where(CompetitorProduct.product_id == product_id))
        return list(result.scalars().all())

    # ==========================================
    # Alerts Data
    # ==========================================

    async def get_current_alerts(self, user_id: str) -> list:
        """Get active alerts for the user."""
        try:
            from models.alert import Alert

            result = await self.db.execute(
                select(Alert).where(Alert.user_id == user_id).where(Alert.status == "active")
            )
            return list(result.scalars().all())
        except Exception:
            return []

    # ==========================================
    # Placeholder Methods (for future implementation)
    # ==========================================

    async def get_sentiment_drops(self, user_id: str, days: int) -> list[dict]:
        """Detect significant sentiment drops."""
        # TODO: Implement sentiment drop detection
        return []

    async def get_recent_competitor_activities(self, user_id: str) -> list[dict]:
        """Get recent competitor price changes."""
        # TODO: Implement competitor activity tracking
        return []
