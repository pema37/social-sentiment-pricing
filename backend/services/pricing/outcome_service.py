"""
Outcome Service - Records and analyzes recommendation outcomes.

Core service: record_outcome, get_outcomes, rule performance, accuracy stats.
Intelligence environment methods split into sibling modules:
  - outcome_measurement.py  → background job interface (7d/14d/30d windows)
  - outcome_calibration.py  → backward learning (confidence, elasticity, merchant patterns)
  - outcome_benchmarks.py   → cross-merchant intelligence (category benchmarks, data gaps)

FIX (2026-02-17): Added record_merchant_decision() for feedback loop entry point.
FIX (2026-02-17): Typed evidence extraction with backward compat for old recommendations.
"""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import sqrt
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.price_recommendation import PriceRecommendation, RecommendationStatus
from models.pricing_rule import PricingRule
from models.product import Product
from models.recommendation_outcome import (
    MeasurementStatus,
    MerchantDecision,
    OutcomeLabel,
    RecommendationOutcome,
    RecommendationSource,
)

logger = logging.getLogger(__name__)


class OutcomeService:
    # Thresholds for outcome classification
    POSITIVE_THRESHOLD = Decimal("0.02")  # 2% improvement
    NEGATIVE_THRESHOLD = Decimal("-0.02")  # 2% decline
    MIN_DATA_THRESHOLD = 3  # Minimum sales to be conclusive

    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────
    # RECORD OUTCOME (updated with intelligence env fields)
    # ──────────────────────────────────────────────

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
        measurement_window_hours: int = 48,
        # ── New: merchant decision tracking ──
        merchant_decision: str = MerchantDecision.ACCEPTED.value,
        actual_price_set: Decimal | None = None,
        # ── New: confidence decomposition ──
        confidence_elasticity: float | None = None,
        confidence_position: float | None = None,
        confidence_urgency: float | None = None,
        confidence_data_quality: float | None = None,
        # ── New: analyst scoring snapshot ──
        elasticity_estimate: float | None = None,
        urgency_score: float | None = None,
        sentiment_score: float | None = None,
        competitive_position_index: float | None = None,
        competitor_count: int | None = None,
        data_completeness: float | None = None,
        # ── New: agent evidence chain ──
        scout_evidence: dict | None = None,
        analyst_evidence: dict | None = None,
        strategist_evidence: dict | None = None,
        # ── New: cross-merchant fields ──
        product_category: str | None = None,
        store_platform: str | None = None,
        # ── New: recommendation source ──
        recommendation_source: str = RecommendationSource.RULE_BASED.value,
        # ── New: margin ──
        margin_before: Decimal | None = None,
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
        stmt = select(RecommendationOutcome).where(RecommendationOutcome.recommendation_id == recommendation_id)
        result = await self.db.execute(stmt)
        existing = result.scalars().first()
        if existing:
            raise ValueError("Outcome already recorded for this recommendation")

        # Get rule info if available
        rule_type = None
        if recommendation.triggered_rule_id:
            rule = await self.db.get(PricingRule, recommendation.triggered_rule_id)
            if rule:
                rule_type = rule.rule_type.value if hasattr(rule.rule_type, "value") else str(rule.rule_type)

        # Calculate changes
        revenue_change = revenue_after - revenue_before
        revenue_change_percent = None
        if revenue_before > 0:
            revenue_change_percent = ((revenue_after - revenue_before) / revenue_before * 100).quantize(Decimal("0.01"))

        units_change = units_sold_after - units_sold_before
        units_change_percent = None
        if units_sold_before > 0:
            units_change_percent = Decimal(
                str((units_sold_after - units_sold_before) / units_sold_before * 100)
            ).quantize(Decimal("0.01"))

        # Calculate avg daily metrics
        days = max(measurement_window_hours / 24, 1)
        avg_daily_before = Decimal(str(units_sold_before / days)).quantize(Decimal("0.01"))
        avg_daily_after = Decimal(str(units_sold_after / days)).quantize(Decimal("0.01"))

        # Calculate outcome score and label
        outcome_score, outcome_label = self._calculate_outcome(
            revenue_before, revenue_after, units_sold_before, units_sold_after, recommendation.change_percent
        )

        now = datetime.now(UTC)

        # Calculate merchant modification if they changed the price
        merchant_modification_percent = None
        if actual_price_set is not None and recommendation.recommended_price > 0:
            diff = actual_price_set - recommendation.recommended_price
            merchant_modification_percent = float(
                (diff / recommendation.recommended_price * 100).quantize(Decimal("0.01"))
            )
            # Auto-detect modification vs straight accept
            if merchant_decision == MerchantDecision.ACCEPTED.value and abs(merchant_modification_percent) > 1.0:
                merchant_decision = MerchantDecision.MODIFIED.value

        outcome = RecommendationOutcome(
            user_id=user_id,
            recommendation_id=recommendation_id,
            product_id=recommendation.product_id,
            rule_id=recommendation.triggered_rule_id,
            rule_type=rule_type,
            recommendation_source=recommendation_source,
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
            # Confidence decomposition
            confidence_elasticity=confidence_elasticity,
            confidence_position=confidence_position,
            confidence_urgency=confidence_urgency,
            confidence_data_quality=confidence_data_quality,
            # Analyst scoring snapshot
            elasticity_estimate=elasticity_estimate,
            urgency_score=urgency_score,
            sentiment_score=sentiment_score,
            competitive_position_index=competitive_position_index,
            competitor_count=competitor_count,
            data_completeness=data_completeness,
            # Merchant decision
            merchant_decision=merchant_decision,
            actual_price_set=actual_price_set or recommendation.recommended_price,
            merchant_modification_percent=merchant_modification_percent,
            decided_at=now,
            # Agent evidence chain
            scout_evidence=scout_evidence,
            analyst_evidence=analyst_evidence,
            strategist_evidence=strategist_evidence,
            # Cross-merchant fields
            product_category=product_category,
            store_platform=store_platform,
            # Margin
            margin_before=margin_before,
            # Measurement state
            measurement_status=MeasurementStatus.DECISION_RECORDED.value,
            price_applied_at=recommendation.applied_at or now,
            measurement_window_hours=measurement_window_hours,
            measured_at=now,
        )

        self.db.add(outcome)
        await self.db.commit()
        await self.db.refresh(outcome)

        return outcome

    # ──────────────────────────────────────────────
    # OUTCOME CALCULATION
    # ──────────────────────────────────────────────

    def _calculate_outcome(
        self,
        revenue_before: Decimal,
        revenue_after: Decimal,
        units_before: int,
        units_after: int,
        price_change_percent: Decimal,
    ) -> tuple[Decimal, OutcomeLabel]:
        """Calculate outcome score (-1 to 1) and label."""

        if units_before < self.MIN_DATA_THRESHOLD and units_after < self.MIN_DATA_THRESHOLD:
            return Decimal("0"), OutcomeLabel.INCONCLUSIVE

        if revenue_before > 0:
            revenue_ratio = (revenue_after - revenue_before) / revenue_before
        else:
            revenue_ratio = Decimal("1") if revenue_after > 0 else Decimal("0")

        if units_before > 0:
            units_ratio = Decimal(str((units_after - units_before) / units_before))
        else:
            units_ratio = Decimal("1") if units_after > 0 else Decimal("0")

        score = revenue_ratio * Decimal("0.7") + units_ratio * Decimal("0.3")
        score = max(Decimal("-1"), min(Decimal("1"), score))
        score = score.quantize(Decimal("0.01"))

        if score >= self.POSITIVE_THRESHOLD:
            label = OutcomeLabel.POSITIVE
        elif score <= self.NEGATIVE_THRESHOLD:
            label = OutcomeLabel.NEGATIVE
        else:
            label = OutcomeLabel.NEUTRAL

        return score, label

    # ──────────────────────────────────────────────
    # QUERY OUTCOMES
    # ──────────────────────────────────────────────

    async def get_outcomes(
        self,
        user_id: UUID,
        product_id: UUID | None = None,
        rule_id: UUID | None = None,
        outcome_label: OutcomeLabel | None = None,
        days: int = 30,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RecommendationOutcome]:
        """List outcomes with filters."""

        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.user_id == user_id, RecommendationOutcome.created_at >= cutoff
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

    # ──────────────────────────────────────────────
    # SINGLE OUTCOME DETAIL
    # ──────────────────────────────────────────────

    async def get_outcome_by_id(
        self,
        outcome_id: UUID,
        user_id: UUID,
    ) -> RecommendationOutcome | None:
        """Fetch a single outcome by ID, scoped to the requesting user."""
        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.id == outcome_id,
            RecommendationOutcome.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    # ──────────────────────────────────────────────
    # RECORD MERCHANT DECISION (feedback loop entry point)
    # ──────────────────────────────────────────────

    async def record_merchant_decision(
        self,
        recommendation_id: UUID,
        user_id: UUID,
        merchant_decision: str,
        actual_price_set: Decimal | None = None,
        rejection_reason: str | None = None,
    ) -> RecommendationOutcome:
        """
        Record a merchant's decision on a recommendation — IMMEDIATELY.

        Called by ApprovalService when a merchant approves, modifies,
        rejects, or auto-applies. Creates the RecommendationOutcome
        record with evidence chain and confidence decomposition.

        Sales data is NOT required. Celery fills 7d/14d/30d windows
        later by querying Shopify/WooCommerce order data.

        For rejections: measurement_status = MEASURED_30D (terminal state,
        nothing to measure, but we track the decision for merchant pattern
        analysis → Strategist guardrail calibration).

        For accepted/modified/auto_applied: measurement_status =
        DECISION_RECORDED → Celery task picks up and measures at
        7d, 14d, 30d windows.
        """
        # ── Validate recommendation exists + ownership ──
        recommendation = await self.db.get(PriceRecommendation, recommendation_id)
        if not recommendation:
            raise ValueError("Recommendation not found")
        if recommendation.user_id != user_id:
            raise ValueError("Recommendation not found")

        # ── Guard: don't double-record ──
        stmt = select(RecommendationOutcome).where(RecommendationOutcome.recommendation_id == recommendation_id)
        result = await self.db.execute(stmt)
        existing = result.scalars().first()
        if existing:
            # If awaiting_decision, update it with the decision
            if existing.measurement_status == MeasurementStatus.AWAITING_DECISION.value:
                existing.merchant_decision = merchant_decision
                existing.decided_at = datetime.now(UTC)
                if actual_price_set is not None:
                    existing.actual_price_set = actual_price_set
                existing.measurement_status = (
                    MeasurementStatus.MEASURED_30D.value
                    if merchant_decision == MerchantDecision.REJECTED.value
                    else MeasurementStatus.DECISION_RECORDED.value
                )
                self.db.add(existing)
                await self.db.commit()
                await self.db.refresh(existing)
                return existing
            # Already recorded — return as-is (idempotent)
            return existing

        # ── Get rule info ──
        rule_type = None
        if recommendation.triggered_rule_id:
            rule = await self.db.get(PricingRule, recommendation.triggered_rule_id)
            if rule:
                rule_type = rule.rule_type.value if hasattr(rule.rule_type, "value") else str(rule.rule_type)

        # ── Extract evidence from recommendation.factors ──
        #
        # Two paths:
        #   NEW (post-2026-02-17): PipelineAdapter stores typed evidence at
        #     factors["scout_evidence"]      → ScoutOutput.to_evidence()
        #     factors["analyst_evidence"]     → AnalystOutput.to_evidence()
        #     factors["strategist_evidence"]  → StrategistOutput.to_evidence()
        #
        #   OLD (pre-2026-02-17): Unstructured dicts at
        #     factors["match_details"]        → rule match info
        #     factors["price_impacts"]        → price impact factors
        #     factors["confidence_breakdown"] → confidence components
        #
        # Prefer typed keys, fall back to old keys for backward compat.
        #
        factors = recommendation.factors or {}

        # ── Scout evidence: prefer typed, fall back to match_details ──
        scout_evidence = factors.get("scout_evidence") or factors.get("match_details")

        # ── Analyst evidence: prefer typed, fall back to price_impacts ──
        analyst_evidence = factors.get("analyst_evidence") or factors.get("price_impacts")

        # ── Strategist evidence: prefer typed, fall back to manual build ──
        strategist_evidence = factors.get("strategist_evidence")
        if not strategist_evidence:
            strategist_evidence = {
                "recommended_price": str(recommendation.recommended_price),
                "change_percent": str(recommendation.change_percent),
                "reasoning": recommendation.reasoning or "",
                "requires_approval": recommendation.requires_approval,
            }

        # ── Extract confidence decomposition ──
        # Typed analyst evidence has nested confidence object
        typed_analyst = factors.get("analyst_evidence", {})
        typed_confidence = typed_analyst.get("confidence", {}) if isinstance(typed_analyst, dict) else {}

        # Fallback: old-style confidence_breakdown dict
        cb = factors.get("confidence_breakdown", {})
        cb_components = cb.get("components", {}) if isinstance(cb, dict) else {}

        # Prefer typed → old-style component scores → old-style flat keys
        confidence_elasticity = (
            typed_confidence.get("elasticity")
            or cb_components.get("signal_agreement", {}).get("score")
            or cb.get("elasticity")
        )
        confidence_position = (
            typed_confidence.get("position")
            or cb_components.get("market_stability", {}).get("score")
            or cb.get("competitive_position")
            or cb.get("position")
        )
        confidence_urgency = (
            typed_confidence.get("urgency")
            or cb_components.get("rule_confidence", {}).get("score")
            or cb.get("urgency")
        )
        confidence_data_quality = (
            typed_confidence.get("data_quality")
            or cb_components.get("data_quality", {}).get("score")
            or cb.get("data_quality")
        )

        # ── Extract analyst scoring snapshot ──
        # Typed analyst evidence has these at top level
        sentiment_score_val = typed_analyst.get("sentiment_score") if isinstance(typed_analyst, dict) else None
        competitor_count_val = typed_analyst.get("competitor_count") if isinstance(typed_analyst, dict) else None

        # Fallback: old-style price_impacts dict
        if sentiment_score_val is None:
            pi = factors.get("price_impacts", {})
            sentiment_score_val = pi.get("sentiment_score") if isinstance(pi, dict) else None
        if competitor_count_val is None:
            pi = factors.get("price_impacts", {})
            competitor_count_val = pi.get("competitor_count") if isinstance(pi, dict) else None

        # ── Extract additional fields from typed evidence ──
        # These are available when PipelineAdapter produced the evidence
        elasticity_estimate_val = None
        urgency_score_val = None
        data_completeness_val = None
        competitive_position_index_val = None

        if isinstance(typed_analyst, dict):
            elasticity_obj = typed_analyst.get("elasticity", {})
            if isinstance(elasticity_obj, dict):
                elasticity_estimate_val = elasticity_obj.get("point_estimate")
            urgency_score_val = typed_analyst.get("urgency_score")
            data_completeness_val = typed_analyst.get("data_completeness")
            competitive_position_index_val = typed_analyst.get("competitive_position_index")

        # ── Get product category for cross-merchant intelligence ──
        product_category = None
        if recommendation.product_id:
            product = await self.db.get(Product, recommendation.product_id)
            if product:
                product_category = getattr(product, "category", None)

        # ── Calculate modification percent ──
        merchant_modification_percent = None
        effective_decision = merchant_decision
        if actual_price_set is not None and recommendation.recommended_price > 0:
            diff = actual_price_set - recommendation.recommended_price
            merchant_modification_percent = float(
                (diff / recommendation.recommended_price * 100).quantize(Decimal("0.01"))
            )
            # Auto-detect: "accepted" but changed price by >1% → "modified"
            if effective_decision == MerchantDecision.ACCEPTED.value and abs(merchant_modification_percent) > 1.0:
                effective_decision = MerchantDecision.MODIFIED.value

        # ── Determine measurement status ──
        needs_measurement = effective_decision in (
            MerchantDecision.ACCEPTED.value,
            MerchantDecision.MODIFIED.value,
            MerchantDecision.AUTO_APPLIED.value,
        )
        measurement_status = (
            MeasurementStatus.DECISION_RECORDED.value if needs_measurement else MeasurementStatus.MEASURED_30D.value
        )

        effective_price = actual_price_set or recommendation.recommended_price
        now = datetime.now(UTC)

        # ── Build outcome record ──
        outcome = RecommendationOutcome(
            user_id=user_id,
            recommendation_id=recommendation_id,
            product_id=recommendation.product_id,
            rule_id=recommendation.triggered_rule_id,
            rule_type=rule_type,
            recommendation_source=RecommendationSource.RULE_BASED.value,
            # Price data
            price_before=recommendation.current_price,
            price_after=effective_price,
            price_change_percent=recommendation.change_percent,
            # Sales data: zeros — Celery fills at 7d/14d/30d
            sales_count_before=0,
            units_sold_before=0,
            revenue_before=Decimal("0"),
            avg_daily_sales_before=Decimal("0"),
            sales_count_after=0,
            units_sold_after=0,
            revenue_after=Decimal("0"),
            avg_daily_sales_after=Decimal("0"),
            revenue_change=Decimal("0"),
            revenue_change_percent=None,
            units_change=0,
            units_change_percent=None,
            # Outcome: inconclusive until measurement
            outcome_score=Decimal("0"),
            outcome_label=OutcomeLabel.INCONCLUSIVE,
            original_confidence=recommendation.confidence_score,
            # Confidence decomposition
            confidence_elasticity=confidence_elasticity,
            confidence_position=confidence_position,
            confidence_urgency=confidence_urgency,
            confidence_data_quality=confidence_data_quality,
            # Analyst scoring snapshot (all 6 fields)
            elasticity_estimate=(float(elasticity_estimate_val) if elasticity_estimate_val is not None else None),
            urgency_score=(float(urgency_score_val) if urgency_score_val is not None else None),
            sentiment_score=(float(sentiment_score_val) if sentiment_score_val is not None else None),
            competitive_position_index=(
                float(competitive_position_index_val) if competitive_position_index_val is not None else None
            ),
            competitor_count=(int(competitor_count_val) if competitor_count_val is not None else None),
            data_completeness=(float(data_completeness_val) if data_completeness_val is not None else None),
            # Merchant decision
            merchant_decision=effective_decision,
            actual_price_set=effective_price,
            merchant_modification_percent=merchant_modification_percent,
            decided_at=now,
            # Agent evidence chain
            scout_evidence=(scout_evidence if isinstance(scout_evidence, dict) else None),
            analyst_evidence=(analyst_evidence if isinstance(analyst_evidence, dict) else None),
            strategist_evidence=strategist_evidence,
            # Cross-merchant intelligence
            product_category=product_category,
            store_platform=recommendation.applied_to_platform,
            # Measurement state
            measurement_status=measurement_status,
            # Timestamps
            price_applied_at=recommendation.applied_at or now,
            measurement_window_hours=0,  # Multi-window, not single
            measured_at=now,
        )

        self.db.add(outcome)
        await self.db.commit()
        await self.db.refresh(outcome)

        logger.info(
            f"Recorded merchant decision for rec {recommendation_id}: "
            f"decision={effective_decision}, status={measurement_status}"
        )

        return outcome

    # ──────────────────────────────────────────────
    # RULE PERFORMANCE
    # ──────────────────────────────────────────────

    async def get_rule_performance(self, rule_id: UUID, user_id: UUID, days: int = 90) -> dict:
        """Get performance statistics for a specific rule."""

        rule = await self.db.get(PricingRule, rule_id)
        if not rule or rule.user_id != user_id:
            raise ValueError("Rule not found")

        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.rule_id == rule_id, RecommendationOutcome.created_at >= cutoff
        )
        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        if not outcomes:
            return {
                "rule_id": rule_id,
                "rule_name": rule.name,
                "rule_type": rule.rule_type.value if hasattr(rule.rule_type, "value") else str(rule.rule_type),
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

        # Calculate confidence correlation
        confidence_correlation = None
        lifts = [o.revenue_lift_7d for o in outcomes if o.revenue_lift_7d is not None]
        if len(lifts) >= 5:
            conf_values = [float(o.original_confidence) for o in outcomes if o.revenue_lift_7d is not None]
            confidence_correlation = pearson_r(conf_values, lifts)
            if confidence_correlation is not None:
                confidence_correlation = round(confidence_correlation, 4)

        return {
            "rule_id": rule_id,
            "rule_name": rule.name,
            "rule_type": rule.rule_type.value if hasattr(rule.rule_type, "value") else str(rule.rule_type),
            "total_outcomes": total,
            "positive_outcomes": positive,
            "negative_outcomes": negative,
            "neutral_outcomes": neutral,
            "success_rate": success_rate,
            "avg_outcome_score": avg_score,
            "avg_revenue_change_percent": avg_revenue_change,
            "total_revenue_impact": total_revenue_impact,
            "avg_confidence": avg_confidence,
            "confidence_accuracy_correlation": confidence_correlation,
        }

    # ──────────────────────────────────────────────
    # ACCURACY STATS
    # ──────────────────────────────────────────────

    async def get_accuracy_stats(self, user_id: UUID, days: int = 30) -> dict:
        """Get overall accuracy statistics."""

        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.user_id == user_id, RecommendationOutcome.created_at >= cutoff
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

        by_rule_type: dict = {}
        for o in outcomes:
            rt = o.rule_type or "unknown"
            if rt not in by_rule_type:
                by_rule_type[rt] = {"count": 0, "positive": 0, "revenue_impact": Decimal("0")}
            by_rule_type[rt]["count"] += 1
            if o.outcome_label == OutcomeLabel.POSITIVE:
                by_rule_type[rt]["positive"] += 1
            by_rule_type[rt]["revenue_impact"] += o.revenue_change

        for rt, stats in by_rule_type.items():
            stats["success_rate"] = float(
                Decimal(str(stats["positive"] / stats["count"] * 100)).quantize(Decimal("0.01"))
            )
            stats["revenue_impact"] = float(stats["revenue_impact"])

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
            rule_averages.append(
                {
                    "rule_id": str(rule_id),
                    "rule_name": rule.name if rule else "Unknown",
                    "rule_type": data["rule_type"],
                    "avg_score": float(avg.quantize(Decimal("0.01"))),
                    "outcome_count": len(data["scores"]),
                }
            )

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

    # ──────────────────────────────────────────────
    # HISTORICAL ACCURACY (used by confidence calculator)
    # ──────────────────────────────────────────────

    async def get_historical_accuracy_for_rule_type(self, user_id: UUID, rule_type: str, days: int = 90) -> Decimal:
        """Get historical success rate for a rule type (used by confidence calculator)."""

        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.user_id == user_id,
            RecommendationOutcome.rule_type == rule_type,
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.outcome_label != OutcomeLabel.INCONCLUSIVE,
        )
        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        if len(outcomes) < 5:
            return Decimal("0.5")

        positive = sum(1 for o in outcomes if o.outcome_label == OutcomeLabel.POSITIVE)
        return Decimal(str(positive / len(outcomes))).quantize(Decimal("0.01"))


# ──────────────────────────────────────────────
# SHARED UTILITY (used by this module + sibling modules)
# ──────────────────────────────────────────────


def pearson_r(x: list[float], y: list[float]) -> float | None:
    """Calculate Pearson correlation coefficient.

    Shared across outcome modules. Import as:
        from services.pricing.outcome_service import pearson_r
    """
    n = len(x)
    if n < 2:
        return None

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denom_x = sqrt(sum((xi - mean_x) ** 2 for xi in x))
    denom_y = sqrt(sum((yi - mean_y) ** 2 for yi in y))

    if denom_x == 0 or denom_y == 0:
        return None

    return numerator / (denom_x * denom_y)
