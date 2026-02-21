// frontend/components/features/products/ProductStoreSync.tsx
// Component for syncing products to e-commerce stores (WooCommerce/Shopify)
'use client';

import { useState } from 'react';
import { 
  Store, 
  Link2, 
  Unlink, 
  RefreshCw, 
  Check, 
  AlertCircle,
  ExternalLink,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { productKeys } from '@/lib/api/query-keys';
import { toast } from 'sonner';
import Link from 'next/link';

// ─────────────────────────────────────────────────────────────────────────────
// Types (snake_case - matches raw API response, no transformation in client)
// ─────────────────────────────────────────────────────────────────────────────

interface ProductStoreSyncProps {
  productId: string;
}

interface SyncLink {
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

interface AvailableIntegration {
  integration_id: string;
  platform: string;
  store_url: string;
}

interface SyncStatus {
  product_id: string;
  product_name: string;
  has_links: boolean;
  links: SyncLink[];
  available_integrations: AvailableIntegration[];
}

interface SyncResultItem {
  integration_id: string;
  platform: string;
  store_url: string;
  success: boolean;
  external_product_id?: string;
  error?: string;
  error_code?: string;
}

interface SyncResult {
  product_id: string;
  product_name: string;
  results?: SyncResultItem[];
  synced?: boolean;
  reason?: string;
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
// API Functions
// ─────────────────────────────────────────────────────────────────────────────

async function fetchSyncStatus(productId: string): Promise<SyncStatus> {
  return api.get<SyncStatus>(`/products/${productId}/sync-status`);
}

async function syncProduct(productId: string, integrationId?: string): Promise<SyncResult> {
  return api.post<SyncResult>(`/products/${productId}/sync`, {
    integration_id: integrationId || null
  });
}

async function unlinkProduct(productId: string, integrationId: string): Promise<void> {
  return api.delete(`/products/${productId}/link/${integrationId}`);
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Components
// ─────────────────────────────────────────────────────────────────────────────

function PlatformBadge({ platform }: { platform: string }) {
  const colors: Record<string, string> = {
    woocommerce: 'bg-purple-100 text-purple-700 border-purple-200',
    shopify: 'bg-green-100 text-green-700 border-green-200',
  };
  
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded border ${colors[platform] || 'bg-gray-100 text-gray-700 border-gray-200'}`}>
      {platform === 'woocommerce' ? 'WooCommerce' : 'Shopify'}
    </span>
  );
}

function formatDate(dateString?: string): string {
  if (!dateString) return 'Never';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function ProductStoreSync({ productId }: ProductStoreSyncProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const queryClient = useQueryClient();
  
  // Fetch sync status
  const { 
    data: status, 
    isLoading, 
    error,
    refetch 
  } = useQuery({
    queryKey: productKeys.syncStatusDetail(productId),
    queryFn: () => fetchSyncStatus(productId),
  });
  
  // Sync mutation
  const syncMutation = useMutation({
    mutationFn: ({ integrationId }: { integrationId?: string }) => 
      syncProduct(productId, integrationId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: productKeys.syncStatusDetail(productId) });
      
      // Check results
      if (data.results) {
        const successCount = data.results.filter(r => r.success).length;
        const failCount = data.results.filter(r => !r.success).length;
        
        if (successCount > 0 && failCount === 0) {
          toast.success(`Product synced to ${successCount} store(s)`);
        } else if (successCount > 0 && failCount > 0) {
          toast.warning(`Synced to ${successCount} stores, ${failCount} failed`);
        } else if (failCount > 0) {
          const firstError = data.results.find(r => !r.success);
          toast.error(firstError?.error || 'Sync failed');
        }
      } else if (data.synced === false) {
        toast.info(data.reason === 'no_active_integrations' 
          ? 'No active store connections. Connect a store first.'
          : 'Nothing to sync');
      }
    },
    onError: (error: ApiError) => {
      toast.error(error.response?.data?.detail || error.message || 'Failed to sync product');
    }
  });
  
  // Unlink mutation
  const unlinkMutation = useMutation({
    mutationFn: ({ integrationId }: { integrationId: string }) =>
      unlinkProduct(productId, integrationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productKeys.syncStatusDetail(productId) });
      toast.success('Product unlinked from store');
    },
    onError: (error: ApiError) => {
      toast.error(error.response?.data?.detail || error.message || 'Failed to unlink product');
    }
  });
  
  // Loading state
  if (isLoading) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-2 text-gray-500">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span>Loading sync status...</span>
        </div>
      </Card>
    );
  }
  
  // Error state
  if (error) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-2 text-red-600">
          <AlertCircle className="h-4 w-4" />
          <span>Failed to load sync status</span>
          <Button variant="ghost" size="sm" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      </Card>
    );
  }
  
  const hasLinks = status?.has_links || false;
  const hasAvailableIntegrations = (status?.available_integrations?.length || 0) > 0;
  const totalIntegrations = (status?.links?.length || 0) + (status?.available_integrations?.length || 0);
  
  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div 
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          <Store className="h-5 w-5 text-blue-500" />
          <div>
            <h3 className="font-semibold text-gray-900">Store Sync</h3>
            <p className="text-sm text-gray-500">
              {hasLinks 
                ? `Linked to ${status?.links?.length} store(s)` 
                : 'Not linked to any stores'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {hasLinks && (
            <span className="flex items-center gap-1 text-sm text-green-600">
              <Check className="h-4 w-4" />
              Synced
            </span>
          )}
          {isExpanded ? (
            <ChevronUp className="h-5 w-5 text-gray-400" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-400" />
          )}
        </div>
      </div>
      
      {/* Content */}
      {isExpanded && (
        <div className="border-t border-gray-100 p-4 space-y-4">
          {/* Existing Links */}
          {status?.links && status.links.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-gray-700">Connected Stores</h4>
              {status.links.map((link) => (
                <div 
                  key={link.link_id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center gap-3">
                    <Link2 className="h-4 w-4 text-green-500" />
                    <div>
                      <div className="flex items-center gap-2">
                        <PlatformBadge platform={link.platform} />
                        <span className="text-sm font-medium text-gray-900">
                          {link.store_url.replace(/^https?:\/\//, '').split('/')[0]}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 mt-1">
                        ID: {link.external_product_id} • 
                        Last sync: {formatDate(link.last_synced_at)}
                        {link.external_price && ` • Price: $${link.external_price.toFixed(2)}`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        unlinkMutation.mutate({ integrationId: link.integration_id });
                      }}
                      isLoading={unlinkMutation.isPending}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Unlink className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
          
          {/* Available Integrations (not linked yet) */}
          {status?.available_integrations && status.available_integrations.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-gray-700">Available Stores</h4>
              {status.available_integrations.map((integration) => (
                <div 
                  key={integration.integration_id}
                  className="flex items-center justify-between p-3 bg-blue-50 rounded-lg border border-blue-100"
                >
                  <div className="flex items-center gap-3">
                    <Store className="h-4 w-4 text-blue-500" />
                    <div>
                      <div className="flex items-center gap-2">
                        <PlatformBadge platform={integration.platform} />
                        <span className="text-sm font-medium text-gray-900">
                          {integration.store_url.replace(/^https?:\/\//, '').split('/')[0]}
                        </span>
                      </div>
                      <p className="text-xs text-blue-600 mt-1">
                        Click &quot;Sync&quot; to create this product in the store
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      syncMutation.mutate({ integrationId: integration.integration_id });
                    }}
                    isLoading={syncMutation.isPending}
                  >
                    <RefreshCw className="h-4 w-4 mr-1" />
                    Sync
                  </Button>
                </div>
              ))}
            </div>
          )}
          
          {/* No integrations at all */}
          {totalIntegrations === 0 && (
            <div className="text-center py-6">
              <Store className="h-10 w-10 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 mb-3">No store connections available</p>
              <Link href="/integrations">
                <Button variant="secondary" size="sm">
                  <ExternalLink className="h-4 w-4 mr-1" />
                  Connect a Store
                </Button>
              </Link>
            </div>
          )}
          
          {/* Sync All Button (when there are links) */}
          {hasLinks && hasAvailableIntegrations && (
            <div className="pt-3 border-t border-gray-100">
              <Button
                variant="secondary"
                className="w-full"
                onClick={() => syncMutation.mutate({})}
                isLoading={syncMutation.isPending}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Sync to All Stores
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default ProductStoreSync;




