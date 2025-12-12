// Alerts API
import { api } from './client';
import type {
  Alert,
  AlertStats,
  PaginatedAlerts,
  AlertFilterParams,
  AlertConfiguration,
  AlertConfigurationCreate,
  AlertConfigurationUpdate,
  AlertType,
} from '@/types';

export const alertsApi = {
  // Get all alerts with filters
  getAll: (params?: AlertFilterParams) =>
    api.get<PaginatedAlerts>('/api/v1/alerts', params as Record<string, string | number | boolean | undefined>),

  // Get alert stats
  getStats: () =>
    api.get<AlertStats>('/api/v1/alerts/stats'),

  // Get unread count
  getUnreadCount: () =>
    api.get<{ unread_count: number }>('/api/v1/alerts/unread/count'),

  // Get single alert
  getById: (id: string) =>
    api.get<Alert>(`/api/v1/alerts/${id}`),

  // Acknowledge an alert
  acknowledge: (id: string) =>
    api.post<Alert>(`/api/v1/alerts/${id}/acknowledge`),

  // Resolve an alert
  resolve: (id: string) =>
    api.post<Alert>(`/api/v1/alerts/${id}/resolve`),

  // Acknowledge all matching alerts
  acknowledgeAll: (params?: { severity?: string; alert_type?: string }) =>
    api.post<{ acknowledged_count: number }>('/api/v1/alerts/acknowledge-all', params),

  // ============== Configuration Endpoints ==============

  // List all configurations
  getConfigurations: (params?: { alert_type?: AlertType; is_active?: boolean }) =>
    api.get<AlertConfiguration[]>('/api/v1/alerts/configurations', params as Record<string, string | number | boolean | undefined>),

  // Get single configuration
  getConfiguration: (id: string) =>
    api.get<AlertConfiguration>(`/api/v1/alerts/configurations/${id}`),

  // Create configuration
  createConfiguration: (data: AlertConfigurationCreate) =>
    api.post<AlertConfiguration>('/api/v1/alerts/configurations', data),

  // Update configuration
  updateConfiguration: (id: string, data: AlertConfigurationUpdate) =>
    api.patch<AlertConfiguration>(`/api/v1/alerts/configurations/${id}`, data),

  // Delete configuration
  deleteConfiguration: (id: string) =>
    api.delete<void>(`/api/v1/alerts/configurations/${id}`),
};
