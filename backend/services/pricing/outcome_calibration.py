"""
Outcome Calibration Service - Backward learning for the agent pipeline.

Three feedback loops that make the intelligence environment self-improving:

1. CONFIDENCE CALIBRATION → System-wide
   Pearson r between predicted confidence and actual revenue lift.
   Target: r > 0.7 by Month 12 (Metric 3 from the architecture doc).
   If confidence scores don't predict results, the system isn't learning.

2. ELASTICITY ACCURACY → Backward learning to Analyst
   Compare predicted elasticity estimates with observed demand changes.
   When the Analyst consistently overestimates demand sensitivity in a
   category, the category prior should be updated via Bayesian posterior.

3. MERCHANT MODIFICATION PATTERNS → Backward learning to Strategist
   If merchants consistently reduce recommendations by 30%, the
   Strategist's guardrails should adapt. The "preference prior" calibrates
   future recommendation magnitude per merchant.

Place at: backend/services/pricing/outcome_calibration.py
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.recommendation_outcome import (
    MerchantDecision,
    OutcomeLabel,
    RecommendationOutcome,
)
from services.pricing.outcome_service import pearson_r


class OutcomeCalibrationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ──────────────────────────────────────────────
    # 1. CONFIDENCE CALIBRATION (Metric 3)
    # ──────────────────────────────────────────────

    async def get_confidence_calibration(
        self,
        user_id: UUID | None = None,
        product_category: str | None = None,
        days: int = 90,
    ) -> dict:
        """Calculate Pearson r between predicted confidence and actual revenue lift.

        Can be scoped to:
        - A single merchant (user_id) for per-merchant calibration
        - A category (product_category) for cross-merchant calibration
        - Both for narrowest scope
        - Neither for system-wide calibration

        Target: r > 0.7 by Month 12.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.revenue_lift_7d.is_not(None),
            RecommendationOutcome.outcome_label != OutcomeLabel.INCONCLUSIVE,
        )

        if user_id:
            stmt = stmt.where(RecommendationOutcome.user_id == user_id)
        if product_category:
            stmt = stmt.where(RecommendationOutcome.product_category == product_category)

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        if len(outcomes) < 5:
            return {
                "sample_size": len(outcomes),
                "pearson_r": None,
                "calibration_status": "insufficient_data",
                "component_calibration": {},
                "avg_confidence": None,
                "avg_lift": None,
                "message": "Need at least 5 measured outcomes for calibration",
            }

        confidences = [float(o.original_confidence) for o in outcomes]
        lifts = [o.revenue_lift_7d for o in outcomes]

        r = pearson_r(confidences, lifts)

        if r is None:
            status = "calculation_error"
        elif r >= 0.7:
            status = "well_calibrated"
        elif r >= 0.4:
            status = "moderately_calibrated"
        elif r >= 0.0:
            status = "poorly_calibrated"
        else:
            status = "inversely_calibrated"

        # Component-level calibration
        component_calibration = self._calculate_component_calibration(outcomes, lifts)

        return {
            "sample_size": len(outcomes),
            "pearson_r": round(r, 4) if r is not None else None,
            "calibration_status": status,
            "component_calibration": component_calibration,
            "avg_confidence": round(sum(confidences) / len(confidences), 4),
            "avg_lift": round(sum(lifts) / len(lifts), 4),
        }

    async def get_confidence_calibration_by_band(
        self,
        user_id: UUID | None = None,
        days: int = 90,
    ) -> list[dict]:
        """Break down outcome quality by confidence band.

        Shows whether high-confidence recommendations actually outperform
        low-confidence ones. If they don't, the confidence model is broken.

        Bands: 0.0-0.3 (low), 0.3-0.6 (medium), 0.6-0.8 (high), 0.8-1.0 (very high)
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.outcome_label != OutcomeLabel.INCONCLUSIVE,
        )
        if user_id:
            stmt = stmt.where(RecommendationOutcome.user_id == user_id)

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        bands = [
            {"label": "low", "min": 0.0, "max": 0.3},
            {"label": "medium", "min": 0.3, "max": 0.6},
            {"label": "high", "min": 0.6, "max": 0.8},
            {"label": "very_high", "min": 0.8, "max": 1.01},
        ]

        results = []
        for band in bands:
            band_outcomes = [o for o in outcomes if band["min"] <= float(o.original_confidence) < band["max"]]

            if not band_outcomes:
                results.append(
                    {
                        "band": band["label"],
                        "confidence_range": f"{band['min']:.1f}-{band['max']:.1f}",
                        "count": 0,
                        "success_rate": None,
                        "avg_lift_7d": None,
                    }
                )
                continue

            positive = sum(1 for o in band_outcomes if o.outcome_label == OutcomeLabel.POSITIVE)
            lifts = [o.revenue_lift_7d for o in band_outcomes if o.revenue_lift_7d is not None]

            results.append(
                {
                    "band": band["label"],
                    "confidence_range": f"{band['min']:.1f}-{band['max']:.1f}",
                    "count": len(band_outcomes),
                    "success_rate": round(positive / len(band_outcomes) * 100, 2),
                    "avg_lift_7d": round(sum(lifts) / len(lifts), 2) if lifts else None,
                }
            )

        return results

    # ──────────────────────────────────────────────
    # 2. ELASTICITY ACCURACY (backward learning → Analyst)
    # ──────────────────────────────────────────────

    async def get_elasticity_accuracy(
        self,
        user_id: UUID | None = None,
        product_category: str | None = None,
        days: int = 90,
    ) -> dict:
        """Compare predicted elasticity with observed demand response.

        When the Analyst consistently overestimates demand sensitivity,
        the Bayesian category prior should be tightened. This method
        provides the data to inform that update.

        Observed PED = (% change in units) / (% change in price)
        Prediction bias = avg(predicted) - avg(observed)
        Positive bias = overestimates sensitivity (predicts bigger volume swings)
        Negative bias = underestimates sensitivity
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.elasticity_estimate.is_not(None),
            RecommendationOutcome.units_change_percent.is_not(None),
            RecommendationOutcome.price_change_percent != 0,
        )
        if user_id:
            stmt = stmt.where(RecommendationOutcome.user_id == user_id)
        if product_category:
            stmt = stmt.where(RecommendationOutcome.product_category == product_category)

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        if len(outcomes) < 3:
            return {
                "sample_size": len(outcomes),
                "avg_predicted_elasticity": None,
                "avg_observed_elasticity": None,
                "prediction_bias": None,
                "bias_direction": None,
                "correlation": None,
                "message": "Need at least 3 outcomes with elasticity data",
            }

        predicted = []
        observed = []

        for o in outcomes:
            price_pct = float(o.price_change_percent)
            if price_pct == 0:
                continue
            observed_ped = float(o.units_change_percent) / price_pct
            observed.append(observed_ped)
            predicted.append(o.elasticity_estimate)

        if not observed:
            return {
                "sample_size": 0,
                "avg_predicted_elasticity": None,
                "avg_observed_elasticity": None,
                "prediction_bias": None,
                "bias_direction": None,
                "correlation": None,
                "message": "No valid elasticity observations",
            }

        avg_predicted = round(sum(predicted) / len(predicted), 4)
        avg_observed = round(sum(observed) / len(observed), 4)
        bias = round(avg_predicted - avg_observed, 4)

        # How well do predictions track observations?
        correlation = pearson_r(predicted, observed)
        if correlation is not None:
            correlation = round(correlation, 4)

        return {
            "sample_size": len(observed),
            "avg_predicted_elasticity": avg_predicted,
            "avg_observed_elasticity": avg_observed,
            "prediction_bias": bias,
            "bias_direction": "overestimates" if bias > 0.05 else "underestimates" if bias < -0.05 else "accurate",
            "correlation": correlation,
        }

    async def get_elasticity_accuracy_by_category(
        self,
        user_id: UUID | None = None,
        days: int = 90,
    ) -> list[dict]:
        """Elasticity accuracy broken down by product category.

        Surfaces which categories have the worst prediction bias,
        so the Analyst knows where to tighten Bayesian priors first.
        Sorted by absolute bias descending (worst first).
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.elasticity_estimate.is_not(None),
            RecommendationOutcome.units_change_percent.is_not(None),
            RecommendationOutcome.price_change_percent != 0,
            RecommendationOutcome.product_category.is_not(None),
        )
        if user_id:
            stmt = stmt.where(RecommendationOutcome.user_id == user_id)

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        # Group by category
        categories: dict = {}
        for o in outcomes:
            cat = o.product_category
            if cat not in categories:
                categories[cat] = {"predicted": [], "observed": []}

            price_pct = float(o.price_change_percent)
            if price_pct == 0:
                continue

            observed_ped = float(o.units_change_percent) / price_pct
            categories[cat]["predicted"].append(o.elasticity_estimate)
            categories[cat]["observed"].append(observed_ped)

        results = []
        for cat, data in categories.items():
            if len(data["observed"]) < 2:
                continue

            avg_pred = sum(data["predicted"]) / len(data["predicted"])
            avg_obs = sum(data["observed"]) / len(data["observed"])
            bias = avg_pred - avg_obs

            results.append(
                {
                    "category": cat,
                    "sample_size": len(data["observed"]),
                    "avg_predicted": round(avg_pred, 4),
                    "avg_observed": round(avg_obs, 4),
                    "bias": round(bias, 4),
                    "abs_bias": round(abs(bias), 4),
                    "direction": "overestimates" if bias > 0.05 else "underestimates" if bias < -0.05 else "accurate",
                }
            )

        results.sort(key=lambda x: x["abs_bias"], reverse=True)
        return results

    # ──────────────────────────────────────────────
    # 3. MERCHANT MODIFICATION PATTERNS (backward learning → Strategist)
    # ──────────────────────────────────────────────

    async def get_merchant_modification_pattern(
        self,
        user_id: UUID,
        product_category: str | None = None,
        days: int = 90,
    ) -> dict:
        """Analyze how a merchant modifies recommendations.

        If merchants consistently reduce suggestions by 30%, the Strategist
        should learn to recommend smaller changes. The preference_prior is
        a scaling factor:
          - 1.0 = merchant accepts as-is
          - 0.7 = merchant typically reduces by 30%
          - 1.1 = merchant typically increases by 10%

        The Strategist multiplies its raw recommendation magnitude by
        preference_prior to pre-calibrate for merchant behavior.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(RecommendationOutcome).where(
            RecommendationOutcome.user_id == user_id,
            RecommendationOutcome.created_at >= cutoff,
            RecommendationOutcome.merchant_decision.in_(
                [
                    MerchantDecision.ACCEPTED.value,
                    MerchantDecision.MODIFIED.value,
                    MerchantDecision.REJECTED.value,
                ]
            ),
        )
        if product_category:
            stmt = stmt.where(RecommendationOutcome.product_category == product_category)

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        if not outcomes:
            return {
                "total_decisions": 0,
                "acceptance_rate": None,
                "modification_rate": None,
                "rejection_rate": None,
                "avg_modification_percent": None,
                "preference_prior": None,
                "by_direction": {},
            }

        total = len(outcomes)
        accepted = sum(1 for o in outcomes if o.merchant_decision == MerchantDecision.ACCEPTED.value)
        modified = sum(1 for o in outcomes if o.merchant_decision == MerchantDecision.MODIFIED.value)
        rejected = sum(1 for o in outcomes if o.merchant_decision == MerchantDecision.REJECTED.value)

        # Average modification percent
        modifications = [
            o.merchant_modification_percent for o in outcomes if o.merchant_modification_percent is not None
        ]
        avg_modification = None
        if modifications:
            avg_modification = round(sum(modifications) / len(modifications), 2)

        # Preference prior
        preference_prior = None
        if avg_modification is not None:
            preference_prior = round(1.0 + (avg_modification / 100), 4)

        # Break down by price direction (increase vs decrease)
        by_direction = self._modification_by_direction(outcomes)

        return {
            "total_decisions": total,
            "acceptance_rate": round(accepted / total * 100, 2),
            "modification_rate": round(modified / total * 100, 2),
            "rejection_rate": round(rejected / total * 100, 2),
            "avg_modification_percent": avg_modification,
            "preference_prior": preference_prior,
            "by_direction": by_direction,
        }

    async def get_merchant_rejection_reasons(
        self,
        user_id: UUID,
        days: int = 90,
        limit: int = 20,
    ) -> list[dict]:
        """Get recent rejection reasons for a merchant.

        Surfaces why merchants reject recommendations so the Strategist
        can learn patterns (e.g., "too aggressive", "wrong timing",
        "competitor context missing").
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = (
            select(RecommendationOutcome)
            .where(
                RecommendationOutcome.user_id == user_id,
                RecommendationOutcome.created_at >= cutoff,
                RecommendationOutcome.merchant_decision == MerchantDecision.REJECTED.value,
            )
            .order_by(RecommendationOutcome.created_at.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        return [
            {
                "outcome_id": str(o.id),
                "product_id": str(o.product_id),
                "product_category": o.product_category,
                "suggested_change_percent": float(o.price_change_percent),
                "confidence": float(o.original_confidence),
                "decided_at": o.decided_at.isoformat() if o.decided_at else None,
            }
            for o in outcomes
        ]

    # ──────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────

    @staticmethod
    def _calculate_component_calibration(
        outcomes: list[RecommendationOutcome],
        lifts: list[float],
    ) -> dict:
        """Calculate per-component confidence correlation with revenue lift."""
        component_calibration = {}

        for component in ["elasticity", "position", "urgency", "data_quality"]:
            field = f"confidence_{component}"

            # Build paired lists: only rows where this component has a value
            pairs = [
                (getattr(o, field), o.revenue_lift_7d)
                for o in outcomes
                if getattr(o, field) is not None and o.revenue_lift_7d is not None
            ]

            if len(pairs) >= 5:
                comp_values = [p[0] for p in pairs]
                comp_lifts = [p[1] for p in pairs]
                r = pearson_r(comp_values, comp_lifts)
                component_calibration[component] = round(r, 4) if r is not None else None

        return component_calibration

    @staticmethod
    def _modification_by_direction(outcomes: list[RecommendationOutcome]) -> dict:
        """Break down merchant modifications by price direction.

        Merchants might accept increases but reduce decrease magnitude,
        or vice versa. This distinction matters for Strategist calibration.
        """
        directions = {"increase": [], "decrease": [], "hold": []}

        for o in outcomes:
            direction = "hold"
            if float(o.price_change_percent) > 0.5:
                direction = "increase"
            elif float(o.price_change_percent) < -0.5:
                direction = "decrease"

            if o.merchant_modification_percent is not None:
                directions[direction].append(o.merchant_modification_percent)

        result = {}
        for direction, mods in directions.items():
            if mods:
                avg = round(sum(mods) / len(mods), 2)
                result[direction] = {
                    "count": len(mods),
                    "avg_modification_percent": avg,
                    "preference_prior": round(1.0 + (avg / 100), 4),
                }

        return result
