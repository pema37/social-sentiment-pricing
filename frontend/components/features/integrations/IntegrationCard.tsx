'use client';

/**
 * IntegrationCard
 * 
 * Displays a single integration with status, sync info, and actions.
 * 
 * FIXED (2025-01-19): 
 * - Shows "Delete" button for disconnected integrations (David's feedback)
 * - Both disconnect and delete use the same API (DELETE endpoint)
 * 
 * FIXED (2026-01-27):
 * - Bug #1: Never-ending sync UI
 * - Root cause: When polling stopped, UI fell back to stale `integration.sync_status` prop
 * - Fix: Track last known values in state, update only when poll returns fresh data
 * 
 * NOTE: ESLint disable comments are used for setState-in-effect because these are
 * valid patterns - we're syncing component state with external query data (React Query).
 * This is the recommended pattern per React docs for "synchronizing with external systems".
 */

import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { Trash2 } from 'lucide-react';
import { Integration, PLATFORM_CONFIGS } from '@/types/integration';
import { 
  useDisconnectIntegration, 
  useTriggerSync, 
  useSyncStatus,
  useInitOAuth,
} from '@/lib/hooks/use-integrations';
import { Button } from '@/components/ui';
import { formatRelativeTime } from '@/lib/utils';

// Type for the cached sync data we want to persist
interface CachedSyncData {
  sync_status: string;
  products_synced: number;
  last_sync_at: string | null;
}

interface IntegrationCardProps {
  integration: Integration;
}

