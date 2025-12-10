// Analytics API
import { api } from './client';
import type {
  DashboardOverview,
  ProductSummary,
  RecommendationStats,
  AlertAnalytics,
  SentimentTrend,
} from '@/types';

export const analyticsApi = {
  // Dashboard overview
  getDashboard: () =>
    api.get<DashboardOverview>('/api/v1/analytics/dashboard'),

  // Product summaries for dashboard
  getProductSummaries: (limit: number = 10) =>
    api.get<ProductSummary[]>('/api/v1/analytics/products', { limit }),

  // Recommendation stats
  getRecommendationStats: (days: number = 30) =>
    api.get<RecommendationStats>('/api/v1/analytics/recommendations/stats', { days }),

  // Alert analytics
  getAlertAnalytics: (days: number = 30) =>
    api.get<AlertAnalytics>('/api/v1/analytics/alerts/stats', { days }),

  // Sentiment trend over time
  getSentimentTrend: (params?: { product_id?: string; days?: number; bucket?: string }) =>
    api.get<SentimentTrend>('/api/v1/analytics/sentiment-trend', params),
};
