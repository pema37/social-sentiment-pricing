// frontend/components/features/integrations/sync-progress-banner.tsx
/**
 * Sync Progress Banner - FIXED VERSION
 * 
 * Uses only Tailwind CSS - no shadcn Badge or Progress components.
 * This avoids the TypeScript errors.
 */

'use client';

import { Loader2, Info, AlertCircle } from 'lucide-react';

interface SyncStatusData {
  integrations: Array<{
    integration_id: string;
    platform: string;
    store_name: string | null;
    sync_status: string;
    is_syncing: boolean;
  }>;
  any_syncing: boolean;
  message?: string;
}

interface SyncProgressBannerProps {
  syncStatus: SyncStatusData | undefined;
}

export function SyncProgressBanner({ syncStatus }: SyncProgressBannerProps) {
  // Don't render if not syncing or no data
  if (!syncStatus?.any_syncing) {
    return null;
  }

  const syncingIntegrations = syncStatus.integrations.filter(i => i.is_syncing);

  return (
    <div className="rounded-lg border bg-blue-50 border-blue-200 p-4 mb-6">
      <div className="flex items-center gap-3">
        <Loader2 className="h-5 w-5 text-blue-600 animate-spin flex-shrink-0" />
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-blue-900">Sync in progress</span>
            {syncingIntegrations.map(integration => (
              <span 
                key={integration.integration_id}
                className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800 border border-blue-200"
              >
                {integration.store_name || integration.platform}
              </span>
            ))}
          </div>
          
          <p className="text-xs text-blue-700 mt-1">
            You can navigate away safely. We&apos;ll notify you when complete.
          </p>
        </div>
        
        <div className="flex items-center gap-1 text-xs text-blue-600 bg-white/60 rounded px-2 py-1 flex-shrink-0">
          <Info className="h-3 w-3" />
          <span>Background sync</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Sync status badge for integration cards
 */
interface SyncStatusBadgeProps {
  status: 'idle' | 'syncing' | 'error' | string;
}

export function SyncStatusBadge({ status }: SyncStatusBadgeProps) {
  if (status === 'syncing') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700 border border-blue-200">
        <Loader2 className="h-3 w-3 animate-spin" />
        Syncing
      </span>
    );
  }
  
  if (status === 'error') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 border border-red-200">
        <AlertCircle className="h-3 w-3" />
        Error
      </span>
    );
  }
  
  return null;
}

export default SyncProgressBanner;



