// Analytics hooks
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { analyticsApi } from '@/lib/api';

// Query keys
export const analyticsKeys = {
  all: ['analytics'] as const,
  dashboard: () => [...analyticsKeys.all, 'dashboard'] as const,
  productSummaries: (limit?: number) => [...analyticsKeys.all, 'product-summaries', limit] as const,
  recommendationStats: (days?: number) => [...analyticsKeys.all, 'recommendation-stats', days] as const,
  alertAnalytics: (days?: number) => [...analyticsKeys.all, 'alert-analytics', days] as const,
  sentimentTrend: (params?: { product_id?: string; days?: number; bucket?: string }) =>
    [...analyticsKeys.all, 'sentiment-trend', params] as const,
};

// Dashboard overview
export function useDashboardOverview() {
  return useQuery({
    queryKey: analyticsKeys.dashboard(),
    queryFn: () => analyticsApi.getDashboard(),
    staleTime: 30 * 1000,
    refetchOnMount: true,
  });
}

// Product summaries for dashboard
export function useProductSummaries(limit: number = 10) {
  return useQuery({
    queryKey: analyticsKeys.productSummaries(limit),
    queryFn: () => analyticsApi.getProductSummaries(limit),
    staleTime: 30 * 1000,
    refetchOnMount: true,
  });
}

// Recommendation stats
export function useRecommendationStats(days: number = 30) {
  return useQuery({
    queryKey: analyticsKeys.recommendationStats(days),
    queryFn: () => analyticsApi.getRecommendationStats(days),
    staleTime: 60 * 1000,
    refetchOnMount: true,
  });
}

// Alert analytics
export function useAlertAnalytics(days: number = 30) {
  return useQuery({
    queryKey: analyticsKeys.alertAnalytics(days),
    queryFn: () => analyticsApi.getAlertAnalytics(days),
    staleTime: 60 * 1000,
    refetchOnMount: true,
  });
}

// Sentiment trend
export function useSentimentTrend(params?: { product_id?: string; days?: number; bucket?: string }) {
  return useQuery({
    queryKey: analyticsKeys.sentimentTrend(params),
    queryFn: () => analyticsApi.getSentimentTrend(params),
    staleTime: 60 * 1000,
    refetchOnMount: true,
  });
}

// Refresh dashboard data
export function useRefreshDashboard() {
  const queryClient = useQueryClient();
  
  return {
    refresh: () => {
      queryClient.invalidateQueries({ queryKey: analyticsKeys.all });
    },
  };
}

