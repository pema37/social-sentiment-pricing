// frontend/lib/hooks/use-integrations.ts

/**
 * Integration Hooks
 * 
 * React Query hooks for e-commerce platform integrations.
 * 
 * PATCHED (2026-01-28): Bug #6 fix - Added timeout protection to useSyncStatus
 * to prevent infinite polling when sync gets stuck. See SSP_AUDIT_REPORT.md.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useCallback, useState } from 'react';
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

// ========== NEW: Timeout configuration (Bug #6) ==========
/**
 * Maximum time to poll for sync status before giving up (5 minutes).
 * If sync takes longer than this, we stop polling and show an error.
 * 
 * The backend has a 15-minute timeout for stuck syncs, but we timeout
 * earlier on the frontend to give users feedback sooner.
 */
const SYNC_POLLING_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Polling interval for sync status
 */
const SYNC_POLLING_INTERVAL_MS = 2000; // 2 seconds
// ========== END NEW ==========

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

// ========== PATCHED: useSyncStatus with timeout protection (Bug #6) ==========
/**
 * Get current sync status with timeout protection
 * 
 * @param integrationId - The integration to check
 * @param options.polling - Whether to poll for updates (default: false)
 * @param options.onTimeout - Callback when polling times out
 * 
 * PATCHED (2026-01-28): Added timeout protection to prevent infinite spinner.
 * If sync status stays 'syncing' for more than 5 minutes, we stop polling
 * and call the onTimeout callback so the UI can show an error.
 */
export function useSyncStatus(
  integrationId: string | null, 
  options?: { 
    polling?: boolean;
    onTimeout?: () => void;
  }
) {
  const queryClient = useQueryClient();
  const pollingStartTime = useRef<number | null>(null);
  const hasTimedOut = useRef(false);
  
  // Reset timeout tracking when polling starts
  useEffect(() => {
    if (options?.polling && integrationId) {
      pollingStartTime.current = Date.now();
      hasTimedOut.current = false;
    } else {
      pollingStartTime.current = null;
    }
  }, [options?.polling, integrationId]);
  
  return useQuery({
    queryKey: integrationKeys.syncStatus(integrationId || ''),
    queryFn: () => integrationsApi.getSyncStatus(integrationId!),
    enabled: !!integrationId,
    staleTime: SYNC_POLLING_INTERVAL_MS * 3,
    refetchInterval: options?.polling 
      ? (query) => {
          const data = query.state.data as SyncStatusResponse | undefined;
          
          // If sync is complete (idle or error), stop polling
          if (data?.sync_status === 'idle' || data?.sync_status === 'error') {
            pollingStartTime.current = null;
            queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
            queryClient.invalidateQueries({ queryKey: integrationKeys.detail(integrationId!) });
            return false;
          }
          
          // ========== NEW: Timeout check ==========
          // If we've been polling for too long, stop and trigger recovery
          if (pollingStartTime.current && !hasTimedOut.current) {
            const elapsed = Date.now() - pollingStartTime.current;
            if (elapsed > SYNC_POLLING_TIMEOUT_MS) {
              hasTimedOut.current = true;
              pollingStartTime.current = null;

              // Trigger backend recovery for the stuck sync
              if (integrationId) {
                integrationsApi.recoverStuckSync(integrationId).catch((err) => {
                  console.error('[useSyncStatus] Failed to recover stuck sync:', err);
                });
              }

              // Call timeout callback if provided
              if (options?.onTimeout) {
                // Use setTimeout to avoid calling during render
                setTimeout(() => options.onTimeout?.(), 0);
              }

              console.warn(
                `[useSyncStatus] Polling timed out after ${SYNC_POLLING_TIMEOUT_MS / 1000}s ` +
                `for integration ${integrationId}. Triggered recovery.`
              );

              // Invalidate to pick up the recovered 'error' status
              queryClient.invalidateQueries({ queryKey: integrationKeys.syncStatus(integrationId!) });
              queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });

              return false; // Stop polling
            }
          }
          // ========== END NEW ==========
          
          return SYNC_POLLING_INTERVAL_MS;
        }
      : false,
  });
}
// ========== END PATCHED ==========

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

// ========== PATCHED: useSyncPolling with timeout protection (Bug #6) ==========
/**
 * Hook to poll sync status until complete or timeout
 * Use this after triggering a sync to track progress
 * 
 * PATCHED (2026-01-28): Added timeout protection. If polling exceeds 5 minutes,
 * returns isTimedOut: true so the UI can show an appropriate message.
 */
