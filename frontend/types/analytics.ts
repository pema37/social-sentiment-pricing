// Analytics domain types

import type { SentimentDataPoint, SentimentTrendDirection } from './sentiment';
import type { ProductSummary } from './product';

// Dashboard overview stats
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

// Recommendation stats
export interface RecommendationStats {
  total_pending: number;
  total_approved: number;
  total_rejected: number;
  total_applied: number;
  total_expired: number;
  avg_confidence_score: number | null;
  avg_adjustment_percent: number | null;
}

// Alert analytics
export interface AlertAnalytics {
  total_alerts: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
}

// Sentiment trend (re-export with analytics context)
export interface SentimentTrendAnalytics {
  product_id: string | null;
  period_days: number;
  current_score: number | null;
  previous_score: number | null;
  change: number | null;
  trend: SentimentTrendDirection;
  timeline: SentimentDataPoint[];
}

// Re-export ProductSummary for convenience
export type { ProductSummary };
