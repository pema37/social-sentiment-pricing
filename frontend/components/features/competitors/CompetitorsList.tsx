// Competitors list component
'use client';

import { CompetitorCard } from './CompetitorCard';
import type { Competitor } from '@/types';

interface CompetitorsListProps {
  competitors: Competitor[];
  isLoading?: boolean;
  error?: Error | null;
  onEdit: (competitor: Competitor) => void;
  onAdd: () => void;
  onRetry?: () => void;
}

export function CompetitorsList({
  competitors,
  isLoading,
  error,
  onEdit,
  onAdd,
  onRetry,
}: CompetitorsListProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
            <div className="h-5 w-1/3 bg-gray-200 rounded mb-2" />
            <div className="h-4 w-2/3 bg-gray-100 rounded mb-2" />
            <div className="h-4 w-1/4 bg-gray-100 rounded" />
          </div>
        ))}
      </div>
    );
  }

  // FIX: Only show error if there's NO data to display
  // React Query can have both stale data AND an error from a failed refetch
  if (error && competitors.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
        <p className="text-red-600 font-medium">Failed to load competitors</p>
        <p className="text-sm text-gray-500 mt-1">{error.message}</p>
      </div>
    );
  }

  if (competitors.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
        <div className="text-4xl mb-3">🏪</div>
        <p className="text-gray-600 font-medium">No competitors yet</p>
        <p className="text-sm text-gray-500 mt-1">
          Add competitors to track their pricing and stay ahead.
        </p>
        <button
          onClick={onAdd}
          className="mt-4 px-4 py-2 text-sm font-medium text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50"
        >
          Add Your First Competitor
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Show warning banner if there's an error but we have stale data */}
      {error && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex items-center gap-2">
          <span className="text-yellow-600 text-sm">
            ⚠️ Failed to refresh data. Showing cached results.
          </span>
          {onRetry && (
            <button
              onClick={onRetry}
              className="text-yellow-700 text-sm underline hover:no-underline ml-auto"
            >
              Retry
            </button>
          )}
        </div>
      )}
      
      {competitors.map((competitor) => (
        <CompetitorCard
          key={competitor.id}
          competitor={competitor}
          onEdit={onEdit}
        />
      ))}
    </div>
  );
}
