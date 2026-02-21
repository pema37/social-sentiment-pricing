// frontend/lib/hooks/use-product-sync.ts
// Hooks for product synchronization with e-commerce stores

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { productKeys } from '@/lib/api/query-keys';

// ─────────────────────────────────────────────────────────────────────────────
// Types (snake_case - matches raw API response, no transformation in client)
// ─────────────────────────────────────────────────────────────────────────────

export interface SyncLink {
  link_id: string;
  integration_id: string;
  platform: string;
  store_url: string;
  external_product_id: string;
  external_variant_id?: string;
  sync_enabled: boolean;
  last_synced_at?: string;
  external_price?: number;
}

export interface AvailableIntegration {
  integration_id: string;
  platform: string;
  store_url: string;
}

export interface SyncStatus {
  product_id: string;
  product_name: string;
  has_links: boolean;
  links: SyncLink[];
  available_integrations: AvailableIntegration[];
}

export interface SyncResultItem {
  integration_id: string;
  platform: string;
  store_url: string;
  success: boolean;
  external_product_id?: string;
  link_id?: string;
  error?: string;
  error_code?: string;
}

export interface SyncResult {
  product_id: string;
  product_name: string;
  results?: SyncResultItem[];
  synced?: boolean;
  reason?: string;
}

export interface BulkSyncDetail {
  product_id: string;
  product_name: string;
  integration_id: string;
  platform: string;
  success: boolean;
  external_product_id?: string;
  error?: string;
}

export interface BulkSyncResult {
  total_products: number;
  total_integrations: number;
  pushed: number;
  failed: number;
  details: BulkSyncDetail[];
}

export interface LinkProductParams {
  productId: string;
  integrationId: string;
  externalProductId: string;
  externalVariantId?: string;
}

interface ApiErrorData {
  detail?: string;
  message?: string;
}

interface ApiError {
  response?: {
    data?: ApiErrorData;
  };
  message?: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Hooks
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Hook to get sync status for a product
 */
export function useProductSyncStatus(productId: string) {
  return useQuery({
    queryKey: productKeys.syncStatusDetail(productId),
    queryFn: async (): Promise<SyncStatus> => {
      return api.get<SyncStatus>(`/products/${productId}/sync-status`);
    },
    enabled: !!productId,
  });
}

/**
 * Hook to sync a product to e-commerce store(s)
 */
export function useSyncProduct() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ 
      productId, 
      integrationId 
    }: { 
      productId: string; 
      integrationId?: string;
    }): Promise<SyncResult> => {
      return api.post<SyncResult>(`/products/${productId}/sync`, {
        integration_id: integrationId || null
      });
    },
    onSuccess: (_, variables) => {
      // Invalidate sync status
      queryClient.invalidateQueries({ 
        queryKey: productKeys.syncStatusDetail(variables.productId) 
      });
      
      // Also invalidate product details
      queryClient.invalidateQueries({ 
        queryKey: productKeys.detail(variables.productId) 
      });
    },
  });
}

/**
 * Hook to sync a product with automatic toast notifications
 */
export function useSyncProductWithToast() {
  const mutation = useSyncProduct();
  
  const syncWithToast = async (productId: string, integrationId?: string) => {
    try {
      const result = await mutation.mutateAsync({ productId, integrationId });
      
      if (result.results) {
        const successCount = result.results.filter(r => r.success).length;
        const failCount = result.results.filter(r => !r.success).length;
        
        if (successCount > 0 && failCount === 0) {
          toast.success(`Product synced to ${successCount} store(s)`, {
            description: result.results
              .filter(r => r.success)
              .map(r => r.store_url.replace(/^https?:\/\//, '').split('/')[0])
              .join(', ')
          });
        } else if (successCount > 0 && failCount > 0) {
          toast.warning('Partially synced', {
            description: `${successCount} succeeded, ${failCount} failed`
          });
        } else {
          const firstError = result.results.find(r => !r.success);
          toast.error('Sync failed', {
            description: firstError?.error || 'Unknown error'
          });
        }
      } else if (result.synced === false) {
        if (result.reason === 'no_active_integrations') {
          toast.info('No stores connected', {
            description: 'Connect a WooCommerce or Shopify store first'
          });
        } else {
          toast.info('Nothing to sync');
        }
      }
      
      return result;
    } catch (error) {
      const apiError = error as ApiError;
      toast.error('Sync failed', {
        description: apiError.response?.data?.detail || apiError.message || 'Unknown error'
      });
      throw error;
    }
  };
  
  return {
    ...mutation,
    syncWithToast,
  };
}

/**
 * Hook to manually link a product to an e-commerce product
 */
export function useLinkProduct() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (params: LinkProductParams) => {
      return api.post(`/products/${params.productId}/link`, {
        integration_id: params.integrationId,
        external_product_id: params.externalProductId,
        external_variant_id: params.externalVariantId,
      });
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ 
        queryKey: productKeys.syncStatusDetail(variables.productId) 
      });
      toast.success('Product linked successfully');
    },
    onError: (error: ApiError) => {
      toast.error('Failed to link product', {
        description: error.response?.data?.detail || error.message || 'Unknown error'
      });
    },
  });
}

/**
 * Hook to unlink a product from an e-commerce store
 */
export function useUnlinkProduct() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ 
      productId, 
      integrationId 
    }: { 
      productId: string; 
      integrationId: string;
    }) => {
      return api.delete(`/products/${productId}/link/${integrationId}`);
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ 
        queryKey: productKeys.syncStatusDetail(variables.productId) 
      });
      toast.success('Product unlinked from store');
    },
    onError: (error: ApiError) => {
      toast.error('Failed to unlink product', {
        description: error.response?.data?.detail || error.message || 'Unknown error'
      });
    },
  });
}

/**
 * Hook to bulk sync products
 */
export function useBulkSyncProducts() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (params?: { 
      productIds?: string[]; 
      integrationId?: string;
    }): Promise<BulkSyncResult> => {
      return api.post<BulkSyncResult>('/products/sync/bulk', {
        product_ids: params?.productIds || null,
        integration_id: params?.integrationId || null,
      });
    },
    onSuccess: (data) => {
      // Invalidate all product queries
      queryClient.invalidateQueries({ queryKey: productKeys.all });
      queryClient.invalidateQueries({ queryKey: productKeys.syncStatus() });
      
      if (data.pushed > 0) {
        toast.success(`Synced ${data.pushed} products`, {
          description: data.failed > 0 ? `${data.failed} failed` : undefined
        });
      } else if (data.failed > 0) {
        toast.error(`${data.failed} products failed to sync`);
      } else {
        toast.info('No products to sync');
      }
    },
    onError: (error: ApiError) => {
      toast.error('Bulk sync failed', {
        description: error.response?.data?.detail || error.message || 'Unknown error'
      });
    },
  });
}

/**
 * Hook to auto-sync product after creation
 * Call this after successfully creating a product
 */
export function useAutoSyncAfterCreate() {
  const { syncWithToast } = useSyncProductWithToast();
  
  const autoSync = async (productId: string, showToast: boolean = true) => {
    try {
      const result = await syncWithToast(productId);
      return result;
    } catch (error) {
      // Don't throw - auto-sync failure shouldn't block product creation
      console.error('Auto-sync failed:', error);
      if (showToast) {
        toast.warning('Product created, but sync failed', {
          description: 'You can manually sync from the product page'
        });
      }
      return null;
    }
  };
  
  return { autoSync };
}



