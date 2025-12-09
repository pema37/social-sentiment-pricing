# backend/schemas/pricing.py
"""
Pricing Schemas - DTOs for rules, recommendations, and settings.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from models.pricing_rule import RuleType, RuleAction
from models.price_recommendation import RecommendationStatus
from models.recommendation_outcome import OutcomeLabel


# ═══════════════════════════════════════════════════════════════
# PRICING RULE SCHEMAS
# ═══════════════════════════════════════════════════════════════

class PricingRuleCreate(BaseModel):
    product_id: UUID
    name: str = Field(max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    rule_type: RuleType
    priority: int = 0
    
    sentiment_threshold: Optional[Decimal] = None
    sentiment_direction: Optional[str] = None
    
    competitor_id: Optional[UUID] = None
    competitor_margin_percent: Optional[Decimal] = None
    
    time_days: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    
    volume_threshold: Optional[int] = None
    volume_window_hours: Optional[int] = 24
    
    viral_threshold_reach: Optional[int] = None
    viral_threshold_engagement: Optional[int] = None
    viral_sentiment_min: Optional[Decimal] = None
    
    action: RuleAction
    action_value: Decimal
    
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    max_change_percent: Decimal = Decimal("15.0")
    cooldown_hours: int = 24


class PricingRuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None
    
    sentiment_threshold: Optional[Decimal] = None
    sentiment_direction: Optional[str] = None
    
    competitor_id: Optional[UUID] = None
    competitor_margin_percent: Optional[Decimal] = None
    
    time_days: Optional[str] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None
    
    volume_threshold: Optional[int] = None
    volume_window_hours: Optional[int] = None
    
    viral_threshold_reach: Optional[int] = None
    viral_threshold_engagement: Optional[int] = None
    viral_sentiment_min: Optional[Decimal] = None
    
    action: Optional[RuleAction] = None
    action_value: Optional[Decimal] = None
    
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    max_change_percent: Optional[Decimal] = None
    cooldown_hours: Optional[int] = None


class PricingRuleResponse(BaseModel):
    id: UUID
    user_id: UUID
    product_id: UUID
    name: str
    description: Optional[str]
    rule_type: RuleType
    is_active: bool
    priority: int
    
    sentiment_threshold: Optional[Decimal]
    sentiment_direction: Optional[str]
    
    competitor_id: Optional[UUID]
    competitor_margin_percent: Optional[Decimal]
    
    time_days: Optional[str]
    time_start: Optional[str]
    time_end: Optional[str]
    
    volume_threshold: Optional[int]
    volume_window_hours: Optional[int]
    
    viral_threshold_reach: Optional[int]
    viral_threshold_engagement: Optional[int]
    viral_sentiment_min: Optional[Decimal]
    
    action: RuleAction
    action_value: Decimal
    
    min_price: Optional[Decimal]
    max_price: Optional[Decimal]
    max_change_percent: Decimal
    cooldown_hours: int
    last_triggered_at: Optional[datetime]
    
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# PRICE RECOMMENDATION SCHEMAS
# ═══════════════════════════════════════════════════════════════

class PriceRecommendationResponse(BaseModel):
    id: UUID
    user_id: UUID
    product_id: UUID
    triggered_rule_id: Optional[UUID]
    
    current_price: Decimal
    recommended_price: Decimal
    change_percent: Decimal
    
    confidence_score: Decimal
    reasoning: str
    factors: dict
    
    status: RecommendationStatus
    requires_approval: bool
    valid_until: datetime
    
    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]
    rejection_reason: Optional[str]
    
    applied_at: Optional[datetime]
    applied_to_platform: Optional[str]
    
    created_at: datetime

    class Config:
        from_attributes = True


class RecommendationApprove(BaseModel):
    """Approve a pending recommendation."""
    pass


class RecommendationReject(BaseModel):
    """Reject a pending recommendation."""
    reason: Optional[str] = Field(default=None, max_length=500)


class RecommendationListParams(BaseModel):
    """Query params for listing recommendations."""
    status: Optional[RecommendationStatus] = None
    product_id: Optional[UUID] = None
    limit: int = Field(default=20, le=100)
    offset: int = 0


# ═══════════════════════════════════════════════════════════════
# PRICING SETTINGS SCHEMAS
# ═══════════════════════════════════════════════════════════════

class PricingSettingsUpdate(BaseModel):
    auto_approve_enabled: Optional[bool] = None
    auto_approve_max_increase: Optional[Decimal] = None
    auto_approve_max_decrease: Optional[Decimal] = None
    auto_approve_min_confidence: Optional[Decimal] = None
    min_margin_percent: Optional[Decimal] = None
    
    max_auto_changes_per_day: Optional[int] = None
    global_cooldown_hours: Optional[int] = None
    
    blackout_hours_start: Optional[int] = None
    blackout_hours_end: Optional[int] = None
    
    require_approval_above_price: Optional[Decimal] = None
    recommendation_valid_hours: Optional[int] = None
    
    notify_on_auto_apply: Optional[bool] = None
    notify_on_pending: Optional[bool] = None
    notification_email: Optional[str] = None
    notification_slack_webhook: Optional[str] = None


class PricingSettingsResponse(BaseModel):
    id: UUID
    user_id: UUID
    
    auto_approve_enabled: bool
    auto_approve_max_increase: Decimal
    auto_approve_max_decrease: Decimal
    auto_approve_min_confidence: Decimal
    min_margin_percent: Decimal
    
    max_auto_changes_per_day: int
    global_cooldown_hours: int
    
    blackout_hours_start: Optional[int]
    blackout_hours_end: Optional[int]
    
    require_approval_above_price: Optional[Decimal]
    recommendation_valid_hours: int
    
    notify_on_auto_apply: bool
    notify_on_pending: bool
    notification_email: Optional[str]
    notification_slack_webhook: Optional[str]
    
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════
# RULE TEST SCHEMAS
# ═══════════════════════════════════════════════════════════════

class MockSignals(BaseModel):
    """Optional mock signals for rule testing."""
    sentiment_score: Optional[Decimal] = None
    sentiment_change_24h: Optional[Decimal] = None
    mention_count_24h: Optional[int] = None
    mention_baseline: Optional[int] = None
    viral_detected: Optional[bool] = None
    viral_reach: Optional[int] = None
    viral_engagement: Optional[int] = None
    viral_sentiment: Optional[Decimal] = None
    competitor_prices: Optional[dict[str, Decimal]] = None


class RuleTestRequest(BaseModel):
    """Request body for testing a rule."""
    mock_signals: Optional[MockSignals] = None


class RuleTestResponse(BaseModel):
    """Response from testing a rule."""
    rule_id: UUID
    rule_name: str
    would_trigger: bool
    match_details: Optional[dict] = None
    signals_used: dict
    calculated_price: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    reason: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# PRICING SIMULATION SCHEMAS
# ═══════════════════════════════════════════════════════════════

class SimulationRequest(BaseModel):
    """Request body for price simulation."""
    product_id: UUID
    mock_signals: Optional[MockSignals] = None


class SimulationResponse(BaseModel):
    """Response from pricing simulation."""
    product_id: UUID
    product_name: str
    current_price: Decimal
    rules_evaluated: int
    rules_triggered: int
    triggered_rules: list[RuleTestResponse]
    best_recommendation: Optional[dict] = None


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
    id: UUID
    user_id: UUID
    recommendation_id: UUID
    product_id: UUID
    rule_id: Optional[UUID]
    rule_type: Optional[str]
    
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
    revenue_change_percent: Optional[Decimal]
    units_change: int
    units_change_percent: Optional[Decimal]
    
    outcome_score: Decimal
    outcome_label: OutcomeLabel
    original_confidence: Decimal
    
    price_applied_at: datetime
    measurement_window_hours: int
    measured_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


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
    avg_revenue_change_percent: Optional[Decimal]
    
    total_revenue_impact: Decimal
    avg_confidence: Decimal
    confidence_accuracy_correlation: Optional[Decimal]


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
    avg_revenue_change_percent: Optional[Decimal]
    
    by_rule_type: dict
    top_performing_rules: list[dict]
    worst_performing_rules: list[dict]
    