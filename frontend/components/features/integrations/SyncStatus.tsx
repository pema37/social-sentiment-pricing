'use client';

/**
 * SyncStatus Component
 * 
 * A reusable component that displays the current sync status
 * of an integration. Shows progress, last sync time, and
 * allows triggering a new sync.
 * 
 * Can be used standalone or embedded in other components.
 */

import { useSyncStatus, useTriggerSync } from '@/lib/hooks/use-integrations';
import { formatRelativeTime } from '@/lib/utils';
import type { SyncStatus as SyncStatusType } from '@/types/integration';

// ==================== Types ====================

interface SyncStatusProps {
  /** Integration ID to show status for */
  integrationId: string;
  /** Current sync status from integration (fallback if hook hasn't loaded) */
  initialStatus?: SyncStatusType;
  /** Last sync timestamp */
  lastSyncAt?: string | null;
  /** Number of products synced */
  productsSynced?: number;
  /** Whether to show the sync button */
  showSyncButton?: boolean;
  /** Compact mode for embedding in cards */
  compact?: boolean;
  /** Callback when sync completes */
  onSyncComplete?: () => void;
}

// ==================== Main Component ====================

export function SyncStatus({
  integrationId,
  initialStatus = 'idle',
  lastSyncAt,
  productsSynced = 0,
  showSyncButton = true,
  compact = false,
  onSyncComplete,
}: SyncStatusProps) {
  // Poll sync status when syncing
  const { data: syncStatus } = useSyncStatus(
    integrationId,
    { polling: initialStatus === 'syncing' }
  );
  
  const triggerSync = useTriggerSync();

  // Use polled status if available, otherwise fallback
  const currentStatus = syncStatus?.sync_status || initialStatus;
  const currentProducts = syncStatus?.products_synced ?? productsSynced;
  const isSyncing = currentStatus === 'syncing';

  // Handle sync trigger
  const handleSync = () => {
    triggerSync.mutate(
      { integrationId, syncType: 'full' },
      {
        onSuccess: () => {
          onSyncComplete?.();
        },
      }
    );
  };

  // Compact version for cards
  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <StatusIndicator status={currentStatus} size="sm" />
        <span className="text-sm text-gray-600">
          {getStatusText(currentStatus, currentProducts)}
        </span>
      </div>
    );
  }

  // Full version
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">Sync Status</h3>
        <StatusIndicator status={currentStatus} />
      </div>

      {/* Status details */}
      <div className="mt-3 space-y-2">
        {/* Current status */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">Status</span>
          <span className={getStatusColor(currentStatus)}>
            {getStatusLabel(currentStatus)}
          </span>
        </div>

        {/* Products synced */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">Products</span>
          <span className="font-medium text-gray-900">{currentProducts}</span>
        </div>

        {/* Last sync */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-500">Last sync</span>
          <span className="text-gray-900">
            {lastSyncAt ? formatRelativeTime(lastSyncAt) : 'Never'}
          </span>
        </div>

        {/* Progress bar when syncing */}
        {isSyncing && syncStatus?.current_progress !== undefined && (
          <div className="mt-2">
            <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className="h-full rounded-full bg-indigo-600 transition-all duration-300"
                style={{ width: `${syncStatus.current_progress}%` }}
              />
            </div>
            <p className="mt-1 text-xs text-gray-500 text-center">
              {syncStatus.current_progress}% complete
            </p>
          </div>
        )}
      </div>

      {/* Sync button */}
      {showSyncButton && (
        <button
          onClick={handleSync}
          disabled={isSyncing || triggerSync.isPending}
          className={`
            mt-4 w-full rounded-md px-3 py-2 text-sm font-medium
            transition-colors duration-150
            ${
              isSyncing || triggerSync.isPending
                ? 'cursor-not-allowed bg-gray-100 text-gray-400'
                : 'bg-indigo-600 text-white hover:bg-indigo-700'
            }
          `}
        >
          {isSyncing ? (
            <span className="flex items-center justify-center gap-2">
              <LoadingSpinner />
              Syncing...
            </span>
          ) : (
            'Sync Now'
          )}
        </button>
      )}
    </div>
  );
}

// ==================== Status Indicator ====================

interface StatusIndicatorProps {
  status: SyncStatusType;
  size?: 'sm' | 'md';
}

function StatusIndicator({ status, size = 'md' }: StatusIndicatorProps) {
  const sizeClasses = size === 'sm' ? 'h-2 w-2' : 'h-2.5 w-2.5';
  
  const colorClasses = {
    idle: 'bg-green-500',
    syncing: 'bg-blue-500 animate-pulse',
    error: 'bg-red-500',
  };

  return (
    <span className="flex items-center gap-1.5">
      <span
        className={`inline-block rounded-full ${sizeClasses} ${
          colorClasses[status] || colorClasses.idle
        }`}
      />
      {size === 'md' && (
        <span className={`text-xs font-medium ${getStatusColor(status)}`}>
          {getStatusLabel(status)}
        </span>
      )}
    </span>
  );
}

// ==================== Helpers ====================

function getStatusLabel(status: SyncStatusType): string {
  const labels: Record<SyncStatusType, string> = {
    idle: 'Ready',
    syncing: 'Syncing',
    error: 'Error',
  };
  return labels[status] || 'Unknown';
}

function getStatusColor(status: SyncStatusType): string {
  const colors: Record<SyncStatusType, string> = {
    idle: 'text-green-600',
    syncing: 'text-blue-600',
    error: 'text-red-600',
  };
  return colors[status] || 'text-gray-600';
}

function getStatusText(status: SyncStatusType, products: number): string {
  if (status === 'syncing') {
    return 'Syncing...';
  }
  if (status === 'error') {
    return 'Sync error';
  }
  return `${products} products synced`;
}

// ==================== Loading Spinner ====================

function LoadingSpinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

// ==================== Export Indicator Separately ====================

export { StatusIndicator };