export function useSyncPolling(integrationId: string | null) {
  const queryClient = useQueryClient();
  
  // State includes integrationId to auto-reset when it changes
  // No useEffect needed - we compute derived values during render
  const [timeoutInfo, setTimeoutInfo] = useState<{
    forIntegrationId: string | null;
    isTimedOut: boolean;
  }>({ forIntegrationId: null, isTimedOut: false });
  
  // Ref for tracking start time (doesn't need re-render)
  const startTimeRef = useRef<{ id: string | null; time: number | null }>({ id: null, time: null });
  
  // Compute effective timeout - only valid if integrationId matches
  const isTimedOut = timeoutInfo.forIntegrationId === integrationId && timeoutInfo.isTimedOut;
  
  const query = useQuery({
    queryKey: integrationKeys.syncStatus(integrationId || ''),
    queryFn: () => integrationsApi.getSyncStatus(integrationId!),
    enabled: !!integrationId,
    refetchInterval: (query) => {
      const data = query.state.data as SyncStatusResponse | undefined;
      
      // If sync is complete, stop polling
      if (data?.sync_status === 'idle' || data?.sync_status === 'error') {
        startTimeRef.current = { id: null, time: null };
        queryClient.invalidateQueries({ queryKey: integrationKeys.detail(integrationId!) });
        return false;
      }
      
      // Initialize start time for this integrationId if not set
      if (startTimeRef.current.id !== integrationId) {
        startTimeRef.current = { id: integrationId, time: Date.now() };
      }
      
      // Check for timeout
      if (startTimeRef.current.time && !isTimedOut) {
        const elapsed = Date.now() - startTimeRef.current.time;
        if (elapsed > SYNC_POLLING_TIMEOUT_MS) {
          setTimeoutInfo({ forIntegrationId: integrationId, isTimedOut: true });
          startTimeRef.current = { id: null, time: null };
          console.warn(`[useSyncPolling] Timed out for integration ${integrationId}`);
          return false;
        }
      }
      
      return SYNC_POLLING_INTERVAL_MS;
    },
  });
  
  return {
    ...query,
    isTimedOut,
  };
}
// ========== END PATCHED ==========


// ========== NEW: Helper hook for handling sync with automatic timeout feedback ==========
/**
 * Combined hook for triggering sync and tracking its progress with timeout handling.
 * 
 * Usage:
 * ```tsx
 * const { triggerSync, syncStatus, isPolling, isTimedOut, error } = useSyncWithTimeout(integrationId);
 * 
 * // Trigger sync
 * triggerSync();
 * 
 * // Show UI based on state
 * if (isPolling) return <Spinner />;
 * if (isTimedOut) return <TimeoutError />;
 * if (error) return <Error message={error} />;
 * ```
 */
export function useSyncWithTimeout(integrationId: string | null) {
  const queryClient = useQueryClient();
  
  // State includes integrationId to auto-reset when it changes
  // No useEffect needed - we compute derived values during render
  const [syncState, setSyncState] = useState<{
    forIntegrationId: string | null;
    isPolling: boolean;
    isTimedOut: boolean;
  }>({ forIntegrationId: null, isPolling: false, isTimedOut: false });
  
  // Ref for start time (doesn't need re-render)
  const startTimeRef = useRef<number | null>(null);
  
  // Compute effective values - only valid if integrationId matches
  const isPolling = syncState.forIntegrationId === integrationId && syncState.isPolling;
  const isTimedOut = syncState.forIntegrationId === integrationId && syncState.isTimedOut;

  // Trigger sync mutation
  const triggerMutation = useTriggerSync();
  
  // Sync status query
  const statusQuery = useQuery({
    queryKey: integrationKeys.syncStatus(integrationId || ''),
    queryFn: () => integrationsApi.getSyncStatus(integrationId!),
    enabled: !!integrationId && isPolling,
    refetchInterval: (query) => {
      if (!isPolling) return false;
      
      const data = query.state.data as SyncStatusResponse | undefined;
      
      // Sync complete - stop polling
      if (data?.sync_status === 'idle' || data?.sync_status === 'error') {
        setSyncState(prev => ({ ...prev, isPolling: false }));
        startTimeRef.current = null;
        queryClient.invalidateQueries({ queryKey: integrationKeys.lists() });
        queryClient.invalidateQueries({ queryKey: integrationKeys.detail(integrationId!) });
        return false;
      }
      
      // Check timeout (Date.now in callback is fine)
      if (startTimeRef.current) {
        const elapsed = Date.now() - startTimeRef.current;
        if (elapsed > SYNC_POLLING_TIMEOUT_MS) {
          setSyncState(prev => ({ ...prev, isTimedOut: true, isPolling: false }));
          startTimeRef.current = null;
          return false;
        }
      }
      
      return SYNC_POLLING_INTERVAL_MS;
    },
  });

  const triggerSync = useCallback(async (syncType: SyncType = 'full') => {
    if (!integrationId) return;
    
    // Set state for this specific integrationId (Date.now in callback is fine)
    setSyncState({
      forIntegrationId: integrationId,
      isPolling: true,
      isTimedOut: false,
    });
    startTimeRef.current = Date.now();
    
    try {
      await triggerMutation.mutateAsync({ integrationId, syncType });
      // Query will automatically start polling due to isPolling state change
    } catch (error) {
      setSyncState(prev => ({ ...prev, isPolling: false }));
      startTimeRef.current = null;
      throw error;
    }
  }, [integrationId, triggerMutation]);

  // Get error from mutation or status response (handle both possible property names)
  const statusError = statusQuery.data && 'error_message' in statusQuery.data 
    ? (statusQuery.data as { error_message?: string }).error_message 
    : statusQuery.data && 'error' in statusQuery.data 
      ? (statusQuery.data as { error?: string }).error 
      : null;

  return {
    triggerSync,
    syncStatus: statusQuery.data,
    isLoading: triggerMutation.isPending,
    isPolling,
    isTimedOut,
    error: triggerMutation.error?.message || statusError || null,
    refetch: statusQuery.refetch,
  };
}
// ========== END NEW ==========


