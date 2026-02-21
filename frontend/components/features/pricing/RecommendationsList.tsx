// Recommendations List Component
// List container with filtering, empty states, and loading skeleton

'use client';

import { useMemo } from 'react';
import { Inbox, Filter } from 'lucide-react';
import { RecommendationCard } from './RecommendationCard';
import { cn } from '@/lib/utils';
import type { PriceRecommendation, RecommendationStatus } from '@/types';

// ============================================
// TYPES
// ============================================

interface RecommendationsListProps {
  recommendations: PriceRecommendation[];
  /** Map of product IDs to product names */
  productNames: Record<string, string>;
  /** Map of product IDs to SKUs */
  productSkus?: Record<string, string | null>;
  /** Current filter status */
  filterStatus?: RecommendationStatus | 'all';
  /** Callback when filter changes */
  onFilterChange?: (status: RecommendationStatus | 'all') => void;
  /** Callback when approve is clicked */
  onApprove?: (id: string) => void;
  /** Callback when reject is clicked */
  onReject?: (id: string) => void;
  /** Callback when view details is clicked */
  onView?: (id: string) => void;
  /** Loading state for actions */
  actionLoadingId?: string;
  /** Empty state message override */
  emptyMessage?: string;
  /** Show filter tabs */
  showFilters?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================
// FILTER CONFIG
// ============================================

const filterTabs: { value: RecommendationStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'applied', label: 'Applied' },
  { value: 'rejected', label: 'Rejected' },
  { value: 'expired', label: 'Expired' },
];

// ============================================
// EMPTY STATE
// ============================================

function EmptyState({
  filterStatus,
  customMessage,
}: {
  filterStatus?: RecommendationStatus | 'all';
  customMessage?: string;
}) {
  const getMessage = () => {
    if (customMessage) return customMessage;

    switch (filterStatus) {
      case 'pending':
        return 'No pending recommendations. Your prices are up to date!';
      case 'approved':
        return 'No approved recommendations yet.';
      case 'applied':
        return 'No recommendations have been applied yet.';
      case 'rejected':
        return 'No rejected recommendations.';
      case 'expired':
        return 'No expired recommendations.';
      default:
        return 'No price recommendations found. They will appear here when the pricing engine generates suggestions.';
    }
  };

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mb-4">
        <Inbox className="h-6 w-6 text-gray-400" />
      </div>
      <h3 className="text-sm font-medium text-gray-900 mb-1">
        No Recommendations
      </h3>
      <p className="text-sm text-gray-500 max-w-sm">{getMessage()}</p>
    </div>
  );
}

// ============================================
// LOADING SKELETON
// ============================================

export function RecommendationsListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-white border border-gray-200 rounded-xl p-4 animate-pulse"
        >
          {/* Header */}
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="h-5 w-40 bg-gray-200 rounded mb-2" />
              <div className="h-4 w-24 bg-gray-100 rounded" />
            </div>
            <div className="h-6 w-20 bg-gray-200 rounded-full" />
          </div>

          {/* Price */}
          <div className="flex items-center gap-4 mb-4">
            <div className="flex-1">
              <div className="h-3 w-16 bg-gray-100 rounded mb-2" />
              <div className="h-6 w-20 bg-gray-200 rounded" />
            </div>
            <div className="h-5 w-5 bg-gray-200 rounded" />
            <div className="flex-1 text-right">
              <div className="h-3 w-16 bg-gray-100 rounded mb-2 ml-auto" />
              <div className="h-6 w-20 bg-gray-200 rounded ml-auto" />
            </div>
          </div>

          {/* Confidence */}
          <div className="h-10 bg-gray-50 rounded-lg mb-3" />

          {/* Reasoning */}
          <div className="h-4 w-full bg-gray-100 rounded mb-2" />
          <div className="h-4 w-3/4 bg-gray-100 rounded mb-4" />

          {/* Footer */}
          <div className="flex items-center justify-between pt-3 border-t border-gray-100">
            <div className="h-4 w-32 bg-gray-100 rounded" />
            <div className="flex gap-2">
              <div className="h-8 w-16 bg-gray-200 rounded-lg" />
              <div className="h-8 w-20 bg-gray-200 rounded-lg" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ============================================
// FILTER TABS
// ============================================

function FilterTabs({
  value,
  onChange,
  counts,
}: {
  value: RecommendationStatus | 'all';
  onChange: (status: RecommendationStatus | 'all') => void;
  counts: Record<string, number>;
}) {
  return (
    <div className="flex items-center gap-1 p-1 bg-gray-100 rounded-lg overflow-x-auto scrollbar-hide">
      {filterTabs.map((tab) => {
        const count = counts[tab.value] ?? 0;
        const isActive = value === tab.value;

        return (
          <button
            key={tab.value}
            onClick={() => onChange(tab.value)}
            className={cn(
              'shrink-0 px-2.5 sm:px-3 py-1.5 text-xs sm:text-sm font-medium rounded-lg whitespace-nowrap transition-colors',
              isActive
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            )}
          >
            {tab.label}
            {count > 0 && (
              <span
                className={cn(
                  'ml-1 sm:ml-1.5 px-1.5 py-0.5 text-xs rounded-full',
                  isActive ? 'bg-gray-100' : 'bg-gray-200'
                )}
              >
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// ============================================
// MAIN COMPONENT
// ============================================

export function RecommendationsList({
  recommendations,
  productNames,
  productSkus,
  filterStatus = 'all',
  onFilterChange,
  onApprove,
  onReject,
  onView,
  actionLoadingId,
  emptyMessage,
  showFilters = true,
  className,
}: RecommendationsListProps) {
  // Calculate counts by status
  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { all: recommendations.length };

    recommendations.forEach((rec) => {
      counts[rec.status] = (counts[rec.status] || 0) + 1;
    });

    return counts;
  }, [recommendations]);

  // Filter recommendations based on status
  const filteredRecommendations = useMemo(() => {
    if (filterStatus === 'all') return recommendations;
    return recommendations.filter((rec) => rec.status === filterStatus);
  }, [recommendations, filterStatus]);

  return (
    <div className={cn('space-y-4', className)}>
      {/* Filter Tabs - Scrollable on mobile */}
      {showFilters && onFilterChange && (
        <div className="flex items-center gap-2 sm:gap-3 overflow-x-auto pb-1">
          <Filter className="h-4 w-4 text-gray-400 shrink-0" />
          <FilterTabs
            value={filterStatus}
            onChange={onFilterChange}
            counts={statusCounts}
          />
        </div>
      )}

      {/* Recommendations */}
      {filteredRecommendations.length === 0 ? (
        <EmptyState filterStatus={filterStatus} customMessage={emptyMessage} />
      ) : (
        <div className="space-y-4">
          {filteredRecommendations.map((recommendation) => (
            <RecommendationCard
              key={recommendation.id}
              recommendation={recommendation}
              productName={productNames[recommendation.product_id] || 'Unknown Product'}
              productSku={productSkus?.[recommendation.product_id]}
              onApprove={onApprove}
              onReject={onReject}
              onView={onView}
              isLoading={actionLoadingId === recommendation.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
