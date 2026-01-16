// frontend/lib/hooks/use-integrations.ts

/**
 * Integration Hooks
 * 
 * React Query hooks for e-commerce platform integrations.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as integrationsApi from '@/lib/api/integrations';
import { integrationKeys } from '@/lib/api/query-keys';
import type {
  IntegrationUpdate,
  OAuthInitRequest,
  WooCommerceConnectRequest,
  SyncType,
  SyncStatusResponse,
  ProductLinkCreate,
  PricePushRequest,
} from '@/types/integration';

// Re-export keys for backwards compatibility
export { integrationKeys };

// ==================== List & Detail ====================

/**
 * Get all integrations for current user
 */
export function useIntegrations() {
  return useQuery({
    queryKey: integrationKeys.lists(),
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
      queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
    },
  });
}

// ==================== Health Check ====================

/**
 * Check integration health
 */
export function useIntegrationHealth(id: string | null) {
  return useQuery({
    queryKey: [...integrationKeys.detail(id || ''), 'health'] as const,
    queryFn: () => integrationsApi.checkHealth(id!),
    enabled: !!id,
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
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
    refetchInterval: options?.polling 
      ? (query) => {
          const data = query.state.data as SyncStatusResponse | undefined;
          if (data?.sync_status === 'idle' || data?.sync_status === 'error') {
            queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
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
    queryKey: [...integrationKeys.detail(integrationId || ''), 'sync-logs', params] as const,
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
    queryKey: integrationKeys.linkedProducts(integrationId || ''),
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
      queryClient.invalidateQueries({ queryKey: integrationKeys.linkedProducts(variables.integrationId) });
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
      queryClient.invalidateQueries({ queryKey: integrationKeys.linkedProducts(variables.integrationId) });
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
      queryClient.invalidateQueries({ queryKey: integrationKeys.linkedProducts(variables.integrationId) });
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
      queryClient.invalidateQueries({ queryKey: integrationKeys.linkedProducts(variables.integrationId) });
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
    queryKey: [...integrationKeys.syncStatus(integrationId || ''), 'polling'] as const,
    queryFn: () => integrationsApi.getSyncStatus(integrationId!),
    enabled: !!integrationId,
    refetchInterval: (query) => {
      const data = query.state.data as SyncStatusResponse | undefined;
      if (data?.sync_status === 'idle' || data?.sync_status === 'error') {
        queryClient.invalidateQueries({ queryKey: integrationKeys.detail(integrationId!) });
        return false;
      }
      return 2000;
    },
  });
}


