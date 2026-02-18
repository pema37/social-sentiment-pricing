// ============================================
// OUTCOMES API + TRANSFORMERS
//
// API functions call backend endpoints.
// Transformers convert raw responses → UI-ready shapes.
//
// Place at: frontend/lib/api/outcomes.ts
// ============================================

import { api } from './client';
import type {
  RecommendationOutcome,
  OutcomeListParams,
  ConfidenceCalibration,
  MerchantModificationPattern,
  CategoryBenchmark,
  DataGapFailureRate,
  ElasticityAccuracy,
  AccuracyStats,
  OutcomeCardData,
  OutcomeWindowData,
} from '@/types/outcome';

// ── API Functions ──

export const outcomesApi = {
  /** List outcomes for the current user with filters. */
  list(params: OutcomeListParams = {}): Promise<RecommendationOutcome[]> {
    const searchParams = new URLSearchParams();
    if (params.product_id) searchParams.set('product_id', params.product_id);
    if (params.rule_id) searchParams.set('rule_id', params.rule_id);
    if (params.outcome_label) searchParams.set('outcome_label', params.outcome_label);
    if (params.days) searchParams.set('days', String(params.days));
    if (params.limit) searchParams.set('limit', String(params.limit));
    if (params.offset) searchParams.set('offset', String(params.offset));

    const qs = searchParams.toString();
    return api.get<RecommendationOutcome[]>(`/api/v1/outcomes${qs ? `?${qs}` : ''}`);
  },

  /** Get a single outcome by ID. */
  get(outcomeId: string): Promise<RecommendationOutcome> {
    return api.get<RecommendationOutcome>(`/api/v1/outcomes/${outcomeId}`);
  },

  /** Get overall accuracy stats for the current user. */
  accuracyStats(days = 30): Promise<AccuracyStats> {
    return api.get<AccuracyStats>(`/api/v1/outcomes/accuracy?days=${days}`);
  },

  /** Get confidence calibration (Pearson r target: > 0.7). */
  confidenceCalibration(params: {
    product_category?: string;
    days?: number;
  } = {}): Promise<ConfidenceCalibration> {
    const searchParams = new URLSearchParams();
    if (params.product_category) searchParams.set('product_category', params.product_category);
    if (params.days) searchParams.set('days', String(params.days));

    const qs = searchParams.toString();
    return api.get<ConfidenceCalibration>(
      `/api/v1/outcomes/calibration${qs ? `?${qs}` : ''}`
    );
  },

  /** Get merchant modification pattern (backward learning → Strategist). */
  merchantModificationPattern(params: {
    product_category?: string;
    days?: number;
  } = {}): Promise<MerchantModificationPattern> {
    const searchParams = new URLSearchParams();
    if (params.product_category) searchParams.set('product_category', params.product_category);
    if (params.days) searchParams.set('days', String(params.days));

    const qs = searchParams.toString();
    return api.get<MerchantModificationPattern>(
      `/api/v1/outcomes/merchant-patterns${qs ? `?${qs}` : ''}`
    );
  },

  /** Get category benchmarks (cross-merchant intelligence). */
  categoryBenchmarks(
    category: string,
    days = 90,
  ): Promise<CategoryBenchmark | null> {
    return api.get<CategoryBenchmark | null>(
      `/api/v1/outcomes/benchmarks/${encodeURIComponent(category)}?days=${days}`
    );
  },

  /** Get data gap failure rates (backward learning → Scout). */
  dataGapFailureRates(days = 90): Promise<DataGapFailureRate[]> {
    return api.get<DataGapFailureRate[]>(
      `/api/v1/outcomes/data-gaps?days=${days}`
    );
  },

  /** Get elasticity accuracy (backward learning → Analyst). */
  elasticityAccuracy(params: {
    product_category?: string;
    days?: number;
  } = {}): Promise<ElasticityAccuracy> {
    const searchParams = new URLSearchParams();
    if (params.product_category) searchParams.set('product_category', params.product_category);
    if (params.days) searchParams.set('days', String(params.days));

    const qs = searchParams.toString();
    return api.get<ElasticityAccuracy>(
      `/api/v1/outcomes/elasticity-accuracy${qs ? `?${qs}` : ''}`
    );
  },

  /** Get performance stats for a specific rule. */
  rulePerformance(ruleId: string, days = 90): Promise<Record<string, unknown>> {
    return api.get(`/api/v1/outcomes/rules/${ruleId}/performance?days=${days}`);
  },
};

