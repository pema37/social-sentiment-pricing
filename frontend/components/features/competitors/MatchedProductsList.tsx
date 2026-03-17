// frontend/components/features/competitors/MatchedProductsList.tsx

'use client';

import { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  SlidersHorizontal,
  Package,
  Loader2,
  AlertTriangle,
  CheckCircle,
  Clock,
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { MatchedProductCard } from './MatchedProductCard';
import type { MatchedProduct, CompetitorSearchResponse, MatchStatus } from '@/types';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface MatchedProductsListProps {
  response: CompetitorSearchResponse | null;
  isLoading?: boolean;
  ourPrice?: string | number | null;
  onLinkProduct?: (product: MatchedProduct) => void;
  linkingProductUrl?: string | null;
  linkedUrls?: string[];
}

interface FilterState {
  search: string;
  minConfidence: number;
  hasPrice: boolean;
  inStockOnly: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function getStatusConfig(status: MatchStatus): {
  icon: typeof CheckCircle;
  color: string;
  bgColor: string;
  label: string;
} {
  switch (status) {
    case 'success':
      return {
        icon: CheckCircle,
        color: 'text-green-600',
        bgColor: 'bg-green-50',
        label: 'Search successful',
      };
    case 'cached':
      return {
        icon: Clock,
        color: 'text-blue-600',
        bgColor: 'bg-blue-50',
        label: 'Cached results',
      };
    case 'partial':
      return {
        icon: AlertTriangle,
        color: 'text-yellow-600',
        bgColor: 'bg-yellow-50',
        label: 'Partial results',
      };
    case 'failed':
      return {
        icon: AlertTriangle,
        color: 'text-red-600',
        bgColor: 'bg-red-50',
        label: 'Search failed',
      };
    default:
      return {
        icon: CheckCircle,
        color: 'text-gray-600',
        bgColor: 'bg-gray-50',
        label: 'Unknown status',
      };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function SearchMetadata({ response }: { response: CompetitorSearchResponse }) {
  const statusConfig = getStatusConfig(response.status);
  const StatusIcon = statusConfig.icon;

  return (
    <div className={`rounded-lg p-4 mb-4 ${statusConfig.bgColor}`}>
      <div className="flex items-center justify-between flex-wrap gap-2">
        {/* Status */}
        <div className="flex items-center gap-2">
          <StatusIcon className={`w-5 h-5 ${statusConfig.color}`} />
          <span className={`font-medium ${statusConfig.color}`}>
            {statusConfig.label}
          </span>
          {response.cached && (
            <Badge variant="info" className="text-xs">Cached</Badge>
          )}
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4 text-sm text-gray-600">
          <span>
            <strong>{response.total_found}</strong> results
          </span>
          <span>
            <strong>{response.search_time_ms}</strong>ms
          </span>
          <span>
            Query: <code className="bg-white px-1 rounded">{response.query_used}</code>
          </span>
        </div>
      </div>

      {/* Provider info */}
      <div className="mt-2 flex items-center gap-2 flex-wrap">
        <span className="text-xs text-gray-500">Providers:</span>
        {response.providers_used.map((provider) => (
          <Badge key={provider} variant="default" className="text-xs">
            {provider.replace(/_/g, ' ')}
          </Badge>
        ))}
        {response.providers_failed.length > 0 && (
          <span className="text-xs text-red-500">
            ({response.providers_failed.length} failed)
          </span>
        )}
      </div>
    </div>
  );
}

function FilterBar({
  filters,
  onChange,
  totalCount,
  filteredCount,
}: {
  filters: FilterState;
  onChange: (filters: FilterState) => void;
  totalCount: number;
  filteredCount: number;
}) {
  const [showFilters, setShowFilters] = useState(false);

  return (
    <div className="mb-4 space-y-3">
      {/* Search and toggle */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            type="text"
            placeholder="Filter results by name or merchant..."
            value={filters.search}
            onChange={(e) => onChange({ ...filters, search: e.target.value })}
            className="pl-10"
          />
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setShowFilters(!showFilters)}
        >
          <SlidersHorizontal className="w-4 h-4 mr-1" />
          Filters
        </Button>
      </div>

      {/* Filter count indicator */}
      {filteredCount !== totalCount && (
        <p className="text-sm text-gray-500">
          Showing {filteredCount} of {totalCount} results
        </p>
      )}

      {/* Expanded filters */}
      {showFilters && (
        <Card className="p-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Min confidence */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Min Confidence: {Math.round(filters.minConfidence * 100)}%
              </label>
              <input
                type="range"
                min="0"
                max="100"
                value={filters.minConfidence * 100}
                onChange={(e) =>
                  onChange({ ...filters, minConfidence: parseInt(e.target.value) / 100 })
                }
                className="w-full"
              />
            </div>

            {/* Has price */}
            <div className="flex items-center">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filters.hasPrice}
                  onChange={(e) => onChange({ ...filters, hasPrice: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">Has price only</span>
              </label>
            </div>

            {/* In stock only */}
            <div className="flex items-center">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={filters.inStockOnly}
                  onChange={(e) => onChange({ ...filters, inStockOnly: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">In stock only</span>
              </label>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function EmptyState({ hasFilters }: { hasFilters: boolean }) {
  return (
    <div className="text-center py-12">
      <Package className="w-12 h-12 text-gray-400 mx-auto mb-4" />
      <h3 className="text-lg font-medium text-gray-900 mb-1">
        {hasFilters ? 'No matching results' : 'No competitors found'}
      </h3>
      <p className="text-gray-500">
        {hasFilters
          ? 'Try adjusting your filters to see more results.'
          : 'Try searching with different keywords or product name.'}
      </p>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="text-center py-12">
      <Loader2 className="w-8 h-8 text-blue-600 mx-auto mb-4 animate-spin" />
      <h3 className="text-lg font-medium text-gray-900 mb-1">
        Searching for competitors...
      </h3>
      <p className="text-gray-500">
        This may take a few seconds.
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function MatchedProductsList({
  response,
  isLoading = false,
  ourPrice,
  onLinkProduct,
  linkingProductUrl,
  linkedUrls = [],
}: MatchedProductsListProps) {
  // Filter state
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    minConfidence: 0,
    hasPrice: false,
    inStockOnly: false,
  });

  // Filter products
  // eslint-disable-next-line react-hooks/preserve-manual-memoization
  const filteredProducts = useMemo(() => {
    if (!response?.products) return [];

    let filtered = [...response.products];

    // Text search
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter(
        (p) =>
          p.title.toLowerCase().includes(searchLower) ||
          p.merchant.toLowerCase().includes(searchLower) ||
          p.merchant_domain.toLowerCase().includes(searchLower)
      );
    }

    // Min confidence
    if (filters.minConfidence > 0) {
      filtered = filtered.filter((p) => p.confidence_score >= filters.minConfidence);
    }

    // Has price
    if (filters.hasPrice) {
      filtered = filtered.filter((p) => p.price !== null);
    }

    // In stock
    if (filters.inStockOnly) {
      filtered = filtered.filter((p) => p.in_stock);
    }

    // Sort by confidence
    return filtered.sort((a, b) => b.confidence_score - a.confidence_score);
  }, [response?.products, filters]);

  const hasActiveFilters =
    filters.search !== '' ||
    filters.minConfidence > 0 ||
    filters.hasPrice ||
    filters.inStockOnly;

  // Loading state
  if (isLoading) {
    return <LoadingState />;
  }

  // No response yet
  if (!response) {
    return null;
  }

  return (
    <div>
      {/* Search metadata */}
      <SearchMetadata response={response} />

      {/* Filters */}
      {response.products.length > 0 && (
        <FilterBar
          filters={filters}
          onChange={setFilters}
          totalCount={response.products.length}
          filteredCount={filteredProducts.length}
        />
      )}

      {/* Results */}
      {filteredProducts.length === 0 ? (
        <EmptyState hasFilters={hasActiveFilters} />
      ) : (
        <div className="space-y-4">
          {filteredProducts.map((product, index) => (
            <MatchedProductCard
              key={`${product.url}-${index}`}
              product={product}
              ourPrice={ourPrice}
              onLink={onLinkProduct}
              isLinking={linkingProductUrl === product.url}
              isLinked={linkedUrls.includes(product.url)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default MatchedProductsList;



