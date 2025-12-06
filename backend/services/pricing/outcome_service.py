# backend/services/pricing/outcome_service.py
"""
Outcome Service - Records and analyzes recommendation outcomes.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.models.recommendation_outcome import RecommendationOutcome, OutcomeLabel
from backend.models.price_recommendation import PriceRecommendation, RecommendationStatus
from backend.models.pricing_rule import PricingRule


class OutcomeService:
    
    # Thresholds for outcome classification
    POSITIVE_THRESHOLD = Decimal("0.02")   # 2% improvement
    NEGATIVE_THRESHOLD = Decimal("-0.02")  # 2% decline
    MIN_DATA_THRESHOLD = 3                  # Minimum sales to be conclusive
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def record_outcome(
        self,
        recommendation_id: UUID,
        user_id: UUID,
        sales_count_before: int,
        units_sold_before: int,
        revenue_before: Decimal,
        sales_count_after: int,
        units_sold_after: int,
        revenue_after: Decimal,
        measurement_window_hours: int = 48
    ) -> RecommendationOutcome:
        """Record the outcome of an applied recommendation."""
        
        # Get recommendation
        recommendation = await self.db.get(PriceRecommendation, recommendation_id)
        if not recommendation:
            raise ValueError("Recommendation not found")
        if recommendation.user_id != user_id:
            raise ValueError("Recommendation not found")
        if recommendation.status != RecommendationStatus.APPLIED:
            raise ValueError("Recommendation was not applied")
        
        # Check if outcome already recorded
        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.recommendation_id == recommendation_id
        )
        result = await self.db.execute(stmt)
        existing = result.scalars().first()
        if existing:
            raise ValueError("Outcome already recorded for this recommendation")
        
        # Get rule info if available
        rule_type = None
        if recommendation.triggered_rule_id:
            rule = await self.db.get(PricingRule, recommendation.triggered_rule_id)
            if rule:
                rule_type = rule.rule_type.value if hasattr(rule.rule_type, 'value') else str(rule.rule_type)
        
        # Calculate changes
        revenue_change = revenue_after - revenue_before
        revenue_change_percent = None
        if revenue_before > 0:
            revenue_change_percent = ((revenue_after - revenue_before) / revenue_before * 100).quantize(Decimal("0.01"))

        units_change = units_sold_after - units_sold_before
        units_change_percent = None
        if units_sold_before > 0:
            units_change_percent = Decimal(str((units_sold_after - units_sold_before) / units_sold_before * 100)).quantize(Decimal("0.01"))
        
        # Calculate avg daily metrics
        days = max(measurement_window_hours / 24, 1)
        avg_daily_before = Decimal(str(units_sold_before / days)).quantize(Decimal("0.01"))
        avg_daily_after = Decimal(str(units_sold_after / days)).quantize(Decimal("0.01"))
        
        # Calculate outcome score and label
        outcome_score, outcome_label = self._calculate_outcome(
            revenue_before, revenue_after,
            units_sold_before, units_sold_after,
            recommendation.change_percent
        )
        
        # Current timestamp for measured_at
        now = datetime.utcnow()
        
        outcome = RecommendationOutcome(
            user_id=user_id,
            recommendation_id=recommendation_id,
            product_id=recommendation.product_id,
            rule_id=recommendation.triggered_rule_id,
            rule_type=rule_type,
            
            price_before=recommendation.current_price,
            price_after=recommendation.recommended_price,
            price_change_percent=recommendation.change_percent,
            
            sales_count_before=sales_count_before,
            units_sold_before=units_sold_before,
            revenue_before=revenue_before,
            avg_daily_sales_before=avg_daily_before,
            
            sales_count_after=sales_count_after,
            units_sold_after=units_sold_after,
            revenue_after=revenue_after,
            avg_daily_sales_after=avg_daily_after,
            
            revenue_change=revenue_change,
            revenue_change_percent=revenue_change_percent,
            units_change=units_change,
            units_change_percent=units_change_percent,
            
            outcome_score=outcome_score,
            outcome_label=outcome_label,
            original_confidence=recommendation.confidence_score,
            
            price_applied_at=recommendation.applied_at or now,
            measurement_window_hours=measurement_window_hours,
            measured_at=now,  # Add measured_at field
        )
        
        self.db.add(outcome)
        await self.db.commit()
        await self.db.refresh(outcome)
        
        return outcome
    
    def _calculate_outcome(
        self,
        revenue_before: Decimal,
        revenue_after: Decimal,
        units_before: int,
        units_after: int,
        price_change_percent: Decimal
    ) -> tuple[Decimal, OutcomeLabel]:
        """Calculate outcome score (-1 to 1) and label."""
        
        # Not enough data
        if units_before < self.MIN_DATA_THRESHOLD and units_after < self.MIN_DATA_THRESHOLD:
            return Decimal("0"), OutcomeLabel.INCONCLUSIVE
        
        # Calculate revenue change ratio
        if revenue_before > 0:
            revenue_ratio = (revenue_after - revenue_before) / revenue_before
        else:
            revenue_ratio = Decimal("1") if revenue_after > 0 else Decimal("0")
        
        # Calculate units change ratio
        if units_before > 0:
            units_ratio = Decimal(str((units_after - units_before) / units_before))
        else:
            units_ratio = Decimal("1") if units_after > 0 else Decimal("0")
        
        # Combined score (revenue weighted more heavily)
        score = (revenue_ratio * Decimal("0.7") + units_ratio * Decimal("0.3"))
        
        # Clamp to -1 to 1
        score = max(Decimal("-1"), min(Decimal("1"), score))
        score = score.quantize(Decimal("0.01"))
        
        # Determine label
        if score >= self.POSITIVE_THRESHOLD:
            label = OutcomeLabel.POSITIVE
        elif score <= self.NEGATIVE_THRESHOLD:
            label = OutcomeLabel.NEGATIVE
        else:
            label = OutcomeLabel.NEUTRAL
        
        return score, label
    
    async def get_outcomes(
        self,
        user_id: UUID,
        product_id: Optional[UUID] = None,
        rule_id: Optional[UUID] = None,
        outcome_label: Optional[OutcomeLabel] = None,
        days: int = 30,
        limit: int = 50,
        offset: int = 0
    ) -> list[RecommendationOutcome]:
        """List outcomes with filters."""
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.user_id == user_id,
            RecommendationOutcome.created_at >= cutoff
        )
        
        if product_id:
            stmt = stmt.where(RecommendationOutcome.product_id == product_id)
        if rule_id:
            stmt = stmt.where(RecommendationOutcome.rule_id == rule_id)
        if outcome_label:
            stmt = stmt.where(RecommendationOutcome.outcome_label == outcome_label)
        
        stmt = stmt.order_by(RecommendationOutcome.created_at.desc())
        stmt = stmt.offset(offset).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_rule_performance(self, rule_id: UUID, user_id: UUID, days: int = 90) -> dict:
        """Get performance statistics for a specific rule."""
        
        rule = await self.db.get(PricingRule, rule_id)
        if not rule or rule.user_id != user_id:
            raise ValueError("Rule not found")
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.rule_id == rule_id,
            RecommendationOutcome.created_at >= cutoff
        )
        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())
        
        if not outcomes:
            return {
                "rule_id": rule_id,
                "rule_name": rule.name,
                "rule_type": rule.rule_type.value if hasattr(rule.rule_type, 'value') else str(rule.rule_type),
                "total_outcomes": 0,
                "positive_outcomes": 0,
                "negative_outcomes": 0,
                "neutral_outcomes": 0,
                "success_rate": Decimal("0"),
                "avg_outcome_score": Decimal("0"),
                "avg_revenue_change_percent": None,
                "total_revenue_impact": Decimal("0"),
                "avg_confidence": Decimal("0"),
                "confidence_accuracy_correlation": None,
            }
        
        positive = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.POSITIVE)
        negative = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.NEGATIVE)
        neutral = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.NEUTRAL)
        
        total = len(outcomes)
        success_rate = Decimal(str(positive / total * 100)).quantize(Decimal("0.01"))
        
        avg_score = sum(o.outcome_score for o in outcomes) / total
        avg_score = avg_score.quantize(Decimal("0.01"))
        
        revenue_changes = [o.revenue_change_percent for o in outcomes if o.revenue_change_percent is not None]
        avg_revenue_change = None
        if revenue_changes:
            avg_revenue_change = (sum(revenue_changes) / len(revenue_changes)).quantize(Decimal("0.01"))
        
        total_revenue_impact = sum(o.revenue_change for o in outcomes)
        
        avg_confidence = (sum(o.original_confidence for o in outcomes) / total).quantize(Decimal("0.01"))
        
        return {
            "rule_id": rule_id,
            "rule_name": rule.name,
            "rule_type": rule.rule_type.value if hasattr(rule.rule_type, 'value') else str(rule.rule_type),
            "total_outcomes": total,
            "positive_outcomes": positive,
            "negative_outcomes": negative,
            "neutral_outcomes": neutral,
            "success_rate": success_rate,
            "avg_outcome_score": avg_score,
            "avg_revenue_change_percent": avg_revenue_change,
            "total_revenue_impact": total_revenue_impact,
            "avg_confidence": avg_confidence,
            "confidence_accuracy_correlation": None,  # TODO: Calculate correlation
        }
    
    async def get_accuracy_stats(self, user_id: UUID, days: int = 30) -> dict:
        """Get overall accuracy statistics."""
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.user_id == user_id,
            RecommendationOutcome.created_at >= cutoff
        )
        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())
        
        if not outcomes:
            return {
                "period_days": days,
                "total_outcomes": 0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "inconclusive_count": 0,
                "overall_success_rate": Decimal("0"),
                "avg_outcome_score": Decimal("0"),
                "total_revenue_impact": Decimal("0"),
                "avg_revenue_change_percent": None,
                "by_rule_type": {},
                "top_performing_rules": [],
                "worst_performing_rules": [],
            }
        
        positive = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.POSITIVE)
        negative = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.NEGATIVE)
        neutral = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.NEUTRAL)
        inconclusive = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.INCONCLUSIVE)
        
        total = len(outcomes)
        conclusive = total - inconclusive
        
        success_rate = Decimal("0")
        if conclusive > 0:
            success_rate = Decimal(str(positive / conclusive * 100)).quantize(Decimal("0.01"))
        
        avg_score = (sum(o.outcome_score for o in outcomes) / total).quantize(Decimal("0.01"))
        
        total_revenue_impact = sum(o.revenue_change for o in outcomes)
        
        revenue_changes = [o.revenue_change_percent for o in outcomes if o.revenue_change_percent is not None]
        avg_revenue_change = None
        if revenue_changes:
            avg_revenue_change = (sum(revenue_changes) / len(revenue_changes)).quantize(Decimal("0.01"))
        
        # Group by rule type
        by_rule_type: dict = {}
        for o in outcomes:
            rt = o.rule_type or "unknown"
            if rt not in by_rule_type:
                by_rule_type[rt] = {"count": 0, "positive": 0, "revenue_impact": Decimal("0")}
            by_rule_type[rt]["count"] += 1
            if o.outcome_label == OutcomeLabel.POSITIVE:
                by_rule_type[rt]["positive"] += 1
            by_rule_type[rt]["revenue_impact"] += o.revenue_change
        
        # Calculate success rates for each rule type
        for rt, stats in by_rule_type.items():
            stats["success_rate"] = float(Decimal(str(stats["positive"] / stats["count"] * 100)).quantize(Decimal("0.01")))
            stats["revenue_impact"] = float(stats["revenue_impact"])
        
        # Get rule performance rankings
        rule_scores: dict = {}
        for o in outcomes:
            if o.rule_id:
                if o.rule_id not in rule_scores:
                    rule_scores[o.rule_id] = {"scores": [], "rule_type": o.rule_type}
                rule_scores[o.rule_id]["scores"].append(o.outcome_score)
        
        rule_averages: list[dict] = []
        for rule_id, data in rule_scores.items():
            avg = sum(data["scores"]) / len(data["scores"])
            rule = await self.db.get(PricingRule, rule_id)
            rule_averages.append({
                "rule_id": str(rule_id),
                "rule_name": rule.name if rule else "Unknown",
                "rule_type": data["rule_type"],
                "avg_score": float(avg.quantize(Decimal("0.01"))),
                "outcome_count": len(data["scores"]),
            })
        
        rule_averages.sort(key=lambda x: x["avg_score"], reverse=True)
        
        return {
            "period_days": days,
            "total_outcomes": total,
            "positive_count": positive,
            "negative_count": negative,
            "neutral_count": neutral,
            "inconclusive_count": inconclusive,
            "overall_success_rate": success_rate,
            "avg_outcome_score": avg_score,
            "total_revenue_impact": total_revenue_impact,
            "avg_revenue_change_percent": avg_revenue_change,
            "by_rule_type": by_rule_type,
            "top_performing_rules": rule_averages[:5],
            "worst_performing_rules": rule_averages[-5:][::-1] if len(rule_averages) > 5 else [],
        }
    
    async def get_historical_accuracy_for_rule_type(self, user_id: UUID, rule_type: str, days: int = 90) -> Decimal:
        """Get historical success rate for a rule type (used by confidence calculator)."""
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.user_id == user_id,
            RecommendationOutcome.rule_type == rule_type,
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.outcome_label != OutcomeLabel.INCONCLUSIVE
        )
        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())
        
        if len(outcomes) < 5:
            # Not enough data, return neutral
            return Decimal("0.5")
        
        positive = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.POSITIVE)
        return Decimal(str(positive / len(outcomes))).quantize(Decimal("0.01"))
    