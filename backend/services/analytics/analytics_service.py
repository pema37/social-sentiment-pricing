# services/analytics/analytics_service.py
"""
Analytics service for dashboard metrics and reporting.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_
from sqlmodel import select
from datetime import datetime, timedelta
from typing import Optional
from decimal import Decimal

from backend.models.product import Product
from backend.models.competitor import Competitor
from backend.models.sentiment import Sentiment
from backend.models.price_recommendation import PriceRecommendation, RecommendationStatus
from backend.models.price_history import PriceHistory
from backend.models.alert import Alert, AlertStatus
from backend.schemas.analytics import (
    DashboardOverview,
    ProductSummary,
    RecommendationStats,
    AlertAnalytics,
)


class AnalyticsService:
    """Service for computing dashboard analytics."""
    
    def __init__(self, session: AsyncSession, user_id: str):
        self.session = session
        self.user_id = user_id
    
    async def get_dashboard_overview(self) -> DashboardOverview:
        """Get main dashboard metrics."""
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Product counts
        result = await self.session.execute(
            select(func.count(Product.id)).where(Product.user_id == self.user_id)
        )
        total_products = result.scalar_one()
        
        result = await self.session.execute(
            select(func.count(Product.id)).where(
                and_(Product.user_id == self.user_id, Product.auto_pricing_enabled == True)
            )
        )
        auto_pricing_count = result.scalar_one()
        
        # Competitor count
        result = await self.session.execute(
            select(func.count(Competitor.id)).where(Competitor.user_id == self.user_id)
        )
        total_competitors = result.scalar_one()
        
        # Alert counts
        result = await self.session.execute(
            select(func.count(Alert.id)).where(
                and_(Alert.user_id == self.user_id, Alert.status == AlertStatus.SENT)
            )
        )
        unread_alerts = result.scalar_one()
        
        result = await self.session.execute(
            select(func.count(Alert.id)).where(
                and_(Alert.user_id == self.user_id, Alert.created_at >= today_start)
            )
        )
        alerts_today = result.scalar_one()
        
        # Recommendation counts
        result = await self.session.execute(
            select(func.count(PriceRecommendation.id)).where(
                and_(
                    PriceRecommendation.user_id == self.user_id,
                    PriceRecommendation.status == RecommendationStatus.PENDING
                )
            )
        )
        pending_recs = result.scalar_one()
        
        result = await self.session.execute(
            select(func.count(PriceRecommendation.id)).where(
                and_(
                    PriceRecommendation.user_id == self.user_id,
                    PriceRecommendation.status == RecommendationStatus.APPLIED,
                    PriceRecommendation.applied_at >= now - timedelta(days=7)
                )
            )
        )
        applied_7d = result.scalar_one()
        
        # Sentiment (last 24h)
        sentiment_24h = await self._get_average_sentiment(hours=24)
        sentiment_48h = await self._get_average_sentiment(hours=48, offset_hours=24)
        
        trend = "stable"
        if sentiment_24h and sentiment_48h:
            diff = sentiment_24h - sentiment_48h
            if diff > 0.05:
                trend = "improving"
            elif diff < -0.05:
                trend = "declining"
        
        # Mentions count - join through Product to filter by user
        result = await self.session.execute(
            select(func.count(Sentiment.id))
            .join(Product, Sentiment.product_id == Product.id)
            .where(
                and_(
                    Product.user_id == self.user_id,
                    Sentiment.analyzed_at >= now - timedelta(hours=24)
                )
            )
        )
        mentions_24h = result.scalar_one()
        
        return DashboardOverview(
            total_products=total_products,
            products_with_auto_pricing=auto_pricing_count,
            total_competitors=total_competitors,
            unread_alerts=unread_alerts,
            alerts_today=alerts_today,
            pending_recommendations=pending_recs,
            applied_recommendations_7d=applied_7d,
            average_sentiment=sentiment_24h,
            sentiment_trend=trend,
            total_mentions_24h=mentions_24h
        )
    
    async def get_product_summaries(self, limit: int = 10) -> list[ProductSummary]:
        """Get product cards for dashboard."""
        now = datetime.utcnow()
        
        result = await self.session.execute(
            select(Product)
            .where(Product.user_id == self.user_id)
            .order_by(Product.updated_at.desc())
            .limit(limit)
        )
        products = result.scalars().all()
        
        summaries = []
        for p in products:
            # Price change from base
            if p.base_price and p.base_price > 0:
                change_pct = float((p.current_price - p.base_price) / p.base_price * 100)
            else:
                change_pct = 0.0
            
            # Latest sentiment
            result = await self.session.execute(
                select(Sentiment)
                .where(Sentiment.product_id == p.id)
                .order_by(Sentiment.analyzed_at.desc())
                .limit(1)
            )
            latest_sentiment = result.scalars().first()
            
            # Mention count 24h
            result = await self.session.execute(
                select(func.count(Sentiment.id)).where(
                    and_(
                        Sentiment.product_id == p.id,
                        Sentiment.analyzed_at >= now - timedelta(hours=24)
                    )
                )
            )
            mention_count = result.scalar_one()
            
            # Pending recommendation check
            result = await self.session.execute(
                select(func.count(PriceRecommendation.id)).where(
                    and_(
                        PriceRecommendation.product_id == str(p.id),
                        PriceRecommendation.status == RecommendationStatus.PENDING
                    )
                )
            )
            has_pending = result.scalar_one() > 0
            
            summaries.append(ProductSummary(
                id=str(p.id),
                name=p.name,
                sku=p.sku,
                current_price=p.current_price,
                base_price=p.base_price,
                price_change_percent=round(change_pct, 2),
                sentiment_score=float(latest_sentiment.compound_score) if latest_sentiment else None,
                mention_count_24h=mention_count,
                has_pending_recommendation=has_pending,
                auto_pricing_enabled=p.auto_pricing_enabled
            ))
        
        return summaries
    
    async def get_recommendation_stats(self, days: int = 30) -> RecommendationStats:
        """Get recommendation performance stats."""
        since = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(func.count(PriceRecommendation.id)).where(
                and_(
                    PriceRecommendation.user_id == self.user_id,
                    PriceRecommendation.created_at >= since
                )
            )
        )
        total = result.scalar_one()
        
        async def count_status(status: RecommendationStatus) -> int:
            result = await self.session.execute(
                select(func.count(PriceRecommendation.id)).where(
                    and_(
                        PriceRecommendation.user_id == self.user_id,
                        PriceRecommendation.created_at >= since,
                        PriceRecommendation.status == status
                    )
                )
            )
            return result.scalar_one()
        
        applied = await count_status(RecommendationStatus.APPLIED)
        rejected = await count_status(RecommendationStatus.REJECTED)
        expired = await count_status(RecommendationStatus.EXPIRED)
        pending = await count_status(RecommendationStatus.PENDING)
        
        # Approval rate
        decided = applied + rejected
        approval_rate = (applied / decided * 100) if decided > 0 else 0.0
        
        # Averages
        result = await self.session.execute(
            select(func.avg(PriceRecommendation.confidence_score)).where(
                and_(
                    PriceRecommendation.user_id == self.user_id,
                    PriceRecommendation.created_at >= since
                )
            )
        )
        avg_confidence = result.scalar_one()
        
        return RecommendationStats(
            total_generated=total,
            total_applied=applied,
            total_rejected=rejected,
            total_expired=expired,
            total_pending=pending,
            approval_rate=round(approval_rate, 1),
            avg_confidence=round(float(avg_confidence), 3) if avg_confidence else None,
            avg_price_change_percent=None  # Would need adjustment_percent avg
        )
    
    async def get_alert_analytics(self, days: int = 7) -> AlertAnalytics:
        """Get alert statistics."""
        since = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(Alert).where(
                and_(
                    Alert.user_id == self.user_id,
                    Alert.created_at >= since
                )
            )
        )
        alerts = result.scalars().all()
        
        by_type = {}
        by_severity = {}
        
        for alert in alerts:
            # By type
            type_key = alert.alert_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1
            
            # By severity
            sev_key = alert.severity.value
            by_severity[sev_key] = by_severity.get(sev_key, 0) + 1
        
        return AlertAnalytics(
            total_alerts_7d=len(alerts),
            by_type=by_type,
            by_severity=by_severity,
            avg_resolution_time_hours=None  # Would need resolved_at tracking
        )
    
    async def _get_average_sentiment(
        self, hours: int = 24, offset_hours: int = 0
    ) -> Optional[float]:
        """Get average sentiment for a time window."""
        now = datetime.utcnow()
        start = now - timedelta(hours=hours + offset_hours)
        end = now - timedelta(hours=offset_hours)
        
        # Join through Product to filter by user_id
        result = await self.session.execute(
            select(func.avg(Sentiment.compound_score))
            .join(Product, Sentiment.product_id == Product.id)
            .where(
                and_(
                    Product.user_id == self.user_id,
                    Sentiment.analyzed_at >= start,
                    Sentiment.analyzed_at < end
                )
            )
        )
        avg_result = result.scalar_one()
        
        return round(float(avg_result), 3) if avg_result else None
    
