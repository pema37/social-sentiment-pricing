export const dynamic = 'force-dynamic';
'use client';

/**
 * Integrations Page
 *
 * Connect and manage e-commerce platform integrations.
 * Handles OAuth callback params, sync progress tracking, and diagnostic health.
 */

import { Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useIntegrations } from '@/lib/hooks/use-integrations';
import { getAllSyncStatus } from '@/lib/api/integrations';
import { integrationKeys } from '@/lib/api/query-keys';
import { SectionHeader } from '@/components/ui';
import { IntegrationsList } from '@/components/features/integrations/IntegrationsList';
import { ConnectPlatformCard } from '@/components/features/integrations/ConnectPlatformCard';
import { IntegrationsEmptyState } from '@/components/features/integrations/IntegrationsEmptyState';
import { ConnectionSuccessToast } from '@/components/features/integrations/ConnectionSuccessToast';
import { SyncProgressBanner } from '@/components/features/integrations/sync-progress-banner';
import { DiagnosticPanel } from '@/components/features/integrations/diagnostic-panel';
import { PLATFORM_CONFIGS, type EcommercePlatform } from '@/types/integration';

export default function IntegrationsPage() {
  return (
    <Suspense fallback={
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="h-48 animate-pulse rounded-lg border border-gray-200 bg-gray-50"
          />
        ))}
      </div>
    }>
      <IntegrationsContent />
    </Suspense>
  );
}

function IntegrationsContent() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useIntegrations();
  
  // ========== Sync status polling ==========
  const { data: syncStatus } = useQuery({
    queryKey: integrationKeys.allSyncStatus(),
    queryFn: getAllSyncStatus,
    refetchInterval: (query) => {
      // Poll every 2s while syncing, every 30s otherwise
      const data = query.state.data;
      return data?.any_syncing ? 2000 : 30000;
    },
    refetchIntervalInBackground: true,
  });
  
  // Track previous sync state to detect completion
  const wasSyncingRef = useRef(false);
  
  // Handle OAuth callback params
  const [toast, setToast] = useState<{
    type: 'success' | 'error';
    message: string;
    platform?: string;
  } | null>(null);

  // Track if we've processed the OAuth callback params
  const hasProcessedCallback = useRef(false);

  // Detect sync completion
  useEffect(() => {
    const isSyncing = syncStatus?.any_syncing ?? false;
    
    if (wasSyncingRef.current && !isSyncing) {
      // Sync just completed - refresh data and show toast
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['integrations'] });
      // Defer setState to avoid cascading render warning
      queueMicrotask(() => {
        setToast({
          type: 'success',
          message: 'Sync complete! Your products are up to date.',
        });
      });
    }
    
    wasSyncingRef.current = isSyncing;
  }, [syncStatus?.any_syncing, queryClient]);

  useEffect(() => {
    // Only process once
    if (hasProcessedCallback.current) return;

    const connected = searchParams.get('connected');
    const errorParam = searchParams.get('error');
    const platform = searchParams.get('platform');
    const message = searchParams.get('message');

    // Early return if no params to process
    if (!connected && !errorParam) return;

    // Mark as processed
    hasProcessedCallback.current = true;

    // Clean URL first
    window.history.replaceState({}, '', '/integrations');

    // Defer state update to avoid cascading render warning
    queueMicrotask(() => {
      if (connected === 'true' && platform) {
        setToast({
          type: 'success',
          message: `Successfully connected ${platform}!`,
          platform,
        });
      } else if (errorParam) {
        setToast({
          type: 'error',
          message: message || `Connection failed: ${errorParam}`,
          platform: platform || undefined,
        });
      }
    });
  }, [searchParams]);

  // Get platforms that aren't connected yet
  const connectedPlatforms = new Set(
    data?.integrations
      .filter((i) => i.status === 'active')
      .map((i) => i.platform) || []
  );
  
  const availablePlatforms = (Object.keys(PLATFORM_CONFIGS) as EcommercePlatform[])
    .filter((p) => !connectedPlatforms.has(p));

  const hasIntegrations = (data?.integrations?.length || 0) > 0;

  return (
    <div className="space-y-8">
      {/* Toast notification */}
      {toast && (
        <ConnectionSuccessToast
          type={toast.type}
          message={toast.message}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Sync Progress Banner */}
      <SyncProgressBanner syncStatus={syncStatus} />

      {/* Header */}
      <SectionHeader
        title="Integrations"
        description="Connect your e-commerce stores to sync products and push price updates automatically."
      />

      {/* Diagnostic Panel — only shown when integrations exist */}
      {hasIntegrations && <DiagnosticPanel />}

      {/* Loading state */}
      {isLoading && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-48 animate-pulse rounded-lg border border-gray-200 bg-gray-50"
            />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-800">
            Failed to load integrations. Please try again.
          </p>
        </div>
      )}

      {/* Content */}
      {!isLoading && !error && (
        <>
          {/* Connected integrations */}
          {hasIntegrations && (
            <section>
              <h2 className="mb-4 text-lg font-medium text-gray-900">
                Connected Stores
              </h2>
              <IntegrationsList integrations={data?.integrations || []} />
            </section>
          )}

          {/* Available platforms to connect */}
          {availablePlatforms.length > 0 && (
            <section>
              <h2 className="mb-4 text-lg font-medium text-gray-900">
                {hasIntegrations ? 'Add Another Store' : 'Connect a Store'}
              </h2>
              {!hasIntegrations && (
                <p className="mb-4 text-sm text-gray-500">
                  Connect your Shopify or WooCommerce store to sync products and enable AI-powered pricing.
                </p>
              )}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {availablePlatforms.map((platform) => (
                  <ConnectPlatformCard
                    key={platform}
                    platform={platform}
                    config={PLATFORM_CONFIGS[platform]}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Empty state - no integrations and no available platforms */}
          {!hasIntegrations && availablePlatforms.length === 0 && (
            <IntegrationsEmptyState />
          )}
        </>
      )}
    </div>
  );
}
