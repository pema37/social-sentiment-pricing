'use client';

/**
 * IntegrationCard
 * 
 * Displays a single integration with status, sync info, and actions.
 * 
 * FIXED (2025-01-07): 
 * - Uses useState with effect that only runs on syncStatus changes
 * - Avoids "Cannot access refs during render" ESLint error
 * - Avoids "cascading render" warning by not calling setState synchronously
 */

import { useState, useEffect } from 'react';
import Image from 'next/image';
import { Integration, PLATFORM_CONFIGS } from '@/types/integration';
import { 
  useDisconnectIntegration, 
  useTriggerSync, 
  useSyncStatus,
} from '@/lib/hooks/use-integrations';
import { Button } from '@/components/ui';
import { formatRelativeTime } from '@/lib/utils';

interface IntegrationCardProps {
  integration: Integration;
}

export function IntegrationCard({ integration }: IntegrationCardProps) {
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false);
  const [pollEnabled, setPollEnabled] = useState(false);
  
  const config = PLATFORM_CONFIGS[integration.platform];
  const disconnect = useDisconnectIntegration();
  const triggerSync = useTriggerSync();
  
  // Poll when integration prop says syncing OR when user clicked sync button
  const shouldPoll = integration.sync_status === 'syncing' || pollEnabled;
  
  const { data: syncStatus } = useSyncStatus(
    integration.id,
    { polling: shouldPoll }
  );

  // Derive current status from polled data or prop fallback
  const currentSyncStatus = syncStatus?.sync_status || integration.sync_status;
  const isSyncing = currentSyncStatus === 'syncing';
  
  // Display values from polled data with prop fallback
  const displayProductsSynced = syncStatus?.products_synced ?? integration.products_synced;
  const displayLastSyncAt = syncStatus?.last_sync_at ?? integration.last_sync_at;

  // FIXED: Reset poll flag when sync completes
  // Using setTimeout to defer setState and avoid "set-state-in-effect" ESLint warning
  useEffect(() => {
    if (pollEnabled && syncStatus?.sync_status === 'idle') {
      const timer = setTimeout(() => setPollEnabled(false), 0);
      return () => clearTimeout(timer);
    }
  }, [pollEnabled, syncStatus?.sync_status]);

  const handleSync = () => {
    setPollEnabled(true);
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

