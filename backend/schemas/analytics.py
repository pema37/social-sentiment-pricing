# schemas/analytics.py
"""
Analytics schemas for dashboard metrics and reporting.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal


# ============== Dashboard Overview ==============

class DashboardOverview(BaseModel):
    """Main dashboard summary metrics."""
    # Counts
    total_products: int
    products_with_auto_pricing: int
    total_competitors: int
    
    # Alerts
    unread_alerts: int
    alerts_today: int
    
    # Recommendations
    pending_recommendations: int
    applied_recommendations_7d: int
    
    # Sentiment (last 24h)
    average_sentiment: Optional[float] = None
    sentiment_trend: str = "stable"  # "improving", "declining", "stable"
    total_mentions_24h: int = 0


class ProductSummary(BaseModel):
    """Product card for dashboard."""
    id: str
    name: str
    sku: Optional[str] = None
    current_price: Decimal
    base_price: Decimal
    price_change_percent: float
    sentiment_score: Optional[float] = None
    mention_count_24h: int = 0
    has_pending_recommendation: bool = False
    auto_pricing_enabled: bool = False


# ============== Recommendation Stats ==============

class RecommendationStats(BaseModel):
    """Recommendation performance metrics."""
    total_generated: int
    total_applied: int
    total_rejected: int
    total_expired: int
    total_pending: int
    
    approval_rate: float  # applied / (applied + rejected)
    avg_confidence: Optional[float] = None
    avg_price_change_percent: Optional[float] = None


# ============== Sentiment Analytics ==============

class SentimentDataPoint(BaseModel):
    """Single point in sentiment timeline."""
    timestamp: datetime
    score: float
    mention_count: int


class SentimentAnalytics(BaseModel):
    """Sentiment trends over time."""
    product_id: Optional[str] = None
    period_days: int
    current_score: Optional[float] = None
    previous_score: Optional[float] = None
    change: Optional[float] = None
    trend: str = "stable"
    timeline: List[SentimentDataPoint] = []


# ============== Revenue Impact ==============

class RevenueImpact(BaseModel):
    """Revenue impact from price changes."""
    period_days: int
    total_price_changes: int
    avg_change_percent: float
    products_increased: int
    products_decreased: int
    
    # If outcome tracking exists
    estimated_revenue_impact: Optional[Decimal] = None


# ============== Alert Analytics ==============

class AlertAnalytics(BaseModel):
    """Alert statistics."""
    total_alerts_7d: int
    by_type: dict  # {"sentiment_change": 5, "price_recommendation": 12, ...}
    by_severity: dict  # {"low": 10, "medium": 5, "high": 2, "critical": 1}
    avg_resolution_time_hours: Optional[float] = None
