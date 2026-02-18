// ============================================
// OUTCOME TYPES (Intelligence Environment)
//
// Matches: backend/models/recommendation_outcome.py
// Consumed by: lib/api/outcomes.ts, lib/hooks/use-outcomes.ts
//
// Place at: frontend/types/outcome.ts
// Then re-export from: frontend/types/index.ts
// ============================================

// ── Enums ──

export type OutcomeLabel = 'positive' | 'negative' | 'neutral' | 'inconclusive';

export type MerchantDecision =
  | 'accepted'
  | 'modified'
  | 'rejected'
  | 'auto_applied'
  | 'expired'
  | 'pending';

export type MeasurementStatus =
  | 'awaiting_decision'
  | 'decision_recorded'
  | 'single_measured'
  | 'measured_7d'
  | 'measured_14d'
  | 'measured_30d'
  | 'measurement_failed';

export type RecommendationSource =
  | 'full_pipeline'
  | 'rule_based'
  | 'manual'
  | 'sentiment_triggered'
  | 'crisis_override';

// ── Core Outcome ──

export interface RecommendationOutcome {
  id: string;
  user_id: string;
  recommendation_id: string;
  product_id: string;
  rule_id: string | null;
  rule_type: string | null;
  recommendation_source: RecommendationSource;

  // Price data
  price_before: string;
  price_after: string;
  price_change_percent: string;

  // Original single-window metrics
  sales_count_before: number;
  units_sold_before: number;
  revenue_before: string;
  avg_daily_sales_before: string;
  sales_count_after: number;
  units_sold_after: number;
  revenue_after: string;
  avg_daily_sales_after: string;

  revenue_change: string;
  revenue_change_percent: string | null;
  units_change: number;
  units_change_percent: string | null;

  // Outcome scoring
  outcome_score: string;
  outcome_label: OutcomeLabel;

  // Confidence: overall + decomposition
  original_confidence: string;
  confidence_elasticity: number | null;
  confidence_position: number | null;
  confidence_urgency: number | null;
  confidence_data_quality: number | null;

  // Analyst scoring snapshot
  elasticity_estimate: number | null;
  urgency_score: number | null;
  sentiment_score: number | null;
  competitive_position_index: number | null;
  competitor_count: number | null;
  data_completeness: number | null;

  // Merchant decision tracking
  merchant_decision: MerchantDecision;
  actual_price_set: string | null;
  merchant_modification_percent: number | null;
  decided_at: string | null;

  // Multi-window revenue measurement
  revenue_7d_after: string | null;
  revenue_14d_after: string | null;
  revenue_30d_after: string | null;
  units_7d_after: number | null;
  units_14d_after: number | null;
  units_30d_after: number | null;
  revenue_lift_7d: number | null;
  revenue_lift_14d: number | null;
  revenue_lift_30d: number | null;

  // Margin tracking
  margin_before: string | null;
  margin_7d_after: string | null;
  margin_30d_after: string | null;
  margin_delta: number | null;

  // Agent evidence chain (JSONB)
  scout_evidence: ScoutEvidence | null;
  analyst_evidence: AnalystEvidence | null;
  strategist_evidence: StrategistEvidence | null;

  // Cross-merchant
  product_category: string | null;
  store_platform: string | null;

  // Measurement state
  measurement_status: MeasurementStatus;

  // Timestamps
  price_applied_at: string;
  measurement_window_hours: number;
  measured_at: string;
  created_at: string;
}

// ── Agent Evidence Types (mirrors Pydantic contracts) ──

export interface CompetitorPriceEvidence {
  competitor_name: string;
  price: string;
  currency: string;
  url: string | null;
  scraped_at: string;
  is_on_sale: boolean;
  sale_price: string | null;
}

export interface SentimentSnapshotEvidence {
  overall_score: number;
  mention_count: number;
  positive_ratio: number;
  negative_ratio: number;
  neutral_ratio: number;
  trending_topics: string[];
  crisis_detected: boolean;
  crisis_severity: number | null;
  source_breakdown: Record<string, number>;
}

export interface ScoutEvidence {
  product_id: string;
  scouted_at: string;
  competitors: CompetitorPriceEvidence[];
  competitor_count: number;
  our_price: string;
  our_position: string | null;
  competitive_position_index: number | null;
  sentiment: SentimentSnapshotEvidence | null;
  data_completeness: number;
  data_sources: string[];
  data_gaps: string[];
  scout_version: string;
  processing_time_ms: number | null;
}

export interface ElasticityEstimateEvidence {
  point_estimate: number;
  confidence_interval_low: number | null;
  confidence_interval_high: number | null;
  method: string;
  prior_source: string | null;
  sample_size: number | null;
}

export interface ConfidenceDecompositionEvidence {
  elasticity: number;
  position: number;
  urgency: number;
  data_quality: number;
}

