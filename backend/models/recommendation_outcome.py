"""
Recommendation Outcome - Tracks actual performance after price changes.

This model serves three architectural purposes in the intelligence environment:

1. FEEDBACK LOOP: Outcomes flow back to improve agent behavior.
   - Scout: categories with data gaps causing failures → more aggressive scraping
   - Analyst: elasticity overestimates → Bayesian prior updates
   - Strategist: merchant modification patterns → guardrail calibration

2. CROSS-MERCHANT INTELLIGENCE: Aggregated, anonymized outcomes power
   category benchmarks (activates at 5+ merchants per category).

3. CONFIDENCE CALIBRATION: Predicted confidence scores are compared to
   actual outcomes. Target: Pearson r > 0.7 by Month 12.

Original fields: basic before/after tracking, outcome scoring, rule linkage.
Intelligence environment additions: multi-window measurement, confidence
decomposition, agent evidence chain, merchant decision tracking, cross-merchant
fields, analyst scoring snapshot, measurement status state machine.
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlmodel import Field, SQLModel

# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────


class OutcomeLabel(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    INCONCLUSIVE = "inconclusive"


class MerchantDecision(str, Enum):
    """What the merchant did with the recommendation."""

    ACCEPTED = "accepted"
    MODIFIED = "modified"
    REJECTED = "rejected"
    AUTO_APPLIED = "auto_applied"
    EXPIRED = "expired"
    PENDING = "pending"


class MeasurementStatus(str, Enum):
    """Tracks which impact windows have been measured.

    State machine:
    awaiting_decision → decision_recorded → measured_7d → measured_14d → measured_30d

    The background job queries by status + price_applied_at to find rows
    due for their next measurement window.
    """

    AWAITING_DECISION = "awaiting_decision"
    DECISION_RECORDED = "decision_recorded"
    SINGLE_MEASURED = "single_measured"  # Legacy: existing 48h measurement
    MEASURED_7D = "measured_7d"
    MEASURED_14D = "measured_14d"
    MEASURED_30D = "measured_30d"
    MEASUREMENT_FAILED = "measurement_failed"


class RecommendationSource(str, Enum):
    """Which pipeline produced this recommendation."""

    FULL_PIPELINE = "full_pipeline"
    RULE_BASED = "rule_based"
    MANUAL = "manual"
    SENTIMENT_TRIGGERED = "sentiment_triggered"
    CRISIS_OVERRIDE = "crisis_override"


# ──────────────────────────────────────────────
# Model
# ──────────────────────────────────────────────


class RecommendationOutcome(SQLModel, table=True):
    __tablename__ = "recommendation_outcomes"

    # ── Identity ──
    id: UUID = Field(default_factory=uuid4, sa_column=Column(PG_UUID(as_uuid=True), primary_key=True))
    user_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    recommendation_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, unique=True, index=True))
    product_id: UUID = Field(sa_column=Column(PG_UUID(as_uuid=True), nullable=False, index=True))
    rule_id: UUID | None = Field(default=None, sa_column=Column(PG_UUID(as_uuid=True), nullable=True, index=True))
    rule_type: str | None = Field(default=None, max_length=50)

    # ── Recommendation source ──
    recommendation_source: str = Field(
        default=RecommendationSource.RULE_BASED.value,
        max_length=30,
    )

    # ── Price data ──
    price_before: Decimal = Field(decimal_places=2)
    price_after: Decimal = Field(decimal_places=2)
    price_change_percent: Decimal = Field(decimal_places=2)

    # ── Original single-window metrics (existing) ──
    sales_count_before: int = Field(default=0)
    units_sold_before: int = Field(default=0)
    revenue_before: Decimal = Field(default=Decimal("0"), decimal_places=2)
    avg_daily_sales_before: Decimal = Field(default=Decimal("0"), decimal_places=2)

    sales_count_after: int = Field(default=0)
    units_sold_after: int = Field(default=0)
    revenue_after: Decimal = Field(default=Decimal("0"), decimal_places=2)
    avg_daily_sales_after: Decimal = Field(default=Decimal("0"), decimal_places=2)

    revenue_change: Decimal = Field(default=Decimal("0"), decimal_places=2)
    revenue_change_percent: Decimal | None = Field(default=None, decimal_places=2)
    units_change: int = Field(default=0)
    units_change_percent: Decimal | None = Field(default=None, decimal_places=2)

    # ── Outcome scoring (existing) ──
    outcome_score: Decimal = Field(default=Decimal("0"), decimal_places=2)
    outcome_label: OutcomeLabel = Field(default=OutcomeLabel.INCONCLUSIVE)

    # ── Confidence: overall (existing) + decomposition (new) ──
    original_confidence: Decimal = Field(decimal_places=2)
    confidence_elasticity: float | None = Field(default=None)
    confidence_position: float | None = Field(default=None)
    confidence_urgency: float | None = Field(default=None)
    confidence_data_quality: float | None = Field(default=None)

    # ── Analyst scoring snapshot (new) ──
    # What the Analyst computed at time of recommendation.
    # Enables "predicted vs actual" for Bayesian prior updates.
    elasticity_estimate: float | None = Field(default=None)
    urgency_score: float | None = Field(default=None)
    sentiment_score: float | None = Field(default=None)
    competitive_position_index: float | None = Field(default=None)
    competitor_count: int | None = Field(default=None)
    data_completeness: float | None = Field(default=None)

    # ── Merchant decision tracking (new) ──
    # What the merchant actually did — the modification pattern is
    # backward learning fuel for the Strategist's guardrail calibration.
    merchant_decision: str = Field(
        default=MerchantDecision.ACCEPTED.value,
        max_length=20,
    )
    actual_price_set: Decimal | None = Field(default=None, decimal_places=2)
    merchant_modification_percent: float | None = Field(default=None)
    decided_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))

    # ── Multi-window revenue measurement (new) ──
    # Filled by background job at 7d, 14d, 30d after price_applied_at.
    revenue_7d_after: Decimal | None = Field(default=None, decimal_places=2)
    revenue_14d_after: Decimal | None = Field(default=None, decimal_places=2)
    revenue_30d_after: Decimal | None = Field(default=None, decimal_places=2)

    units_7d_after: int | None = Field(default=None)
    units_14d_after: int | None = Field(default=None)
    units_30d_after: int | None = Field(default=None)

    revenue_lift_7d: float | None = Field(default=None)
    revenue_lift_14d: float | None = Field(default=None)
    revenue_lift_30d: float | None = Field(default=None)

    # ── Margin tracking (new) ──
    margin_before: Decimal | None = Field(default=None, decimal_places=3)
    margin_7d_after: Decimal | None = Field(default=None, decimal_places=3)
    margin_30d_after: Decimal | None = Field(default=None, decimal_places=3)
    margin_delta: float | None = Field(default=None)

    # ── Agent evidence chain (new) ──
    # Full provenance for failure tracing. When a recommendation fails,
    # trace which agent's reasoning was wrong.
    scout_evidence: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    analyst_evidence: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    strategist_evidence: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))

    # ── Cross-merchant intelligence fields (new) ──
    # Required for category benchmarks (activates at 5+ merchants).
    product_category: str | None = Field(default=None, max_length=100)
    store_platform: str | None = Field(default=None, max_length=20)

    # ── Measurement status (new) ──
    measurement_status: str = Field(
        default=MeasurementStatus.AWAITING_DECISION.value,
        max_length=30,
    )

    # ── Timestamps (existing) ──
    price_applied_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    measurement_window_hours: int = Field(default=48)
    measured_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    )

    class Config:
        use_enum_values = True
