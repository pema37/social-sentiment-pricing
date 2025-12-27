'use client';

/**
 * IntegrationCard
 * 
 * Displays a single integration with status, sync info, and actions.
 * 
 * FIXED: Now properly polls for sync status and displays updated values
 */

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { Integration, PLATFORM_CONFIGS } from '@/types/integration';
import { 
  useDisconnectIntegration, 
  useTriggerSync, 
  useSyncStatus,
  integrationKeys,
} from '@/lib/hooks/use-integrations';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui';
import { formatRelativeTime } from '@/lib/utils';

interface IntegrationCardProps {
  integration: Integration;
}

export function IntegrationCard({ integration }: IntegrationCardProps) {
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false);
  // FIXED: Track if we just triggered a sync to enable polling
  const [justTriggeredSync, setJustTriggeredSync] = useState(false);
  
  const queryClient = useQueryClient();
  const config = PLATFORM_CONFIGS[integration.platform];
  const disconnect = useDisconnectIntegration();
  const triggerSync = useTriggerSync();
  
  // FIXED: Poll sync status when syncing OR when we just triggered a sync
  const shouldPoll = integration.sync_status === 'syncing' || justTriggeredSync;
  
  const { data: syncStatus } = useSyncStatus(
    integration.id,
    { polling: shouldPoll }
  );

  // FIXED: Use polled status if available, otherwise fall back to prop
  const currentSyncStatus = syncStatus?.sync_status || integration.sync_status;
  const isSyncing = currentSyncStatus === 'syncing';
  
  // FIXED: Use polled values for display, with fallback to integration prop
  const displayProductsSynced = syncStatus?.products_synced ?? integration.products_synced;
  const displayLastSyncAt = syncStatus?.last_sync_at ?? integration.last_sync_at;

  // FIXED: Stop polling when sync completes and refresh the integration data
  useEffect(() => {
    if (justTriggeredSync && syncStatus?.sync_status === 'idle') {
      setJustTriggeredSync(false);
      // Refresh the parent integration list to get updated data
      queryClient.invalidateQueries({ queryKey: integrationKeys.list() });
      queryClient.invalidateQueries({ queryKey: integrationKeys.detail(integration.id) });
    }
  }, [syncStatus?.sync_status, justTriggeredSync, queryClient, integration.id]);

  const handleSync = () => {
    setJustTriggeredSync(true);
    triggerSync.mutate({ integrationId: integration.id, syncType: 'full' });
  };

  const handleDisconnect = () => {
    disconnect.mutate(integration.id, {
      onSuccess: () => setShowDisconnectConfirm(false),
    });
  };

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

      {/* Stats - FIXED: Now uses polled syncStatus values */}
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
        <div className="mt-3 rounded-md bg-red-50 p-2">
          <p className="text-xs text-red-700">{integration.error_message}</p>
        </div>
      )}

      {/* Actions */}
      <div className="mt-4 flex gap-2">
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
        
        {!showDisconnectConfirm ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDisconnectConfirm(true)}
          >
            Disconnect
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button
              variant="danger"
              size="sm"
              onClick={handleDisconnect}
              disabled={disconnect.isPending}
            >
              {disconnect.isPending ? 'Disconnecting...' : 'Confirm'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDisconnectConfirm(false)}
            >
              Cancel
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}
