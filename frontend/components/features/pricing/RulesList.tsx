// Rules List Component
// List container with filtering, empty states, and loading skeleton

'use client';

import { useMemo } from 'react';
import { Inbox, Filter } from 'lucide-react';
import { RuleCard } from './RuleCard';
import { cn } from '@/lib/utils';
import type { PricingRule, RuleType } from '@/types';

// ============================================
// TYPES
// ============================================

interface RulesListProps {
  /** Competitor ID to name mapping */
  competitorNames?: Record<string, string>;
  rules: PricingRule[];
  /** Product ID to name mapping */
  productNames?: Record<string, string>;
  /** Current filter by rule type */
  filterType?: RuleType | 'all';
  /** Current filter by active status */
  filterActive?: 'all' | 'active' | 'inactive';
  /** Callback when type filter changes */
  onFilterTypeChange?: (type: RuleType | 'all') => void;
  /** Callback when active filter changes */
  onFilterActiveChange?: (status: 'all' | 'active' | 'inactive') => void;
  /** Callback when toggle is clicked */
  onToggle?: (id: string, isActive: boolean) => void;
  /** Callback when edit is clicked */
  onEdit?: (id: string) => void;
  /** Callback when delete is clicked */
  onDelete?: (id: string) => void;
  /** Callback when duplicate is clicked */
  onDuplicate?: (id: string) => void;
  /** Loading state for actions */
  actionLoadingId?: string;
  /** Empty state message override */
  emptyMessage?: string;
  /** Show filter controls */
  showFilters?: boolean;
  /** Additional CSS classes */
  className?: string;
}

// ============================================
// FILTER CONFIG
// ============================================

const typeFilterTabs: { value: RuleType | 'all'; label: string }[] = [
  { value: 'all', label: 'All Types' },
  { value: 'sentiment_threshold', label: 'Sentiment' },
  { value: 'competitor_relative', label: 'Competitor' },
  { value: 'time_based', label: 'Time-Based' },
  { value: 'volume_surge', label: 'Volume' },
  { value: 'viral_detection', label: 'Viral' },
];

const activeFilterTabs: { value: 'all' | 'active' | 'inactive'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
];

// ============================================
// EMPTY STATE
// ============================================

function EmptyState({
  filterType,
  filterActive,
  customMessage,
}: {
  filterType?: RuleType | 'all';
  filterActive?: 'all' | 'active' | 'inactive';
  customMessage?: string;
}) {
  const getMessage = () => {
    if (customMessage) return customMessage;

    if (filterType && filterType !== 'all') {
      return `No ${filterType.replace('_', ' ')} rules found.`;
    }
    if (filterActive === 'active') {
      return 'No active rules. Enable a rule to start automatic pricing.';
    }
    if (filterActive === 'inactive') {
      return 'No inactive rules.';
    }
    return 'No pricing rules yet. Create your first rule to enable automatic pricing.';
  };

  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mb-4">
        <Inbox className="h-6 w-6 text-gray-400" />
      </div>
      <h3 className="text-sm font-medium text-gray-900 mb-1">No Rules</h3>
      <p className="text-sm text-gray-500 max-w-sm">{getMessage()}</p>
    </div>
  );
}

// ============================================
// LOADING SKELETON
// ============================================

export function RulesListSkeleton({ count = 3 }: { count?: number }) {
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
              <div className="h-5 w-48 bg-gray-200 rounded mb-2" />
              <div className="h-4 w-32 bg-gray-100 rounded" />
            </div>
            <div className="h-6 w-24 bg-gray-200 rounded-full" />
          </div>

          {/* Details Grid */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            {[...Array(4)].map((_, j) => (
              <div key={j}>
                <div className="h-3 w-16 bg-gray-100 rounded mb-2" />
                <div className="h-4 w-24 bg-gray-200 rounded" />
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between pt-3 border-t border-gray-100">
            <div className="h-8 w-24 bg-gray-200 rounded-lg" />
            <div className="flex gap-1">
              <div className="h-8 w-8 bg-gray-200 rounded-lg" />
              <div className="h-8 w-8 bg-gray-200 rounded-lg" />
              <div className="h-8 w-8 bg-gray-200 rounded-lg" />
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

function FilterTabs<T extends string>({
  tabs,
  value,
  onChange,
  counts,
}: {
  tabs: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  counts?: Record<string, number>;
}) {
  return (
    <div className="flex items-center gap-1 p-1 bg-gray-100 rounded-lg overflow-x-auto">
      {tabs.map((tab) => {
        const count = counts?.[tab.value];
        const isActive = value === tab.value;

        return (
          <button
            key={tab.value}
            onClick={() => onChange(tab.value)}
            className={cn(
              'px-3 py-1.5 text-sm font-medium rounded-lg whitespace-nowrap transition-colors',
              isActive
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            )}
          >
            {tab.label}
            {count !== undefined && count > 0 && (
              <span
                className={cn(
                  'ml-1.5 px-1.5 py-0.5 text-xs rounded-full',
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
export function RulesList({
  rules,
  productNames = {},
  competitorNames = {},
  filterType = 'all',
  filterActive = 'all',
  onFilterTypeChange,
  onFilterActiveChange,
  onToggle,
  onEdit,
  onDelete,
  onDuplicate,
  actionLoadingId,
  emptyMessage,
  showFilters = true,
  className,
}: RulesListProps) {
  // Calculate counts by type
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = { all: rules.length };
    rules.forEach((rule) => {
      counts[rule.rule_type] = (counts[rule.rule_type] || 0) + 1;
    });
    return counts;
  }, [rules]);

  // Calculate counts by active status
  const activeCounts = useMemo(() => {
    return {
      all: rules.length,
      active: rules.filter((r) => r.is_active).length,
      inactive: rules.filter((r) => !r.is_active).length,
    };
  }, [rules]);

  // Filter rules
  const filteredRules = useMemo(() => {
    let result = rules;

    if (filterType !== 'all') {
      result = result.filter((rule) => rule.rule_type === filterType);
    }

    if (filterActive === 'active') {
      result = result.filter((rule) => rule.is_active);
    } else if (filterActive === 'inactive') {
      result = result.filter((rule) => !rule.is_active);
    }

    // Sort by priority (lower = higher priority)
    return result.sort((a, b) => a.priority - b.priority);
  }, [rules, filterType, filterActive]);

  return (
    <div className={cn('space-y-4', className)}>
      {/* Filters */}
      {showFilters && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-gray-400" />
            <span className="text-sm text-gray-600">Type:</span>
          </div>
          {onFilterTypeChange && (
            <FilterTabs
              tabs={typeFilterTabs}
              value={filterType}
              onChange={onFilterTypeChange}
              counts={typeCounts}
            />
          )}
        </div>
      )}

      {showFilters && onFilterActiveChange && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-600 ml-6">Status:</span>
          <FilterTabs
            tabs={activeFilterTabs}
            value={filterActive}
            onChange={onFilterActiveChange}
            counts={activeCounts}
          />
        </div>
      )}

      {/* Rules */}
      {filteredRules.length === 0 ? (
        <EmptyState
          filterType={filterType}
          filterActive={filterActive}
          customMessage={emptyMessage}
        />
      ) : (
        <div className="space-y-4">
          {filteredRules.map((rule) => (

            <RuleCard
              productNames={productNames}
              competitorNames={competitorNames}
              key={rule.id}
              rule={rule}
              onToggle={onToggle}
              onEdit={onEdit}
              onDelete={onDelete}
              onDuplicate={onDuplicate}
              isLoading={actionLoadingId === rule.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
