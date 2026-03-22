// frontend/lib/api/integrations.ts

/**
 * Integrations API Client
 * 
 * Functions for e-commerce platform integration endpoints.
 */

import { api } from './client';
import type {
  Integration,
  IntegrationListResponse,
  IntegrationUpdate,
  OAuthInitRequest,
  OAuthInitResponse,
  WooCommerceConnectRequest,
  SyncTriggerRequest,
  SyncStatusResponse,
  SyncLogsResponse,
  ProductLink,
  ProductLinkCreate,
  ProductLinkListResponse,
  PricePushRequest,
  PricePushResponse,
  BulkPricePushRequest,
  BulkPricePushResponse,
  IntegrationHealthResponse,
  SyncType,
} from '@/types/integration';

const BASE = '/api/v1/integrations';

// ==================== OAuth / Connection ====================

/**
 * Start OAuth flow for Shopify
 * Returns URL to redirect user to for authorization
 */
export async function initOAuth(data: OAuthInitRequest): Promise<OAuthInitResponse> {
  return api.post<OAuthInitResponse>(`${BASE}/oauth/init`, data);
}

/**
 * Connect WooCommerce store with API keys
 */
export async function connectWooCommerce(data: WooCommerceConnectRequest): Promise<Integration> {
  return api.post<Integration>(`${BASE}/woocommerce/connect`, data);
}

// ==================== Integration CRUD ====================

/**
 * List all integrations for current user
 */
export async function getIntegrations(): Promise<IntegrationListResponse> {
  return api.get<IntegrationListResponse>(`${BASE}/`);
}

/**
 * Get a specific integration
 */
export async function getIntegration(id: string): Promise<Integration> {
  return api.get<Integration>(`${BASE}/${id}`);
}

/**
 * Update integration settings
 */
export async function updateIntegration(id: string, data: IntegrationUpdate): Promise<Integration> {
  return api.patch<Integration>(`${BASE}/${id}`, data);
}

/**
 * Disconnect an integration (soft delete)
 */
export async function disconnectIntegration(id: string): Promise<void> {
  return api.delete<void>(`${BASE}/${id}`);
}

// ==================== Sync Operations ====================

/**
 * Trigger a product sync from the e-commerce platform
 */
export async function triggerSync(
  integrationId: string,
  syncType: SyncType = 'full'
): Promise<SyncStatusResponse> {
  const data: SyncTriggerRequest = { sync_type: syncType };
  return api.post<SyncStatusResponse>(`${BASE}/${integrationId}/sync`, data);
}

/**
 * Get current sync status
 */
export async function getSyncStatus(integrationId: string): Promise<SyncStatusResponse> {
  return api.get<SyncStatusResponse>(`${BASE}/${integrationId}/sync/status`);
}

/**
 * Recover an integration stuck in 'syncing' status.
 * Called when frontend polling times out.
 */
export async function recoverStuckSync(integrationId: string): Promise<{
  recovered: boolean;
  message: string;
  sync_status: string;
}> {
  return api.post(`${BASE}/${integrationId}/sync/recover`);
}

/**
 * Get sync history logs
 */
export async function getSyncLogs(
  integrationId: string,
  page = 1,
  pageSize = 10
): Promise<SyncLogsResponse> {
  return api.get<SyncLogsResponse>(`${BASE}/${integrationId}/sync/logs`, {
    page,
    page_size: pageSize,
  });
}

// ==================== Product Links ====================

/**
 * Link an SSP product to an external platform product
 */
export async function createProductLink(
  integrationId: string,
  data: ProductLinkCreate
): Promise<ProductLink> {
  return api.post<ProductLink>(`${BASE}/${integrationId}/links`, data);
}

/**
 * List all product links for an integration
 */
export async function getProductLinks(integrationId: string): Promise<ProductLinkListResponse> {
  return api.get<ProductLinkListResponse>(`${BASE}/${integrationId}/links`);
}

/**
 * Remove a product link
 */
export async function deleteProductLink(integrationId: string, linkId: string): Promise<void> {
  return api.delete<void>(`${BASE}/${integrationId}/links/${linkId}`);
}

// ==================== Price Push ====================

/**
 * Push a price update to the e-commerce platform
 */
export async function pushPrice(
  integrationId: string,
  data: PricePushRequest
): Promise<PricePushResponse> {
  return api.post<PricePushResponse>(`${BASE}/${integrationId}/push-price`, data);
}

/**
 * Push multiple price updates
 */
export async function pushPricesBulk(
  integrationId: string,
  data: BulkPricePushRequest
): Promise<BulkPricePushResponse> {
  return api.post<BulkPricePushResponse>(`${BASE}/${integrationId}/push-price/bulk`, data);
}

// ==================== Health Check ====================

/**
 * Check if an integration connection is healthy
 */
export async function checkHealth(integrationId: string): Promise<IntegrationHealthResponse> {
  return api.get<IntegrationHealthResponse>(`${BASE}/${integrationId}/health`);
}

// ==================== Convenience Helpers ====================

/**
 * Poll sync status until complete or error
 */
export async function pollSyncStatus(
  integrationId: string,
  onProgress?: (status: SyncStatusResponse) => void,
  intervalMs = 2000,
  maxAttempts = 60
): Promise<SyncStatusResponse> {
  let attempts = 0;
  
  return new Promise((resolve, reject) => {
    const poll = async () => {
      try {
        const status = await getSyncStatus(integrationId);
        onProgress?.(status);
        
        if (status.sync_status === 'idle' || status.sync_status === 'error') {
          resolve(status);
          return;
        }
        
        attempts++;
        if (attempts >= maxAttempts) {
          reject(new Error('Sync polling timeout'));
          return;
        }
        
        setTimeout(poll, intervalMs);
      } catch (error) {
        reject(error);
      }
    };
    
    poll();
  });
}

// Add to frontend/lib/api/integrations.ts

// ==================== Sync Progress (NEW) ====================

export interface SyncProgress {
  integration_id: string;
  platform: string;
  store_name: string | null;
  sync_status: 'idle' | 'syncing' | 'error';
  is_syncing: boolean;
  products_processed: number;
  products_total: number | null;
  progress_percent: number | null;
  current_phase: 'idle' | 'fetching' | 'processing' | 'finalizing';
  started_at: string | null;
  elapsed_seconds: number | null;
  last_sync_at: string | null;
  products_synced: number;
  products_created: number;
  products_updated: number;
  products_deleted: number;
  error_message: string | null;
  status_message: string;
  can_refresh_safely: boolean;
}

export interface AllSyncStatus {
  integrations: Array<{
    integration_id: string;
    platform: string;
    store_name: string | null;
    sync_status: string;
    is_syncing: boolean;
    products_synced: number;
    last_sync_at: string | null;
    status: string;
  }>;
  any_syncing: boolean;
  total_integrations: number;
  message: string;
}

/**
 * Get detailed sync progress with user-friendly messaging
 */
export async function getSyncProgress(integrationId: string): Promise<SyncProgress> {
  return api.get<SyncProgress>(`${BASE}/${integrationId}/sync/progress`);
}

/**
 * Get sync status for all integrations
 */
export async function getAllSyncStatus(): Promise<AllSyncStatus> {
  return api.get<AllSyncStatus>(`${BASE}/sync/status/all`);
}


