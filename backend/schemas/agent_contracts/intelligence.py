"""
Intelligence Environment Response Schemas.

API response models consumed by the frontend hooks in use-outcomes.ts.
These describe intelligence environment concepts (calibration, benchmarks,
data gaps) — not basic pricing CRUD.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Confidence Calibration ────────────────────────────────────────

class CalibrationBucket(BaseModel):
    """One bucket in the calibration curve."""
    confidence_range_low: float = Field(ge=0.0, le=1.0)
    confidence_range_high: float = Field(ge=0.0, le=1.0)
    predicted_success_rate: float = Field(ge=0.0, le=1.0)
    actual_success_rate: float = Field(ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)
    avg_revenue_lift_pct: Optional[float] = None


class ConfidenceCalibrationResponse(BaseModel):
    """
    Response for GET /outcomes/calibration

    Perfect calibration = the diagonal line. Over-confident systems
    show actual < predicted; under-confident show actual > predicted.
    """
    buckets: list[CalibrationBucket]
    overall_calibration_error: float = Field(
        ge=0.0,
        description="MAE between predicted and actual across all buckets.",
    )
    total_outcomes: int = Field(ge=0)
    period_days: int
    category: Optional[str] = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Merchant Modification Patterns ────────────────────────────────

class ModificationDetail(BaseModel):
    """Detail of how the merchant commonly modifies recommendations."""
    direction: str = Field(description="'rounds_down', 'rounds_up', 'reduces_magnitude', 'increases_magnitude'")
    frequency: float = Field(ge=0.0, le=1.0, description="How often this pattern occurs")
    avg_adjustment_pct: float = Field(description="Average % the merchant adjusts by")


class MerchantPatternResponse(BaseModel):
    """
    Response for GET /outcomes/merchant-patterns

    Feeds Tier 1 context injection — the Strategist uses this
    to pre-adjust recommendations toward the merchant's preferences.
    """
    total_decisions: int = Field(ge=0)
    acceptance_rate: float = Field(ge=0.0, le=1.0)
    modification_rate: float = Field(ge=0.0, le=1.0)
    rejection_rate: float = Field(ge=0.0, le=1.0)
    avg_time_to_decision_hours: Optional[float] = Field(
        default=None, ge=0.0,
        description="Average hours between recommendation and merchant action",
    )
    common_modifications: list[ModificationDetail] = Field(default_factory=list)
    preferred_change_magnitude: Optional[float] = Field(
        default=None,
        description="Median % change the merchant actually applies.",
    )
    period_days: int
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Category Benchmarks ───────────────────────────────────────────

class CategoryBenchmarkResponse(BaseModel):
    """
    Response for GET /outcomes/benchmarks/{category}

    Cross-merchant aggregates. Only populated when k-anonymity >= 5.
    """
    category: str
    merchant_count: int = Field(ge=0, description="Must be >= 5")
    has_sufficient_data: bool = Field(
        description="False if merchant_count < 5. All metrics will be null.",
    )

    # Pricing benchmarks
    median_price: Optional[Decimal] = None
    price_25th_percentile: Optional[Decimal] = None
    price_75th_percentile: Optional[Decimal] = None
    avg_margin_pct: Optional[float] = None

    # Outcome benchmarks
    avg_acceptance_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    avg_revenue_lift_7d: Optional[float] = None
    best_performing_strategy: Optional[str] = Field(
        default=None,
        description="'competitive_match', 'premium', 'undercut', etc.",
    )

    # Optimal change range (for Strategist guardrails)
    optimal_change_min_pct: Optional[float] = None
    optimal_change_max_pct: Optional[float] = None
    optimal_change_median_pct: Optional[float] = None

    period_days: int
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Data Gap Failure Rates ────────────────────────────────────────

class DataGapDetail(BaseModel):
    """One specific gap in the feedback loop."""
    gap_type: str = Field(
        description="'unmeasured_recommendation', 'failed_sales_pull', 'no_outcome_history', 'stale_competitor_data'",
    )
    count: int = Field(ge=0)
    percentage: float = Field(ge=0.0, le=100.0, description="As % of total relevant items")
    affected_product_ids: list[UUID] = Field(
        default_factory=list,
        description="Up to 10 product IDs affected (for debugging)",
    )


class DataGapFailureRate(BaseModel):
    """Overall failure rate for one measurement window."""
    window: str = Field(description="'24h', '48h', '7d', '14d', '30d'")
    total_expected: int = Field(ge=0)
    total_measured: int = Field(ge=0)
    failure_rate: float = Field(ge=0.0, le=1.0)


class DataGapResponse(BaseModel):
    """
    Response for GET /outcomes/data-gaps

    A feedback loop with unmeasured outcomes is worse than no loop —
    it creates silent confidence in uncalibrated scores.
    """
    gaps: list[DataGapDetail]
    measurement_failure_rates: list[DataGapFailureRate] = Field(default_factory=list)
    total_recommendations: int = Field(ge=0)
    total_measured: int = Field(ge=0)
    overall_measurement_rate: float = Field(
        ge=0.0, le=1.0,
        description="total_measured / total_recommendations. Target: > 0.8",
    )
    products_with_no_outcomes: int = Field(ge=0)
    period_days: int
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Elasticity Accuracy ───────────────────────────────────────────

class ElasticityAccuracyBucket(BaseModel):
    """One bucket comparing predicted vs observed elasticity."""
    predicted_elasticity_range: str = Field(description="e.g. '-2.0 to -1.5'")
    avg_predicted: float
    avg_observed: float
    sample_count: int = Field(ge=0)
    mean_absolute_error: float = Field(ge=0.0)


class ElasticityAccuracyResponse(BaseModel):
    """
    Response for GET /outcomes/elasticity-accuracy

    Core signal for Analyst model quality. Pearson r > 0.5 = good, < 0.3 = retrain.
    """
    buckets: list[ElasticityAccuracyBucket]
    overall_mae: float = Field(ge=0.0, description="Mean absolute error. Lower = better.")
    correlation: Optional[float] = Field(
        default=None, ge=-1.0, le=1.0,
        description="Pearson correlation between predicted and observed.",
    )
    total_observations: int = Field(ge=0)
    period_days: int
    category: Optional[str] = None
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Dashboard Summaries ───────────────────────────────────────────

class OutcomeCardData(BaseModel):
    """Lightweight summary for frontend OutcomeCard component."""
    outcome_id: UUID
    product_name: str
    outcome_label: str
    outcome_score: Decimal
    revenue_change_percent: Optional[Decimal] = None
    confidence_score: Decimal
    measured_at: datetime
    measurement_window: str = Field(description="'24h', '48h', '7d', '14d', '30d'")


class AccuracyStats(BaseModel):
    """Lightweight accuracy summary for dashboard header."""
    total_outcomes: int
    positive_rate: float
    negative_rate: float
    neutral_rate: float
    avg_confidence: float
    avg_revenue_lift: Optional[float] = None
    calibration_error: Optional[float] = None


    