// ── Transformers: Raw API → UI-ready shapes ──

/**
 * Transform a raw RecommendationOutcome into a card-ready data object.
 * Used by outcome list views and detail panels.
 */
export function transformOutcomeToCard(outcome: RecommendationOutcome): OutcomeCardData {
  const measurementWindows: OutcomeWindowData[] = [
    {
      window: '7d',
      revenue: outcome.revenue_7d_after ? parseFloat(outcome.revenue_7d_after) : null,
      units: outcome.units_7d_after,
      lift: outcome.revenue_lift_7d,
      measured: outcome.revenue_7d_after !== null,
    },
    {
      window: '14d',
      revenue: outcome.revenue_14d_after ? parseFloat(outcome.revenue_14d_after) : null,
      units: outcome.units_14d_after,
      lift: outcome.revenue_lift_14d,
      measured: outcome.revenue_14d_after !== null,
    },
    {
      window: '30d',
      revenue: outcome.revenue_30d_after ? parseFloat(outcome.revenue_30d_after) : null,
      units: outcome.units_30d_after,
      lift: outcome.revenue_lift_30d,
      measured: outcome.revenue_30d_after !== null,
    },
  ];

  return {
    id: outcome.id,
    productId: outcome.product_id,
    outcomeLabel: outcome.outcome_label,
    outcomeScore: parseFloat(outcome.outcome_score),
    priceChange: {
      from: parseFloat(outcome.price_before),
      to: parseFloat(outcome.price_after),
      percent: parseFloat(outcome.price_change_percent),
    },
    confidence: parseFloat(outcome.original_confidence),
    confidenceBreakdown: {
      elasticity: outcome.confidence_elasticity,
      position: outcome.confidence_position,
      urgency: outcome.confidence_urgency,
      dataQuality: outcome.confidence_data_quality,
    },
    merchantDecision: outcome.merchant_decision,
    measurementWindows,
    measurementStatus: outcome.measurement_status,
    appliedAt: outcome.price_applied_at,
    hasEvidence:
      outcome.scout_evidence !== null ||
      outcome.analyst_evidence !== null ||
      outcome.strategist_evidence !== null,
  };
}

/**
 * Get the "best available" revenue lift from an outcome.
 * Prefers longest measured window.
 */
export function getBestLift(outcome: RecommendationOutcome): {
  lift: number | null;
  window: string;
} {
  if (outcome.revenue_lift_30d !== null) {
    return { lift: outcome.revenue_lift_30d, window: '30d' };
  }
  if (outcome.revenue_lift_14d !== null) {
    return { lift: outcome.revenue_lift_14d, window: '14d' };
  }
  if (outcome.revenue_lift_7d !== null) {
    return { lift: outcome.revenue_lift_7d, window: '7d' };
  }
  return { lift: null, window: 'none' };
}

/**
 * Compute a human-readable measurement progress label.
 */
export function getMeasurementProgress(status: RecommendationOutcome['measurement_status']): {
  label: string;
  percent: number;
  color: 'gray' | 'blue' | 'yellow' | 'green' | 'red';
} {
  switch (status) {
    case 'awaiting_decision':
      return { label: 'Awaiting decision', percent: 0, color: 'gray' };
    case 'decision_recorded':
      return { label: 'Measuring...', percent: 10, color: 'blue' };
    case 'single_measured':
      return { label: '48h measured', percent: 25, color: 'blue' };
    case 'measured_7d':
      return { label: '7-day measured', percent: 50, color: 'yellow' };
    case 'measured_14d':
      return { label: '14-day measured', percent: 75, color: 'yellow' };
    case 'measured_30d':
      return { label: 'Fully measured', percent: 100, color: 'green' };
    case 'measurement_failed':
      return { label: 'Measurement failed', percent: 0, color: 'red' };
    default:
      return { label: 'Unknown', percent: 0, color: 'gray' };
  }
}

