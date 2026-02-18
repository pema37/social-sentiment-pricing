"""
Outcome Measurement Service - Multi-window impact tracking.

Background job interface for measuring recommendation outcomes at
7-day, 14-day, and 30-day windows after price application.

The measurement state machine:
  awaiting_decision → decision_recorded → measured_7d → measured_14d → measured_30d

The Celery task (pricing_tasks.py) calls:
  1. get_outcomes_due_for_measurement("7d") → list of outcome rows
  2. For each row, fetch sales data from Shopify/WooCommerce for the window period
  3. record_window_measurement(outcome_id, "7d", revenue, units, margin)

This is the engine that fills the multi-window columns added by the
intelligence environment migration. Without it, those columns stay null
and the feedback loop doesn't compound.

Place at: backend/services/pricing/outcome_measurement.py
"""

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from models.recommendation_outcome import (
    RecommendationOutcome,
    MeasurementStatus,
)


# Window configuration: which status qualifies, how many days must pass
WINDOW_CONFIG = {
    "7d": {
        "required_status": MeasurementStatus.DECISION_RECORDED.value,
        "days_since_applied": 7,
        "next_status": MeasurementStatus.MEASURED_7D.value,
    },
    "14d": {
        "required_status": MeasurementStatus.MEASURED_7D.value,
        "days_since_applied": 14,
        "next_status": MeasurementStatus.MEASURED_14D.value,
    },
    "30d": {
        "required_status": MeasurementStatus.MEASURED_14D.value,
        "days_since_applied": 30,
        "next_status": MeasurementStatus.MEASURED_30D.value,
    },
}

# Also pick up legacy single_measured rows for 7d measurement
LEGACY_STATUS = MeasurementStatus.SINGLE_MEASURED.value


class OutcomeMeasurementService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_outcomes_due_for_measurement(
        self,
        window: str,
        batch_size: int = 100,
    ) -> list[RecommendationOutcome]:
        """Find outcomes due for their next measurement window.

        Args:
            window: "7d", "14d", or "30d"
            batch_size: Max rows to return per call (prevents long-running jobs)

        Returns:
            List of RecommendationOutcome rows ready for measurement.
            The Celery task iterates these and calls record_window_measurement
            after fetching sales data from the merchant's platform.
        """
        config = WINDOW_CONFIG.get(window)
        if not config:
            raise ValueError(f"Invalid window: {window}. Use '7d', '14d', or '30d'.")

        now = datetime.now(UTC)
        cutoff = now - timedelta(days=config["days_since_applied"])

        # Primary query: rows in the expected status
        stmt = (
            select(RecommendationOutcome)
            .where(
                RecommendationOutcome.measurement_status == config["required_status"],
                RecommendationOutcome.price_applied_at <= cutoff,
            )
            .order_by(RecommendationOutcome.price_applied_at.asc())
            .limit(batch_size)
        )

        result = await self.db.execute(stmt)
        outcomes = list(result.scalars().all())

        # For the 7d window, also pick up legacy rows that only had 48h measurement
        if window == "7d":
            remaining = batch_size - len(outcomes)
            if remaining > 0:
                legacy_stmt = (
                    select(RecommendationOutcome)
                    .where(
                        RecommendationOutcome.measurement_status == LEGACY_STATUS,
                        RecommendationOutcome.price_applied_at <= cutoff,
                    )
                    .order_by(RecommendationOutcome.price_applied_at.asc())
                    .limit(remaining)
                )
                legacy_result = await self.db.execute(legacy_stmt)
                outcomes.extend(legacy_result.scalars().all())

        return outcomes

    async def record_window_measurement(
        self,
        outcome_id: UUID,
        window: str,
        revenue: Decimal,
        units: int,
        margin: Optional[Decimal] = None,
    ) -> RecommendationOutcome:
        """Record measurement data for a specific window.

        Called by the Celery task after fetching sales data from
        Shopify/WooCommerce for the window period.

        Args:
            outcome_id: The RecommendationOutcome row to update
            window: "7d", "14d", or "30d"
            revenue: Total revenue for the product during the window period
            units: Total units sold during the window period
            margin: Optional margin percentage during the window period
        """
        outcome = await self.db.get(RecommendationOutcome, outcome_id)
        if not outcome:
            raise ValueError("Outcome not found")

        config = WINDOW_CONFIG.get(window)
        if not config:
            raise ValueError(f"Invalid window: {window}")

        # Calculate revenue lift vs baseline
        lift = self._calculate_lift(outcome, revenue, window)

        # Apply window-specific fields
        if window == "7d":
            outcome.revenue_7d_after = revenue
            outcome.units_7d_after = units
            outcome.revenue_lift_7d = lift
            if margin is not None:
                outcome.margin_7d_after = margin
                if outcome.margin_before is not None:
                    outcome.margin_delta = float(margin - outcome.margin_before)

        elif window == "14d":
            outcome.revenue_14d_after = revenue
            outcome.units_14d_after = units
            outcome.revenue_lift_14d = lift

        elif window == "30d":
            outcome.revenue_30d_after = revenue
            outcome.units_30d_after = units
            outcome.revenue_lift_30d = lift
            if margin is not None:
                outcome.margin_30d_after = margin

        # Advance the state machine
        outcome.measurement_status = config["next_status"]
        outcome.measured_at = datetime.now(UTC)

        self.db.add(outcome)
        await self.db.commit()
        await self.db.refresh(outcome)

        return outcome

    async def mark_measurement_failed(
        self,
        outcome_id: UUID,
        reason: Optional[str] = None,
    ) -> RecommendationOutcome:
        """Mark an outcome as failed to measure.

        Called when the Celery task cannot fetch sales data from
        the merchant's platform (API error, store disconnected, etc).
        The row won't be picked up again by get_outcomes_due_for_measurement.
        """
        outcome = await self.db.get(RecommendationOutcome, outcome_id)
        if not outcome:
            raise ValueError("Outcome not found")

        outcome.measurement_status = MeasurementStatus.MEASUREMENT_FAILED.value
        outcome.measured_at = datetime.now(UTC)

        self.db.add(outcome)
        await self.db.commit()
        await self.db.refresh(outcome)

        return outcome

    async def get_measurement_stats(self) -> dict:
        """Get counts by measurement status. Useful for monitoring dashboards."""

        stats = {}
        for status in MeasurementStatus:
            stmt = select(RecommendationOutcome).where(
                RecommendationOutcome.measurement_status == status.value
            )
            result = await self.db.execute(stmt)
            stats[status.value] = len(result.scalars().all())

        return stats

    # ──────────────────────────────────────────────
    # PRIVATE
    # ──────────────────────────────────────────────

    @staticmethod
    def _calculate_lift(
        outcome: RecommendationOutcome,
        window_revenue: Decimal,
        window: str,
    ) -> Optional[float]:
        """Calculate revenue lift as percentage vs normalized baseline.

        Normalizes the baseline (revenue_before, measured over
        measurement_window_hours) to the same period length as
        the measurement window (7/14/30 days).
        """
        if not outcome.revenue_before or outcome.revenue_before <= 0:
            return None

        baseline_hours = max(outcome.measurement_window_hours, 1)
        baseline_daily = outcome.revenue_before / Decimal(str(baseline_hours / 24))

        window_days = {"7d": 7, "14d": 14, "30d": 30}.get(window)
        if not window_days:
            return None

        normalized_baseline = baseline_daily * Decimal(str(window_days))
        if normalized_baseline <= 0:
            return None

        lift = float(
            (window_revenue - normalized_baseline) / normalized_baseline * 100
        )
        return round(lift, 2)
    

    