# backend/schemas/pricing.py
"""
Pricing Schemas - DTOs for rules, recommendations, and settings.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from models.price_recommendation import RecommendationStatus
from models.pricing_rule import RuleAction, RuleType
from models.recommendation_outcome import OutcomeLabel

# ═══════════════════════════════════════════════════════════════
# PRICING RULE SCHEMAS
# ═══════════════════════════════════════════════════════════════


class PricingRuleCreate(BaseModel):
    # Legacy single product (now optional)
    product_id: UUID | None = None

    # NEW: Scoping options
    applies_to_all_products: bool = False
    applies_to_products: list[str] | None = None  # List of UUID strings
    applies_to_categories: list[str] | None = None

    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    rule_type: RuleType
    priority: int = 0

    sentiment_threshold: Decimal | None = None
    sentiment_direction: str | None = None

    competitor_id: UUID | None = None
    competitor_margin_percent: Decimal | None = None
    price_position: str | None = None

    time_days: str | None = None
    time_start: str | None = None
    time_end: str | None = None

    volume_threshold: int | None = None
    volume_window_hours: int | None = 24

    viral_threshold_reach: int | None = None
    viral_threshold_engagement: int | None = None
    viral_sentiment_min: Decimal | None = None

    action: RuleAction
    action_value: Decimal

    min_price: Decimal | None = None
    max_price: Decimal | None = None
    max_change_percent: Decimal = Decimal("15.0")
    cooldown_hours: int = 24


class PricingRuleUpdate(BaseModel):
    # NEW: Scoping options
    applies_to_all_products: bool | None = None
    applies_to_products: list[str] | None = None
    applies_to_categories: list[str] | None = None

    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    is_active: bool | None = None
    priority: int | None = None

    sentiment_threshold: Decimal | None = None
    sentiment_direction: str | None = None

    competitor_id: UUID | None = None
    competitor_margin_percent: Decimal | None = None
    price_position: str | None = None

    time_days: str | None = None
    time_start: str | None = None
    time_end: str | None = None

    volume_threshold: int | None = None
    volume_window_hours: int | None = None

    viral_threshold_reach: int | None = None
    viral_threshold_engagement: int | None = None
    viral_sentiment_min: Decimal | None = None

    action: RuleAction | None = None
    action_value: Decimal | None = None

    min_price: Decimal | None = None
    max_price: Decimal | None = None
    max_change_percent: Decimal | None = None
    cooldown_hours: int | None = None


class PricingRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    product_id: UUID | None  # Now optional

    # NEW: Scoping fields
    applies_to_all_products: bool = False
    applies_to_products: list[str] | None = None
    applies_to_categories: list[str] | None = None

    name: str
    description: str | None
    rule_type: RuleType
    is_active: bool
    priority: int

    sentiment_threshold: Decimal | None
    sentiment_direction: str | None

    competitor_id: UUID | None
    competitor_margin_percent: Decimal | None
    price_position: str | None

    time_days: str | None
    time_start: str | None
    time_end: str | None

    volume_threshold: int | None
    volume_window_hours: int | None

    viral_threshold_reach: int | None
    viral_threshold_engagement: int | None
    viral_sentiment_min: Decimal | None

    action: RuleAction
    action_value: Decimal

    min_price: Decimal | None
    max_price: Decimal | None
    max_change_percent: Decimal
    cooldown_hours: int
    last_triggered_at: datetime | None

    created_at: datetime
    updated_at: datetime | None


# ═══════════════════════════════════════════════════════════════
# PRICE RECOMMENDATION SCHEMAS
# ═══════════════════════════════════════════════════════════════


class PriceRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    product_id: UUID
    triggered_rule_id: UUID | None

    # Add defaults for safety
    current_price: Decimal = Decimal("0")
    recommended_price: Decimal = Decimal("0")
    change_percent: Decimal = Decimal("0")
    confidence_score: Decimal = Decimal("0")

    reasoning: str = ""
    factors: dict = Field(default_factory=dict)

    status: RecommendationStatus
    requires_approval: bool
    valid_until: datetime

    reviewed_by: UUID | None
    reviewed_at: datetime | None
    rejection_reason: str | None

    applied_at: datetime | None
    applied_to_platform: str | None

    created_at: datetime


class RecommendationApprove(BaseModel):
    """Approve a pending recommendation."""

    pass


class RecommendationReject(BaseModel):
    """Reject a pending recommendation."""

    reason: str | None = Field(default=None, max_length=500)


class RecommendationListParams(BaseModel):
    """Query params for listing recommendations."""

    status: RecommendationStatus | None = None
    product_id: UUID | None = None
    limit: int = Field(default=20, le=100)
    offset: int = 0


# ═══════════════════════════════════════════════════════════════
# PRICING SETTINGS SCHEMAS
# ═══════════════════════════════════════════════════════════════


class PricingSettingsUpdate(BaseModel):
    auto_approve_enabled: bool | None = None
    auto_approve_max_increase: Decimal | None = None
    auto_approve_max_decrease: Decimal | None = None
    auto_approve_min_confidence: Decimal | None = None
    min_margin_percent: Decimal | None = None

    max_auto_changes_per_day: int | None = None
    global_cooldown_hours: int | None = None

    blackout_hours_start: int | None = None
    blackout_hours_end: int | None = None

    require_approval_above_price: Decimal | None = None
    recommendation_valid_hours: int | None = None

    notify_on_auto_apply: bool | None = None
    notify_on_pending: bool | None = None
    notification_email: str | None = None
    notification_slack_webhook: str | None = None


class PricingSettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID

    auto_approve_enabled: bool
    auto_approve_max_increase: Decimal
    auto_approve_max_decrease: Decimal
    auto_approve_min_confidence: Decimal
    min_margin_percent: Decimal

    max_auto_changes_per_day: int
    global_cooldown_hours: int

    blackout_hours_start: int | None
    blackout_hours_end: int | None

    require_approval_above_price: Decimal | None
    recommendation_valid_hours: int

    notify_on_auto_apply: bool
    notify_on_pending: bool
    notification_email: str | None
    notification_slack_webhook: str | None

    created_at: datetime
    updated_at: datetime | None


# ═══════════════════════════════════════════════════════════════
# RULE TEST SCHEMAS
# ═══════════════════════════════════════════════════════════════


class MockSignals(BaseModel):
    """Optional mock signals for rule testing."""

    sentiment_score: Decimal | None = None
    sentiment_change_24h: Decimal | None = None
    mention_count_24h: int | None = None
    mention_baseline: int | None = None
    viral_detected: bool | None = None
    viral_reach: int | None = None
    viral_engagement: int | None = None
    viral_sentiment: Decimal | None = None
    competitor_prices: dict[str, Decimal] | None = None


class RuleTestRequest(BaseModel):
    """Request body for testing a rule."""

    mock_signals: MockSignals | None = None


class RuleTestResponse(BaseModel):
    """Response from testing a rule."""

    rule_id: UUID
    rule_name: str
    would_trigger: bool
    match_details: dict | None = None
    signals_used: dict
    calculated_price: Decimal | None = None
    change_percent: Decimal | None = None
    reason: str | None = None


# ═══════════════════════════════════════════════════════════════
# PRICING SIMULATION SCHEMAS
# ═══════════════════════════════════════════════════════════════


class SimulationRequest(BaseModel):
    """Request body for price simulation."""

    product_id: UUID
    mock_signals: MockSignals | None = None


class SimulationResponse(BaseModel):
    """Response from pricing simulation."""

    product_id: UUID
    product_name: str
    current_price: Decimal
    rules_evaluated: int
    rules_triggered: int
    triggered_rules: list[RuleTestResponse]
    best_recommendation: dict | None = None


# ═══════════════════════════════════════════════════════════════
# OUTCOME TRACKING SCHEMAS
# ═══════════════════════════════════════════════════════════════


class OutcomeRecordRequest(BaseModel):
    """Request to record outcome metrics."""

    sales_count_before: int = Field(ge=0)
    units_sold_before: int = Field(ge=0)
    revenue_before: Decimal = Field(ge=0)
    sales_count_after: int = Field(ge=0)
    units_sold_after: int = Field(ge=0)
    revenue_after: Decimal = Field(ge=0)
    measurement_window_hours: int = Field(default=48, ge=1, le=168)


class OutcomeResponse(BaseModel):
    """Response for a recorded outcome."""

    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    recommendation_id: UUID
    product_id: UUID
    rule_id: UUID | None
    rule_type: str | None

    price_before: Decimal
    price_after: Decimal
    price_change_percent: Decimal

    sales_count_before: int
    units_sold_before: int
    revenue_before: Decimal

    sales_count_after: int
    units_sold_after: int
    revenue_after: Decimal

    revenue_change: Decimal
    revenue_change_percent: Decimal | None
    units_change: int
    units_change_percent: Decimal | None

    outcome_score: Decimal
    outcome_label: OutcomeLabel
    original_confidence: Decimal

    price_applied_at: datetime
    measurement_window_hours: int
    measured_at: datetime
    created_at: datetime


class RulePerformanceResponse(BaseModel):
    """Performance stats for a single rule."""

    rule_id: UUID
    rule_name: str
    rule_type: str

    total_outcomes: int
    positive_outcomes: int
    negative_outcomes: int
    neutral_outcomes: int

    success_rate: Decimal
    avg_outcome_score: Decimal
    avg_revenue_change_percent: Decimal | None

    total_revenue_impact: Decimal
    avg_confidence: Decimal
    confidence_accuracy_correlation: Decimal | None


class AccuracyStatsResponse(BaseModel):
    """Overall accuracy statistics."""

    period_days: int
    total_outcomes: int

    positive_count: int
    negative_count: int
    neutral_count: int
    inconclusive_count: int

    overall_success_rate: Decimal
    avg_outcome_score: Decimal

    total_revenue_impact: Decimal
    avg_revenue_change_percent: Decimal | None

    by_rule_type: dict
    top_performing_rules: list[dict]
    worst_performing_rules: list[dict]