/**
 * Format confidence decomposition for display.
 * Returns components sorted by contribution (weakest first for diagnostics).
 */
export function formatConfidenceBreakdown(outcome: RecommendationOutcome): {
  component: string;
  value: number;
  label: string;
  status: 'strong' | 'moderate' | 'weak';
}[] {
  const components = [
    { component: 'elasticity', value: outcome.confidence_elasticity, label: 'Elasticity' },
    { component: 'position', value: outcome.confidence_position, label: 'Market Position' },
    { component: 'urgency', value: outcome.confidence_urgency, label: 'Urgency' },
    { component: 'data_quality', value: outcome.confidence_data_quality, label: 'Data Quality' },
  ];

  return components
    .filter((c): c is { component: string; value: number; label: string } => c.value !== null)
    .map((c) => ({
      ...c,
      status: c.value >= 0.7 ? 'strong' as const : c.value >= 0.4 ? 'moderate' as const : 'weak' as const,
    }))
    .sort((a, b) => a.value - b.value); // Weakest first
}

/**
 * Extract the pipeline trace summary from evidence chain.
 * Used in the "Why this price?" detail panel.
 */
export function extractPipelineTrace(outcome: RecommendationOutcome): {
  scoutSummary: string | null;
  analystSummary: string | null;
  strategistSummary: string | null;
  totalPipelineMs: number | null;
} {
  const scout = outcome.scout_evidence;
  const analyst = outcome.analyst_evidence;
  const strategist = outcome.strategist_evidence;

  return {
    scoutSummary: scout
      ? `Found ${scout.competitor_count} competitors, data completeness ${Math.round(scout.data_completeness * 100)}%${scout.sentiment?.crisis_detected ? ' ⚠️ CRISIS DETECTED' : ''}`
      : null,
    analystSummary: analyst
      ? `${analyst.recommended_direction.toUpperCase()} recommended (urgency: ${analyst.urgency_level}). Elasticity: ${analyst.elasticity.point_estimate.toFixed(2)}`
      : null,
    strategistSummary: strategist
      ? `$${strategist.current_price} → $${strategist.recommended_price} (${strategist.change_percent}%)${strategist.was_clamped ? ' [guardrail clamped]' : ''}`
      : null,
    totalPipelineMs: strategist?.total_pipeline_time_ms ?? null,
  };
}

/**
 * Compute calibration status as a traffic-light indicator.
 */
export function getCalibrationIndicator(calibration: ConfidenceCalibration): {
  color: 'green' | 'yellow' | 'orange' | 'red' | 'gray';
  label: string;
  description: string;
} {
  if (calibration.calibration_status === 'insufficient_data') {
    return {
      color: 'gray',
      label: 'Not enough data',
      description: `Need at least 5 measured outcomes (have ${calibration.sample_size})`,
    };
  }

  const r = calibration.pearson_r;
  if (r === null) {
    return { color: 'gray', label: 'Error', description: 'Could not calculate correlation' };
  }

  if (r >= 0.7) {
    return { color: 'green', label: 'Well calibrated', description: `r = ${r.toFixed(3)} — confidence predicts outcomes reliably` };
  }
  if (r >= 0.4) {
    return { color: 'yellow', label: 'Moderately calibrated', description: `r = ${r.toFixed(3)} — improving, not yet reliable` };
  }
  if (r >= 0) {
    return { color: 'orange', label: 'Poorly calibrated', description: `r = ${r.toFixed(3)} — confidence scores need work` };
  }
  return { color: 'red', label: 'Inversely calibrated', description: `r = ${r.toFixed(3)} — high confidence correlates with bad outcomes` };
}

// Re-exported as named from module

