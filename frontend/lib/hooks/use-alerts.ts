// Alert hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alertsApi } from '@/lib/api';
import type { AlertFilterParams } from '@/types';

// Query keys
export const alertKeys = {
  all: ['alerts'] as const,
  list: (params?: AlertFilterParams) => [...alertKeys.all, 'list', params] as const,
  detail: (id: string) => [...alertKeys.all, 'detail', id] as const,
  stats: () => [...alertKeys.all, 'stats'] as const,
  unreadCount: () => [...alertKeys.all, 'unread-count'] as const,
};

// Get paginated alerts
export function useAlerts(params?: AlertFilterParams) {
  return useQuery({
    queryKey: alertKeys.list(params),
    queryFn: () => alertsApi.getAll(params),
    staleTime: 30 * 1000,
  });
}

// Get single alert
export function useAlert(id: string | null) {
  return useQuery({
    queryKey: alertKeys.detail(id || ''),
    queryFn: () => alertsApi.getById(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });
}

// Get alert stats
export function useAlertStats() {
  return useQuery({
    queryKey: alertKeys.stats(),
    queryFn: () => alertsApi.getStats(),
    staleTime: 30 * 1000,
  });
}

// Get unread count
export function useUnreadAlertCount() {
  return useQuery({
    queryKey: alertKeys.unreadCount(),
    queryFn: () => alertsApi.getUnreadCount(),
    staleTime: 15 * 1000, // Refresh more frequently
    refetchInterval: 60 * 1000, // Auto-refresh every minute
  });
}

// Acknowledge an alert
export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => alertsApi.acknowledge(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: alertKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: alertKeys.list() });
      queryClient.invalidateQueries({ queryKey: alertKeys.stats() });
      queryClient.invalidateQueries({ queryKey: alertKeys.unreadCount() });
    },
  });
}

// Resolve an alert
export function useResolveAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => alertsApi.resolve(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: alertKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: alertKeys.list() });
      queryClient.invalidateQueries({ queryKey: alertKeys.stats() });
      queryClient.invalidateQueries({ queryKey: alertKeys.unreadCount() });
    },
  });
}

// Acknowledge all alerts
export function useAcknowledgeAllAlerts() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params?: { severity?: string; alert_type?: string }) =>
      alertsApi.acknowledgeAll(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
    },
  });
}
