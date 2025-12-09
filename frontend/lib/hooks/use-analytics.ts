// lib/hooks/use-analytics.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { analyticsApi, alertsApi } from '@/lib/api/client';
import type { DashboardOverview, ProductSummary, Alert, AlertStats, SentimentTrend } from '@/lib/api/client';

// Query keys for cache management
export const queryKeys = {
  dashboard: ['dashboard'] as const,
  productSummaries: (limit: number) => ['product-summaries', limit] as const,
  recommendationStats: (days: number) => ['recommendation-stats', days] as const,
  alertAnalytics: (days: number) => ['alert-analytics', days] as const,
  sentimentTrend: (params?: { product_id?: string; days?: number; bucket?: string }) => 
    ['sentiment-trend', params] as const,
  alerts: (params?: Record<string, unknown>) => ['alerts', params] as const,
  alertStats: ['alert-stats'] as const,
  unreadCount: ['unread-count'] as const,
};

// ============================================
// Dashboard Hooks
// ============================================

// Main dashboard overview stats
export function useDashboardOverview() {
  return useQuery({
    queryKey: queryKeys.dashboard,
    queryFn: async (): Promise<DashboardOverview> => {
      const response = await analyticsApi.getDashboard();
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 60 * 1000, // Consider fresh for 1 minute
  });
}

// Product summaries for dashboard cards
export function useProductSummaries(limit: number = 10) {
  return useQuery({
    queryKey: queryKeys.productSummaries(limit),
    queryFn: async (): Promise<ProductSummary[]> => {
      const response = await analyticsApi.getProductSummaries(limit);
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 60 * 1000,
  });
}

// Recommendation statistics
export function useRecommendationStats(days: number = 30) {
  return useQuery({
    queryKey: queryKeys.recommendationStats(days),
    queryFn: async () => {
      const response = await analyticsApi.getRecommendationStats(days);
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 5 * 60 * 1000, // Fresh for 5 minutes
  });
}

// Alert analytics (breakdown by type/severity)
export function useAlertAnalytics(days: number = 30) {
  return useQuery({
    queryKey: queryKeys.alertAnalytics(days),
    queryFn: async () => {
      const response = await analyticsApi.getAlertAnalytics(days);
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 60 * 1000,
  });
}

// Sentiment trend for charts
export function useSentimentTrend(params?: { 
  product_id?: string; 
  days?: number; 
  bucket?: string;
}) {
  return useQuery({
    queryKey: queryKeys.sentimentTrend(params),
    queryFn: async (): Promise<SentimentTrend> => {
      const response = await analyticsApi.getSentimentTrend(params);
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 60 * 1000, // Fresh for 1 minute
  });
}

// ============================================
// Alert Hooks
// ============================================

// Get paginated alerts
export function useAlerts(params?: { 
  skip?: number;
  limit?: number;
  status?: string;
  severity?: string;
  alert_type?: string;
  product_id?: string;
}) {
  return useQuery({
    queryKey: queryKeys.alerts(params),
    queryFn: async () => {
      const response = await alertsApi.getAll(params);
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 30 * 1000, // Fresh for 30 seconds
    refetchInterval: 30 * 1000, // Poll every 30 seconds
  });
}

// Alert stats (total unread, by severity, etc)
export function useAlertStats() {
  return useQuery({
    queryKey: queryKeys.alertStats,
    queryFn: async (): Promise<AlertStats> => {
      const response = await alertsApi.getStats();
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    staleTime: 30 * 1000,
    refetchInterval: 30 * 1000,
  });
}

// Lightweight unread count for header badge
export function useUnreadAlertCount() {
  return useQuery({
    queryKey: queryKeys.unreadCount,
    queryFn: async () => {
      const response = await alertsApi.getUnreadCount();
      if (response.error) throw new Error(response.error);
      return response.data!.unread_count;
    },
    staleTime: 15 * 1000,
    refetchInterval: 15 * 1000, // Poll more frequently for badge
  });
}

// ============================================
// Alert Mutations
// ============================================

// Acknowledge single alert
export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (alertId: string): Promise<Alert> => {
      const response = await alertsApi.acknowledge(alertId);
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      // Invalidate all alert-related queries
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.alertStats });
      queryClient.invalidateQueries({ queryKey: queryKeys.unreadCount });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

// Resolve single alert
export function useResolveAlert() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (alertId: string): Promise<Alert> => {
      const response = await alertsApi.resolve(alertId);
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.alertStats });
      queryClient.invalidateQueries({ queryKey: queryKeys.unreadCount });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

// Acknowledge all alerts
export function useAcknowledgeAllAlerts() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (params?: { severity?: string; alert_type?: string }) => {
      const response = await alertsApi.acknowledgeAll(params);
      if (response.error) throw new Error(response.error);
      return response.data!;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: queryKeys.alertStats });
      queryClient.invalidateQueries({ queryKey: queryKeys.unreadCount });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    },
  });
}

// ============================================
// Utility Hooks
// ============================================

// Helper to manually refresh all dashboard data
export function useRefreshDashboard() {
  const queryClient = useQueryClient();
  
  return () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.dashboard });
    queryClient.invalidateQueries({ queryKey: ['product-summaries'] });
    queryClient.invalidateQueries({ queryKey: ['alerts'] });
    queryClient.invalidateQueries({ queryKey: queryKeys.alertStats });
    queryClient.invalidateQueries({ queryKey: queryKeys.unreadCount });
  };
}
