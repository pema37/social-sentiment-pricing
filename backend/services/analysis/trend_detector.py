# backend/services/analysis/trend_detector.py

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.social_mention import SocialMention
from services.analysis.sentiment_aggregator import SentimentAggregator


class TrendDetector:
    """
    Detects trends, viral spikes, and sentiment anomalies
    that should trigger pricing decisions or alerts.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.aggregator = SentimentAggregator(db)
        
        # Thresholds for detection
        self.volume_spike_threshold = 2.0  # 2x normal volume
        self.sentiment_shift_threshold = 0.3  # 0.3 point shift
        self.viral_engagement_threshold = 1000  # High engagement count
    
    async def detect_all(self, product_id: UUID) -> Dict:
        """
        Run all trend detection checks for a product.
        
        Returns:
            {
                "product_id": str,
                "has_alerts": bool,
                "alerts": [
                    {"type": "volume_spike", "severity": "high", "message": "..."},
                    ...
                ],
                "metrics": {
                    "volume_change": float,
                    "sentiment_velocity": float,
                    "viral_mentions": int
                }
            }
        """
        alerts = []
        
        # Check for volume spike
        volume_alert = await self.detect_volume_spike(product_id)
        if volume_alert:
            alerts.append(volume_alert)
        
        # Check for sentiment shift
        sentiment_alert = await self.detect_sentiment_shift(product_id)
        if sentiment_alert:
            alerts.append(sentiment_alert)
        
        # Check for viral mentions
        viral_alert = await self.detect_viral_mentions(product_id)
        if viral_alert:
            alerts.append(viral_alert)
        
        # Get current metrics
        velocity = await self.aggregator.get_sentiment_velocity(product_id)
        
        return {
            "product_id": str(product_id),
            "has_alerts": len(alerts) > 0,
            "alerts": alerts,
            "metrics": {
                "volume_change": velocity["volume_change"],
                "sentiment_velocity": velocity["velocity"],
                "trend": velocity["trend"],
                "current_sentiment": velocity["current_sentiment"]
            },
            "checked_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def detect_volume_spike(
        self,
        product_id: UUID,
        current_hours: int = 6,
        baseline_hours: int = 48
    ) -> Optional[Dict]:
        """
        Detect unusual increase in mention volume.
        
        A spike might indicate:
        - Viral post about the product
        - News coverage
        - Competitor activity
        """
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(hours=current_hours)
        baseline_start = now - timedelta(hours=baseline_hours)
        
        # Current period count
        result = await self.db.execute(
            select(SocialMention)
            .where(SocialMention.product_id == product_id)
            .where(SocialMention.collected_at >= current_start)
        )
        current_mentions = list(result.scalars().all())
        current_count = len(current_mentions)
        
        # Baseline period count
        result = await self.db.execute(
            select(SocialMention)
            .where(SocialMention.product_id == product_id)
            .where(SocialMention.collected_at >= baseline_start)
            .where(SocialMention.collected_at < current_start)
        )
        baseline_mentions = list(result.scalars().all())
        baseline_count = len(baseline_mentions)
        
        baseline_periods = (baseline_hours - current_hours) / current_hours
        baseline_avg = baseline_count / baseline_periods if baseline_periods > 0 else 0
        
        if baseline_avg > 0 and current_count > baseline_avg * self.volume_spike_threshold:
            multiplier = current_count / baseline_avg
            severity = "critical" if multiplier > 5 else "high" if multiplier > 3 else "medium"
            
            return {
                "type": "volume_spike",
                "severity": severity,
                "message": f"Mention volume is {multiplier:.1f}x higher than normal",
                "data": {
                    "current_count": current_count,
                    "baseline_avg": round(baseline_avg, 1),
                    "multiplier": round(multiplier, 1)
                }
            }
        
        return None
    
    async def detect_sentiment_shift(
        self,
        product_id: UUID,
        current_hours: int = 12,
        previous_hours: int = 12
    ) -> Optional[Dict]:
        """
        Detect significant shift in sentiment.
        
        A sudden drop might indicate:
        - Product quality issue
        - PR crisis
        - Competitor launch
        
        A sudden rise might indicate:
        - Positive press coverage
        - Influencer endorsement
        - Successful campaign
        """
        velocity_data = await self.aggregator.get_sentiment_velocity(
            product_id,
            current_hours=current_hours,
            previous_hours=previous_hours
        )
        
        current = velocity_data["current_sentiment"]
        previous = velocity_data["previous_sentiment"]
        shift = current - previous
        
        if abs(shift) >= self.sentiment_shift_threshold:
            if shift < 0:
                severity = "critical" if shift < -0.5 else "high"
                return {
                    "type": "sentiment_drop",
                    "severity": severity,
                    "message": f"Sentiment dropped {abs(shift):.2f} points in {current_hours} hours",
                    "data": {
                        "current_sentiment": round(current, 2),
                        "previous_sentiment": round(previous, 2),
                        "shift": round(shift, 2)
                    }
                }
            else:
                severity = "info" if shift < 0.5 else "high"
                return {
                    "type": "sentiment_spike",
                    "severity": severity,
                    "message": f"Sentiment improved {shift:.2f} points in {current_hours} hours",
                    "data": {
                        "current_sentiment": round(current, 2),
                        "previous_sentiment": round(previous, 2),
                        "shift": round(shift, 2)
                    }
                }
        
        return None
    
    async def detect_viral_mentions(
        self,
        product_id: UUID,
        hours: int = 24
    ) -> Optional[Dict]:
        """
        Detect mentions with unusually high engagement.
        
        Viral mentions can significantly impact sentiment
        and should be weighted more heavily in pricing decisions.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        result = await self.db.execute(
            select(SocialMention)
            .where(SocialMention.product_id == product_id)
            .where(SocialMention.collected_at >= cutoff)
        )
        mentions = list(result.scalars().all())
        
        viral_mentions = [
            m for m in mentions
            if (m.engagement_count or 0) >= self.viral_engagement_threshold
        ]
        
        if viral_mentions:
            # Analyze sentiment of viral mentions
            positive_viral = 0
            negative_viral = 0
            
            for m in viral_mentions:
                sentiment = (m.raw_data or {}).get("sentiment", {})
                label = sentiment.get("label", "neutral")
                if "positive" in label:
                    positive_viral += 1
                elif "negative" in label:
                    negative_viral += 1
            
            overall = "positive" if positive_viral > negative_viral else "negative" if negative_viral > positive_viral else "mixed"
            severity = "critical" if negative_viral > 0 else "high" if positive_viral > 0 else "medium"
            
            return {
                "type": "viral_mention",
                "severity": severity,
                "message": f"{len(viral_mentions)} viral mention(s) detected with {overall} sentiment",
                "data": {
                    "viral_count": len(viral_mentions),
                    "positive_viral": positive_viral,
                    "negative_viral": negative_viral,
                    "overall_sentiment": overall
                }
            }
        
        return None
    
    async def get_pricing_signal(self, product_id: UUID) -> Dict:
        """
        Generate a pricing signal based on trend analysis.
        
        Used by the pricing engine to make decisions.
        
        Returns:
            {
                "signal": "increase" | "decrease" | "hold",
                "strength": float (0-1),
                "reasons": [str],
                "recommended_adjustment_pct": float
            }
        """
        detection = await self.detect_all(product_id)
        aggregation = await self.aggregator.get_product_sentiment(product_id, hours=24)
        velocity = await self.aggregator.get_sentiment_velocity(product_id)
        
        signal = "hold"
        strength = 0.0
        reasons: List[str] = []
        adjustment = 0.0
        
        # Factor 1: Current sentiment level
        avg_sentiment = aggregation["avg_sentiment"]
        if avg_sentiment > 0.5:
            signal = "increase"
            strength += 0.3
            adjustment += 3.0
            reasons.append(f"Strong positive sentiment ({avg_sentiment:.2f})")
        elif avg_sentiment < -0.3:
            signal = "decrease"
            strength += 0.3
            adjustment -= 3.0
            reasons.append(f"Negative sentiment ({avg_sentiment:.2f})")
        
        # Factor 2: Sentiment trend
        if velocity["trend"] == "improving" and velocity["velocity"] > 0.05:
            if signal != "decrease":
                signal = "increase"
            strength += 0.2
            adjustment += 2.0
            reasons.append("Sentiment trending upward")
        elif velocity["trend"] == "declining" and velocity["velocity"] < -0.05:
            signal = "decrease"
            strength += 0.2
            adjustment -= 2.0
            reasons.append("Sentiment trending downward")
        
        # Factor 3: Volume changes
        if velocity["volume_change"] > 1.0:  # More than double
            strength += 0.2
            reasons.append(f"High mention volume (+{velocity['volume_change']*100:.0f}%)")
        
        # Factor 4: Alerts
        for alert in detection["alerts"]:
            if alert["type"] == "viral_mention":
                if alert["data"]["overall_sentiment"] == "positive":
                    adjustment += 2.0
                    reasons.append("Viral positive mention detected")
                elif alert["data"]["overall_sentiment"] == "negative":
                    signal = "decrease"
                    adjustment -= 3.0
                    reasons.append("Viral negative mention detected")
            elif alert["type"] == "sentiment_drop":
                signal = "decrease"
                adjustment -= 2.0
        
        # Cap strength at 1.0
        strength = min(strength, 1.0)
        
        # Cap adjustment
        adjustment = max(min(adjustment, 10.0), -10.0)
        
        return {
            "signal": signal,
            "strength": round(strength, 2),
            "reasons": reasons,
            "recommended_adjustment_pct": round(adjustment, 1),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    

    