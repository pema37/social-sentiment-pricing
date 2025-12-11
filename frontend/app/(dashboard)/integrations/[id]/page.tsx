'use client';

/**
 * Integration Detail Page
 * 
 * Shows detailed view of a connected integration including:
 * - Connection status and health
 * - Sync controls and status
 * - Sync history logs
 * - Linked products table
 * 
 * URL: /integrations/[id]
 */

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import Link from 'next/link';
import {
  useIntegration,
  useDisconnectIntegration,
  useTriggerSync,
  useSyncStatus,
  useSyncLogs,
  useProductLinks,
} from '@/lib/hooks/use-integrations';
import { PLATFORM_CONFIGS } from '@/types/integration';
import { formatRelativeTime } from '@/lib/utils';

// ==================== Main Component ====================

export default function IntegrationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const integrationId = params.id as string;

  // Fetch integration data
  const { data: integration, isLoading, error } = useIntegration(integrationId);
  
  // Fetch related data
  const { data: syncStatus } = useSyncStatus(
    integrationId,
    { polling: integration?.sync_status === 'syncing' }
  );
  const { data: syncLogs } = useSyncLogs(integrationId, { page: 1, pageSize: 10 });
  const { data: productLinks } = useProductLinks(integrationId);

  // Mutations
  const triggerSync = useTriggerSync();
  const disconnect = useDisconnectIntegration();

  // Local state
  const [showDisconnectModal, setShowDisconnectModal] = useState(false);

  // Loading state
  if (isLoading) {
    return <LoadingSkeleton />;
  }

  // Error state
  if (error || !integration) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-red-700">Failed to load integration details.</p>
        <Link
          href="/integrations"
          className="mt-4 inline-block text-sm text-indigo-600 hover:text-indigo-500"
        >
          ← Back to Integrations
        </Link>
      </div>
    );
  }

  const config = PLATFORM_CONFIGS[integration.platform];
  const currentSyncStatus = syncStatus?.sync_status || integration.sync_status;
  const isSyncing = currentSyncStatus === 'syncing';

  // Handlers
  const handleSync = () => {
    triggerSync.mutate({ integrationId, syncType: 'full' });
  };

  const handleDisconnect = () => {
    disconnect.mutate(integrationId, {
      onSuccess: () => {
        router.push('/integrations?disconnected=true');
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/integrations"
        className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
      >
        <BackArrowIcon />
        <span className="ml-1">Back to Integrations</span>
      </Link>

      {/* Header Card */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          {/* Store info */}
          <div className="flex items-center gap-4">
            <Image
              src={config.logo}
              alt={config.name}
              width={48}
              height={48}
              className="h-12 w-12"
            />
            <div>
              <h1 className="text-xl font-semibold text-gray-900">
                {integration.store_name || integration.store_url}
              </h1>
              <p className="text-sm text-gray-500">{config.name}</p>
            </div>
          </div>

          {/* Status badge */}
          <StatusBadge status={integration.status} />
        </div>

        {/* Error message */}
        {integration.error_message && (
          <div className="mt-4 rounded-md bg-red-50 p-3">
            <p className="text-sm text-red-700">{integration.error_message}</p>
          </div>
        )}

        {/* Stats grid */}
        <div className="mt-6 grid grid-cols-2 gap-4 border-t border-gray-100 pt-6 sm:grid-cols-4">
          <StatItem
            label="Products Synced"
            value={integration.products_synced.toString()}
          />
          <StatItem
            label="Last Sync"
            value={
              integration.last_sync_at
                ? formatRelativeTime(integration.last_sync_at)
                : 'Never'
            }
          />
          <StatItem
            label="Sync Status"
            value={currentSyncStatus}
            valueClassName={
              currentSyncStatus === 'syncing'
                ? 'text-blue-600'
                : currentSyncStatus === 'error'
                ? 'text-red-600'
                : 'text-green-600'
            }
          />
          <StatItem
            label="Connected"
            value={formatRelativeTime(integration.created_at)}
          />
        </div>

        {/* Action buttons */}
        <div className="mt-6 flex flex-wrap gap-3 border-t border-gray-100 pt-6">
          {integration.status === 'active' && (
            <button
              onClick={handleSync}
              disabled={isSyncing || triggerSync.isPending}
              className={`
                inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium
                ${
                  isSyncing || triggerSync.isPending
                    ? 'cursor-not-allowed bg-gray-100 text-gray-400'
                    : 'bg-indigo-600 text-white hover:bg-indigo-700'
                }
              `}
            >
              {isSyncing ? (
                <>
                  <LoadingSpinner />
                  Syncing...
                </>
              ) : (
                <>
                  <SyncIcon />
                  Sync Now
                </>
              )}
            </button>
          )}

          <button
            onClick={() => setShowDisconnectModal(true)}
            className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Disconnect
          </button>
        </div>
      </div>

      {/* Sync History */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-medium text-gray-900">Sync History</h2>
        
        {syncLogs?.items && syncLogs.items.length > 0 ? (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Type
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Status
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Products
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Duration
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Started
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {syncLogs.items.map((log) => (
                  <tr key={log.id}>
                    <td className="whitespace-nowrap px-3 py-2 text-sm text-gray-900">
                      <span className="capitalize">{log.sync_type}</span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm">
                      {log.success ? (
                        <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                          Success
                        </span>
                      ) : (
                        <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
                          Failed
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm text-gray-600">
                      +{log.products_created} / ~{log.products_updated} / -{log.products_deleted}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm text-gray-600">
                      {log.duration_seconds
                        ? `${log.duration_seconds.toFixed(1)}s`
                        : '-'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm text-gray-500">
                      {formatRelativeTime(log.started_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 text-sm text-gray-500">No sync history yet.</p>
        )}
      </div>

      {/* Linked Products */}
      <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium text-gray-900">Linked Products</h2>
          <span className="text-sm text-gray-500">
            {productLinks?.total || 0} products
          </span>
        </div>

        {productLinks?.links && productLinks.links.length > 0 ? (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    External ID
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Price
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Last Pull
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Last Push
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-medium uppercase text-gray-500">
                    Sync
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {productLinks.links.slice(0, 10).map((link) => (
                  <tr key={link.id}>
                    <td className="whitespace-nowrap px-3 py-2 text-sm font-mono text-gray-900">
                      {link.external_product_id}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm text-gray-600">
                      {link.external_price
                        ? `$${link.external_price.toFixed(2)}`
                        : '-'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm text-gray-500">
                      {link.last_price_pull_at
                        ? formatRelativeTime(link.last_price_pull_at)
                        : '-'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm text-gray-500">
                      {link.last_price_push_at
                        ? formatRelativeTime(link.last_price_push_at)
                        : '-'}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-sm">
                      {link.sync_enabled ? (
                        <span className="text-green-600">Enabled</span>
                      ) : (
                        <span className="text-gray-400">Disabled</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            {productLinks.total > 10 && (
              <p className="mt-3 text-center text-sm text-gray-500">
                Showing 10 of {productLinks.total} products
              </p>
            )}
          </div>
        ) : (
          <p className="mt-4 text-sm text-gray-500">
            No products synced yet. Click {"Sync Now"} to import products.
          </p>
        )}
      </div>

      {/* Disconnect Modal */}
      {showDisconnectModal && (
        <DisconnectModal
          storeName={integration.store_name || integration.store_url}
          isDisconnecting={disconnect.isPending}
          onConfirm={handleDisconnect}
          onCancel={() => setShowDisconnectModal(false)}
        />
      )}
    </div>
  );
}

// ==================== Sub-components ====================

function StatusBadge({ status }: { status: string }) {
  const styles = {
    active: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
    paused: 'bg-yellow-100 text-yellow-800',
    disconnected: 'bg-gray-100 text-gray-800',
  };

  return (
    <span
      className={`inline-flex rounded-full px-3 py-1 text-sm font-medium capitalize ${
        styles[status as keyof typeof styles] || styles.disconnected
      }`}
    >
      {status}
    </span>
  );
}

function StatItem({
  label,
  value,
  valueClassName = 'text-gray-900',
}: {
  label: string;
  value: string;
  valueClassName?: string;
}) {
  return (
    <div>
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${valueClassName}`}>{value}</p>
    </div>
  );
}

function DisconnectModal({
  storeName,
  isDisconnecting,
  onConfirm,
  onCancel,
}: {
  storeName: string;
  isDisconnecting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h3 className="text-lg font-medium text-gray-900">
          Disconnect {storeName}?
        </h3>
        <p className="mt-2 text-sm text-gray-500">
          This will stop syncing products and remove the connection. 
          Your product data will remain in the system.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={isDisconnecting}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isDisconnecting}
            className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isDisconnecting ? 'Disconnecting...' : 'Disconnect'}
          </button>
        </div>
      </div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="h-4 w-32 animate-pulse rounded bg-gray-200" />
      <div className="h-64 animate-pulse rounded-lg bg-gray-100" />
      <div className="h-48 animate-pulse rounded-lg bg-gray-100" />
    </div>
  );
}

function BackArrowIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
    </svg>
  );
}

function SyncIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );
}

function LoadingSpinner() {
  return (
    <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}
