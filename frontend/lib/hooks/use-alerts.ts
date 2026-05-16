'use client';

// Alert hooks
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alertsApi } from '@/lib/api';
import { toast } from '@/lib/hooks/use-toast';
import { alertKeys } from '@/lib/api/query-keys';
import type { 
  AlertFilterParams, 
  AlertType,
  AlertConfigurationCreate,
  AlertConfigurationUpdate,
} from '@/types';

// Re-export keys for backwards compatibility
export { alertKeys };

// Get paginated alerts
export function useAlerts(params?: AlertFilterParams) {
  return useQuery({
    queryKey: alertKeys.list(params as Record<string, unknown>),
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
    queryKey: [...alertKeys.all, 'unread-count'] as const,
    queryFn: () => alertsApi.getUnreadCount(),
    staleTime: 15 * 1000,
    refetchInterval: 60 * 1000,
  });
}

// Acknowledge an alert
export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => alertsApi.acknowledge(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: alertKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
      toast.success('Alert acknowledged');
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to acknowledge alert', message: error.message });
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
      queryClient.invalidateQueries({ queryKey: alertKeys.all });
      toast.success('Alert resolved');
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to resolve alert', message: error.message });
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
      toast.success('All alerts acknowledged');
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to acknowledge alerts', message: error.message });
    },
  });
}

// ============== Configuration Hooks ==============

// Get all configurations
export function useAlertConfigurations(params?: { alert_type?: AlertType; is_active?: boolean }) {
  return useQuery({
    queryKey: [...alertKeys.configurations(), 'list', params] as const,
    queryFn: () => alertsApi.getConfigurations(params),
    staleTime: 60 * 1000,
  });
}

// Get single configuration
export function useAlertConfiguration(id: string | null) {
  return useQuery({
    queryKey: alertKeys.configurationDetail(id || ''),
    queryFn: () => alertsApi.getConfiguration(id!),
    enabled: !!id,
    staleTime: 60 * 1000,
  });
}

// Create configuration
export function useCreateAlertConfiguration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AlertConfigurationCreate) => alertsApi.createConfiguration(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.configurations() });
      toast.success({ title: 'Configuration created', message: 'Alert configuration has been created' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to create configuration', message: error.message });
    },
  });
}

// Update configuration
export function useUpdateAlertConfiguration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AlertConfigurationUpdate }) =>
      alertsApi.updateConfiguration(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: alertKeys.configurationDetail(id) });
      queryClient.invalidateQueries({ queryKey: alertKeys.configurations() });
      toast.success({ title: 'Configuration updated', message: 'Alert configuration has been updated' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to update configuration', message: error.message });
    },
  });
}

// Delete configuration
export function useDeleteAlertConfiguration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => alertsApi.deleteConfiguration(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.configurations() });
      toast.success({ title: 'Configuration deleted', message: 'Alert configuration has been deleted' });
    },
    onError: (error: Error) => {
      toast.error({ title: 'Failed to delete configuration', message: error.message });
    },
  });
}


