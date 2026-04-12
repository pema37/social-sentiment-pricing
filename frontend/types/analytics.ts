// Analytics domain types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08
// Source: components["schemas"]["DashboardOverview"], RecommendationStats, etc.

import type { SentimentDataPoint, SentimentTrendDirection } from './sentiment';
import type { ProductSummary } from './product';

// AP-013/sprint-1: RulePerformanceSummary was defined here AND in outcome.ts,
// causing a duplicate export collision when both are re-exported from types/index.ts.
// Removed local definition — import from outcome.ts as the single source of truth.
// AccuracyStatsResponse uses RulePerformanceSummary, so we import it here for use below.
import type { RulePerformanceSummary } from './outcome';
export type { RulePerformanceSummary };

// ============================================
// DASHBOARD OVERVIEW
// ============================================

/**
 * Dashboard overview stats
 * Matches: components["schemas"]["DashboardOverview"]
 */
export interface DashboardOverview {
  total_products: number;
  products_with_auto_pricing: number;
  total_competitors: number;
  unread_alerts: number;
  alerts_today: number;
  pending_recommendations: number;
  applied_recommendations_7d: number;
  average_sentiment: number | null;
  sentiment_trend: 'improving' | 'declining' | 'stable';
  total_mentions_24h: number;
}

// ============================================
// RECOMMENDATION STATS
// ============================================

/**
 * Recommendation statistics
 * Matches: components["schemas"]["RecommendationStats"]
 */
export interface RecommendationStats {
  total_generated: number;
  total_applied: number;
  total_rejected: number;
  total_expired: number;
  total_pending: number;
  approval_rate: number;
  avg_confidence: number | null;
  avg_price_change_percent: number | null;
}

// ============================================
// ALERT ANALYTICS
// ============================================

/**
 * Alert analytics for dashboard
 * Matches: components["schemas"]["AlertAnalytics"]
 */
export interface AlertAnalytics {
  total_alerts_7d: number;
  by_type: Record<string, unknown>;
  by_severity: Record<string, unknown>;
  avg_resolution_time_hours: number | null;
  by_status?: Record<string, number>;
}

// ============================================
// SENTIMENT ANALYTICS
// ============================================

/**
 * Sentiment trend with analytics context
 */
export interface SentimentTrendAnalytics {
  product_id: string | null;
  period_days: number;
  current_score: number | null;
  previous_score: number | null;
  change: number | null;
  trend: SentimentTrendDirection;
  timeline: SentimentDataPoint[];
}

// ============================================
// ACCURACY STATS
// ============================================

/**
 * Per-rule-type accuracy breakdown
 */
export interface RuleTypeStats {
  count: number;
  positive: number;
  revenue_impact: number;
  success_rate: number;
}

/**
 * Accuracy statistics for recommendations
 * Matches: components["schemas"]["AccuracyStatsResponse"]
 */
export interface AccuracyStatsResponse {
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
  by_rule_type: Record<string, RuleTypeStats>;
  top_performing_rules: RulePerformanceSummary[];
  worst_performing_rules: RulePerformanceSummary[];
}

// Re-export ProductSummary for convenience
export type { ProductSummary };



