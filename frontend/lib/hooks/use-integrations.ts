// frontend/lib/hooks/use-integrations.ts

/**
 * Integration Hooks
 * 
 * React Query hooks for e-commerce platform integrations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as integrationsApi from '@/lib/api/integrations';
import type {
  IntegrationUpdate,
  OAuthInitRequest,
  WooCommerceConnectRequest,
  SyncType,
  SyncStatusResponse,
  ProductLinkCreate,
  PricePushRequest,
} from '@/types/integration';

// Query keys
export const integrationKeys = {
  all: ['integrations'] as const,
  list: () => [...integrationKeys.all, 'list'] as const,
  detail: (id: string) => [...integrationKeys.all, 'detail', id] as const,
  health: (id: string) => [...integrationKeys.all, 'health', id] as const,
  syncStatus: (id: string) => [...integrationKeys.all, 'sync-status', id] as const,
  syncLogs: (id: string, params?: { page?: number; pageSize?: number }) =>
    [...integrationKeys.all, 'sync-logs', id, params] as const,
  links: (id: string) => [...integrationKeys.all, 'links', id] as const,
};

// ==================== List & Detail ====================

/**
 * Get all integrations for current user
 */
export function useIntegrations() {
  return useQuery({
    queryKey: integrationKeys.list(),
    queryFn: () => integrationsApi.getIntegrations(),
    staleTime: 30 * 1000,
  });
}

/**
 * Get a specific integration
 */
export function useIntegration(id: string | null) {
  return useQuery({
    queryKey: integrationKeys.detail(id || ''),
    queryFn: () => integrationsApi.getIntegration(id!),
    enabled: !!id,
    staleTime: 30 * 1000,
  });
}

// ==================== Connection ====================

/**
 * Start Shopify OAuth flow
 */
export function useInitOAuth() {
  return useMutation({
    mutationFn: (data: OAuthInitRequest) => integrationsApi.initOAuth(data),
    onSuccess: (response) => {
      // Redirect user to authorization URL
      window.location.href = response.authorization_url;
    },
  });
}

/**
 * Connect WooCommerce store with API keys
 */
export function useConnectWooCommerce() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: WooCommerceConnectRequest) => integrationsApi.connectWooCommerce(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.all });
    },
  });
}

/**
 * Disconnect an integration
 */
export function useDisconnectIntegration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => integrationsApi.disconnectIntegration(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.all });
    },
  });
}

/**
 * Update integration settings
 */
export function useUpdateIntegration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: IntegrationUpdate }) =>
      integrationsApi.updateIntegration(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: integrationKeys.list() });
    },
  });
}

// ==================== Health Check ====================

/**
 * Check integration health
 */
export function useIntegrationHealth(id: string | null) {
  return useQuery({
    queryKey: integrationKeys.health(id || ''),
    queryFn: () => integrationsApi.checkHealth(id!),
    enabled: !!id,
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 5 * 60 * 1000, // Auto-refresh every 5 minutes
  });
}

// ==================== Sync Operations ====================

/**
 * Get current sync status
 */
export function useSyncStatus(integrationId: string | null, options?: { polling?: boolean }) {
  const queryClient = useQueryClient();
  
  return useQuery({
    queryKey: integrationKeys.syncStatus(integrationId || ''),
    queryFn: () => integrationsApi.getSyncStatus(integrationId!),
    enabled: !!integrationId,
    staleTime: 5 * 1000,
    // FIXED: Function-based interval that auto-stops and refreshes UI
    refetchInterval: options?.polling 
      ? (query) => {
          const data = query.state.data as SyncStatusResponse | undefined;
          if (data?.sync_status === 'idle' || data?.sync_status === 'error') {
            queryClient.invalidateQueries({ queryKey: integrationKeys.list() });
            queryClient.invalidateQueries({ queryKey: integrationKeys.detail(integrationId!) });
            return false;
          }
          return 2000;
        }
      : false,
  });
}

/**
 * Get sync history logs
 */
export function useSyncLogs(
  integrationId: string | null,
  params?: { page?: number; pageSize?: number }
) {
  return useQuery({
    queryKey: integrationKeys.syncLogs(integrationId || '', params),
    queryFn: () => integrationsApi.getSyncLogs(integrationId!, params?.page, params?.pageSize),
    enabled: !!integrationId,
    staleTime: 30 * 1000,
  });
}

/**
 * Trigger a product sync
 */
export function useTriggerSync() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ integrationId, syncType = 'full' }: { integrationId: string; syncType?: SyncType }) =>
      integrationsApi.triggerSync(integrationId, syncType),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.syncStatus(variables.integrationId) });
      queryClient.invalidateQueries({ queryKey: integrationKeys.detail(variables.integrationId) });
    },
  });
}

// ==================== Product Links ====================

/**
 * Get product links for an integration
 */
export function useProductLinks(integrationId: string | null) {
  return useQuery({
    queryKey: integrationKeys.links(integrationId || ''),
    queryFn: () => integrationsApi.getProductLinks(integrationId!),
    enabled: !!integrationId,
    staleTime: 30 * 1000,
  });
}

/**
 * Create a product link
 */
export function useCreateProductLink() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ integrationId, data }: { integrationId: string; data: ProductLinkCreate }) =>
      integrationsApi.createProductLink(integrationId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.links(variables.integrationId) });
    },
  });
}

/**
 * Delete a product link
 */
export function useDeleteProductLink() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ integrationId, linkId }: { integrationId: string; linkId: string }) =>
      integrationsApi.deleteProductLink(integrationId, linkId),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.links(variables.integrationId) });
    },
  });
}

// ==================== Price Push ====================

/**
 * Push a price update to the platform
 */
export function usePushPrice() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ integrationId, data }: { integrationId: string; data: PricePushRequest }) =>
      integrationsApi.pushPrice(integrationId, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.links(variables.integrationId) });
    },
  });
}

/**
 * Push multiple price updates
 */
export function usePushPricesBulk() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ integrationId, updates }: { integrationId: string; updates: PricePushRequest[] }) =>
      integrationsApi.pushPricesBulk(integrationId, { updates }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: integrationKeys.links(variables.integrationId) });
    },
  });
}

// ==================== Polling Helper Hook ====================

/**
 * Hook to poll sync status until complete
 * Use this after triggering a sync to track progress
 */
export function useSyncPolling(integrationId: string | null) {
  const queryClient = useQueryClient();
  
  return useQuery({
    queryKey: [...integrationKeys.syncStatus(integrationId || ''), 'polling'],
    queryFn: () => integrationsApi.getSyncStatus(integrationId!),
    enabled: !!integrationId,
    refetchInterval: (query) => {
      const data = query.state.data as SyncStatusResponse | undefined;
      // Stop polling when sync completes or errors
      if (data?.sync_status === 'idle' || data?.sync_status === 'error') {
        // Invalidate related queries when done
        queryClient.invalidateQueries({ queryKey: integrationKeys.detail(integrationId!) });
        queryClient.invalidateQueries({ queryKey: integrationKeys.syncLogs(integrationId!) });
        return false;
      }
      return 2000; // Poll every 2 seconds while syncing
    },
  });
}
