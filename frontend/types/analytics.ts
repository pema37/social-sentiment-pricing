// Analytics domain types
// AUTO-SYNCED with backend via openapi-typescript
// Last synced: 2026-01-08
// Source: components["schemas"]["DashboardOverview"], RecommendationStats, etc.

import type { SentimentDataPoint, SentimentTrendDirection } from './sentiment';
import type { ProductSummary } from './product';

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
  sentiment_trend: 'improving' | 'declining' | 'stable';  // Default: 'stable'
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
  by_rule_type: Record<string, unknown>;
  top_performing_rules: Record<string, unknown>[];
  worst_performing_rules: Record<string, unknown>[];
}

// Re-export ProductSummary for convenience
export type { ProductSummary };