export interface AnalystEvidence {
  product_id: string;
  scout_scouted_at: string;
  analyzed_at: string;
  elasticity: ElasticityEstimateEvidence;
  confidence: ConfidenceDecompositionEvidence;
  urgency_level: string;
  urgency_score: number;
  urgency_reasons: string[];
  sentiment_score: number | null;
  sentiment_impact: string | null;
  competitive_position_index: number;
  market_pressure: string | null;
  recommended_direction: 'increase' | 'decrease' | 'hold';
  direction_reasoning: string;
  data_completeness: number;
  competitor_count: number;
  analyst_version: string;
  processing_time_ms: number | null;
  model_used: string;
}

export interface GuardrailCheckEvidence {
  name: string;
  passed: boolean;
  original_value: string | null;
  clamped_value: string | null;
  reason: string | null;
}

export interface StrategistEvidence {
  product_id: string;
  scout_scouted_at: string;
  analyst_analyzed_at: string;
  strategized_at: string;
  current_price: string;
  recommended_price: string;
  change_percent: string;
  change_direction: 'increase' | 'decrease' | 'hold';
  compare_at_price: string | null;
  confidence_score: number;
  confidence_decomposition: ConfidenceDecompositionEvidence;
  reasoning: string;
  factors: Record<string, unknown>;
  guardrails_applied: GuardrailCheckEvidence[];
  was_clamped: boolean;
  raw_recommended_price: string | null;
  preference_prior_applied: number | null;
  pre_calibration_change_percent: string | null;
  category_benchmark_used: boolean;
  category_optimal_range: { min: number; max: number; median: number } | null;
  pipeline_source: string;
  strategist_version: string;
  processing_time_ms: number | null;
  total_pipeline_time_ms: number | null;
  model_used: string;
}

// ── API Response Types ──

export interface OutcomeListParams {
  product_id?: string;
  rule_id?: string;
  outcome_label?: OutcomeLabel;
  days?: number;
  limit?: number;
  offset?: number;
}

export interface ConfidenceCalibration {
  sample_size: number;
  pearson_r: number | null;
  calibration_status: 'insufficient_data' | 'well_calibrated' | 'moderately_calibrated' | 'poorly_calibrated' | 'inversely_calibrated' | 'calculation_error';
  component_calibration: Record<string, number | null>;
  avg_confidence: number;
  avg_lift: number;
  message?: string;
}

export interface MerchantModificationPattern {
  total_decisions: number;
  acceptance_rate: number | null;
  modification_rate: number | null;
  rejection_rate: number | null;
  avg_modification_percent: number | null;
  preference_prior: number | null;
}

export interface CategoryBenchmark {
  category: string;
  merchant_count: number;
  total_outcomes: number;
  success_rate: number;
  avg_revenue_lift_7d: number | null;
  avg_confidence: number;
  optimal_price_change_range: { min: number; max: number; median: number } | null;
  period_days: number;
}

export interface DataGapFailureRate {
  category: string;
  failure_rate_from_data_gaps: number;
  low_data_outcomes: number;
  total_outcomes: number;
}

export interface ElasticityAccuracy {
  sample_size: number;
  avg_predicted_elasticity: number | null;
  avg_observed_elasticity: number | null;
  prediction_bias: number | null;
  bias_direction: 'overestimates' | 'underestimates' | 'accurate';
  message?: string;
}

export interface AccuracyStats {
  period_days: number;
  total_outcomes: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  inconclusive_count: number;
  overall_success_rate: string;
  avg_outcome_score: string;
  total_revenue_impact: string;
  avg_revenue_change_percent: string | null;
  by_rule_type: Record<string, {
    count: number;
    positive: number;
    success_rate: number;
    revenue_impact: number;
  }>;
  top_performing_rules: RulePerformanceSummary[];
  worst_performing_rules: RulePerformanceSummary[];
}

export interface RulePerformanceSummary {
  rule_id: string;
  rule_name: string;
  rule_type: string;
  avg_score: number;
  outcome_count: number;
}

// ── Transformed types for UI components ──

export interface OutcomeWindowData {
  window: '7d' | '14d' | '30d';
  revenue: number | null;
  units: number | null;
  lift: number | null;
  measured: boolean;
}

export interface OutcomeCardData {
  id: string;
  productId: string;
  outcomeLabel: OutcomeLabel;
  outcomeScore: number;
  priceChange: { from: number; to: number; percent: number };
  confidence: number;
  confidenceBreakdown: {
    elasticity: number | null;
    position: number | null;
    urgency: number | null;
    dataQuality: number | null;
  };
  merchantDecision: MerchantDecision;
  measurementWindows: OutcomeWindowData[];
  measurementStatus: MeasurementStatus;
  appliedAt: string;
  hasEvidence: boolean;
}