export function IntegrationCard({ integration }: IntegrationCardProps) {
  const [showConfirm, setShowConfirm] = useState(false);
  const [pollEnabled, setPollEnabled] = useState(false);
  
  // Cache the last known sync data to prevent UI from reverting to stale props
  const [cachedSyncData, setCachedSyncData] = useState<CachedSyncData | null>(null);
  
  const config = PLATFORM_CONFIGS[integration.platform];
  const disconnect = useDisconnectIntegration();
  const triggerSync = useTriggerSync();
  const initOAuth = useInitOAuth(); 
  
  // Poll when integration prop says syncing OR when user clicked sync button
  const shouldPoll = integration.sync_status === 'syncing' || pollEnabled;
  
  const { data: syncStatus } = useSyncStatus(
    integration.id,
    { polling: shouldPoll }
  );

  // Update cached data when we get fresh poll results
  // This is a valid use of setState in effect - syncing with external query data
  useEffect(() => {
    if (syncStatus?.sync_status) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Valid: syncing state with external query data
      setCachedSyncData({
        sync_status: syncStatus.sync_status,
        products_synced: syncStatus.products_synced ?? 0,
        last_sync_at: syncStatus.last_sync_at ?? null,
      });
    }
  }, [syncStatus?.sync_status, syncStatus?.products_synced, syncStatus?.last_sync_at]);

  // Reset poll flag when sync completes
  // This is a valid use of setState in effect - responding to external state change
  useEffect(() => {
    if (syncStatus?.sync_status && syncStatus.sync_status !== 'syncing') {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- Valid: stopping poll when external sync completes
      setPollEnabled(false);
    }
  }, [syncStatus?.sync_status]);

  // Derive current status with fallback chain:
  // 1. Fresh polled data (if available)
  // 2. Cached data from previous polls
  // 3. Prop fallback (initial render only)
  const currentSyncStatus = syncStatus?.sync_status 
    ?? cachedSyncData?.sync_status 
    ?? integration.sync_status;
  const isSyncing = currentSyncStatus === 'syncing';
  
  // Display values with same fallback chain
  const displayProductsSynced = syncStatus?.products_synced 
    ?? cachedSyncData?.products_synced 
    ?? integration.products_synced 
    ?? 0;
  const displayLastSyncAt = syncStatus?.last_sync_at 
    ?? cachedSyncData?.last_sync_at 
    ?? integration.last_sync_at;

  // Check if this is a disconnected/invalid integration
  const isDisconnected = integration.status === 'disconnected';

  const handleSync = useCallback(() => {
    setPollEnabled(true);
    triggerSync.mutate({ integrationId: integration.id, syncType: 'full' });
  }, [triggerSync, integration.id]);

  // Both disconnect and delete use the same API endpoint.
  // Uses mutateAsync so setShowConfirm(false) runs deterministically after
  // the mutation settles — per-call onSuccess callbacks in React Query v5
  // are ephemeral and may not fire if the component re-renders mid-flight
  // (which happens because the hook's onSuccess invalidates the full list).
  const handleRemove = useCallback(async () => {
    try {
      await disconnect.mutateAsync(integration.id);
      setShowConfirm(false);
    } catch {
      // React Query sets disconnect.isError + disconnect.error automatically.
      // No additional handling needed here.
    }
  }, [disconnect, integration.id]);

  const statusColors = {
    active: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
    paused: 'bg-yellow-100 text-yellow-800',
    disconnected: 'bg-gray-100 text-gray-800',
  };

  return (
    <article className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <Image
            src={config.logo}
            alt={config.name}
            width={32}
            height={32}
            className="h-8 w-8 object-contain"
          />
          <div>
            <h3 className="font-medium text-gray-900">
              {integration.store_name || integration.store_url}
            </h3>
            <p className="text-sm text-gray-500">{config.name}</p>
          </div>
        </div>
        <span
          className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${statusColors[integration.status]}`}
        >
          {integration.status}
        </span>
      </div>

      {/* Stats */}
      <div className="mt-4 grid grid-cols-2 gap-4 border-t border-gray-100 pt-4">
        <div>
          <p className="text-sm text-gray-500">Products Synced</p>
          <p className="text-lg font-semibold text-gray-900">
            {isSyncing ? (
              <span className="flex items-center gap-2">
                <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
                <span className="text-sm text-gray-500">Syncing...</span>
              </span>
            ) : (
              displayProductsSynced
            )}
          </p>
        </div>
        <div>
          <p className="text-sm text-gray-500">Last Sync</p>
          <p className="text-sm font-medium text-gray-900">
            {isSyncing ? (
              <span className="text-blue-600">In progress...</span>
            ) : displayLastSyncAt ? (
              formatRelativeTime(displayLastSyncAt)
            ) : (
              'Never'
            )}
          </p>
        </div>
      </div>

      {/* Error message */}
      {integration.error_message && (
        <div className="mt-3 rounded-md bg-red-50 p-3 space-y-2">
          <p className="text-xs text-red-700">{integration.error_message}</p>
          {integration.status === 'error' && (
            <button
              onClick={() =>
                initOAuth.mutate({
                  platform: integration.platform,
                  store_url: integration.store_url,
                })
              }
              disabled={initOAuth.isPending}
              className="text-xs font-semibold text-red-700 underline hover:no-underline disabled:opacity-50"
            >
              {initOAuth.isPending ? 'Redirecting to Shopify…' : '↻ Reconnect this store'}
            </button>
          )}
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex gap-2">
        {/* Sync button - only for active integrations */}
        {integration.status === 'active' && (
          <Button
            variant="secondary"
            size="sm"
            onClick={handleSync}
            disabled={isSyncing || triggerSync.isPending}
          >
            {isSyncing ? 'Syncing...' : 'Sync Now'}
          </Button>
        )}
        
        {/* Disconnect/Delete button */}
        {!showConfirm ? (
          <Button
            variant={isDisconnected ? 'danger' : 'ghost'}
            size="sm"
            onClick={() => setShowConfirm(true)}
          >
            {isDisconnected ? (
              <>
                <Trash2 className="w-4 h-4 mr-1" />
                Delete
              </>
            ) : (
              'Disconnect'
            )}
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button
              variant="danger"
              size="sm"
              onClick={handleRemove}
              disabled={disconnect.isPending}
            >
              {disconnect.isPending ? 'Removing...' : 'Confirm'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowConfirm(false)}
            >
              Cancel
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}


