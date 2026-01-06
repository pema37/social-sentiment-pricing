'use client';

/**
 * LinkedProducts Component
 * 
 * Displays a table of products linked to an integration.
 * Shows external product info, prices, sync status, and last sync times.
 * 
 * Supports:
 * - Pagination
 * - Search/filter (optional)
 * - Enable/disable sync per product
 * - View product details
 */

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { useProductLinks, useDeleteProductLink } from '@/lib/hooks/use-integrations';
import { formatRelativeTime } from '@/lib/utils';
import type { ProductLink } from '@/types/integration';

// ==================== Types ====================

interface LinkedProductsProps {
  /** Integration ID to show products for */
  integrationId: string;
  /** Maximum items to show (0 = all) */
  limit?: number;
  /** Show search input */
  showSearch?: boolean;
  /** Show actions column */
  showActions?: boolean;
  /** Compact mode for embedding */
  compact?: boolean;
}

// ==================== Main Component ====================

export function LinkedProducts({
  integrationId,
  limit = 0,
  showSearch = false,
  showActions = true,
  compact = false,
}: LinkedProductsProps) {
  const { data, isLoading, error } = useProductLinks(integrationId);
  const deleteLink = useDeleteProductLink();
  
  const [searchQuery, setSearchQuery] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // Filter products by search query
  const filteredProducts = useMemo(() => {
    if (!data?.links) return [];
    
    let filtered = data.links;
    
    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (link) =>
          link.external_product_id.toLowerCase().includes(query) ||
          link.external_variant_id?.toLowerCase().includes(query)
      );
    }
    
    // Apply limit
    if (limit > 0) {
      filtered = filtered.slice(0, limit);
    }
    
    return filtered;
  }, [data?.links, searchQuery, limit]);

  // Handle unlink product
  const handleUnlink = (linkId: string) => {
    deleteLink.mutate(
      { integrationId, linkId },
      {
        onSuccess: () => setConfirmDelete(null),
      }
    );
  };

  // Loading state
  if (isLoading) {
    return <LoadingSkeleton compact={compact} />;
  }

  // Error state
  if (error) {
    return (
      <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
        Failed to load linked products.
      </div>
    );
  }

  // Empty state
  if (!data?.links || data.links.length === 0) {
    return (
      <EmptyState compact={compact} />
    );
  }

  return (
    <div className={compact ? '' : 'rounded-lg border border-gray-200 bg-white'}>
      {/* Header with search */}
      {!compact && (
        <div className="flex flex-col gap-3 border-b border-gray-200 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-base font-medium text-gray-900">
              Linked Products
            </h3>
            <p className="text-sm text-gray-500">
              {data.total} product{data.total !== 1 ? 's' : ''} synced
            </p>
          </div>
          
          {showSearch && (
            <div className="relative">
              <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                placeholder="Search by ID..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full rounded-md border border-gray-300 py-1.5 pl-9 pr-3 text-sm placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 sm:w-64"
              />
            </div>
          )}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className={compact ? 'sr-only' : 'bg-gray-50'}>
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                External ID
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Price
              </th>
              {!compact && (
                <>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Compare At
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Last Pull
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Last Push
                  </th>
                </>
              )}
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                Status
              </th>
              {showActions && !compact && (
                <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {filteredProducts.map((link) => (
              <ProductRow
                key={link.id}
                link={link}
                compact={compact}
                showActions={showActions}
                isDeleting={deleteLink.isPending && confirmDelete === link.id}
                confirmDelete={confirmDelete === link.id}
                onDeleteClick={() => setConfirmDelete(link.id)}
                onDeleteConfirm={() => handleUnlink(link.id)}
                onDeleteCancel={() => setConfirmDelete(null)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Show more link */}
      {limit > 0 && data.total > limit && (
        <div className="border-t border-gray-200 p-3 text-center">
          <Link
            href={`/integrations/${integrationId}`}
            className="text-sm text-indigo-600 hover:text-indigo-500"
          >
            View all {data.total} products →
          </Link>
        </div>
      )}

      {/* Pagination info */}
      {!compact && limit === 0 && filteredProducts.length < data.total && (
        <div className="border-t border-gray-200 p-3 text-center text-sm text-gray-500">
          Showing {filteredProducts.length} of {data.total} products
        </div>
      )}
    </div>
  );
}

// ==================== Product Row ====================

interface ProductRowProps {
  link: ProductLink;
  compact: boolean;
  showActions: boolean;
  isDeleting: boolean;
  confirmDelete: boolean;
  onDeleteClick: () => void;
  onDeleteConfirm: () => void;
  onDeleteCancel: () => void;
}

function ProductRow({
  link,
  compact,
  showActions,
  isDeleting,
  confirmDelete,
  onDeleteClick,
  onDeleteConfirm,
  onDeleteCancel,
}: ProductRowProps) {
  return (
    <tr className="hover:bg-gray-50">
      {/* External ID */}
      <td className="whitespace-nowrap px-4 py-3">
        <div>
          <p className="font-mono text-sm text-gray-900">
            {link.external_product_id}
          </p>
          {link.external_variant_id && (
            <p className="font-mono text-xs text-gray-500">
              Variant: {link.external_variant_id}
            </p>
          )}
        </div>
      </td>

      {/* Price */}
      <td className="whitespace-nowrap px-4 py-3 text-sm">
        {link.external_price !== null ? (
          <span className="font-medium text-gray-900">
            ${(Number(link.external_price ?? 0)).toFixed(2)}
          </span>
        ) : (
          <span className="text-gray-400">—</span>
        )}
      </td>

      {/* Compare at price (full mode only) */}
      {!compact && (
        <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
          {link.external_compare_at_price !== null ? (
            <span className="line-through">
              ${(Number(link.external_compare_at_price ?? 0)).toFixed(2)}
            </span>
          ) : (
            '—'
          )}
        </td>
      )}

      {/* Last pull (full mode only) */}
      {!compact && (
        <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
          {link.last_price_pull_at
            ? formatRelativeTime(link.last_price_pull_at)
            : '—'}
        </td>
      )}

      {/* Last push (full mode only) */}
      {!compact && (
        <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
          {link.last_price_push_at
            ? formatRelativeTime(link.last_price_push_at)
            : '—'}
        </td>
      )}

      {/* Sync status */}
      <td className="whitespace-nowrap px-4 py-3">
        {link.sync_enabled ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
            <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
            Synced
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
            <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
            Disabled
          </span>
        )}
      </td>

      {/* Actions (full mode only) */}
      {showActions && !compact && (
        <td className="whitespace-nowrap px-4 py-3 text-right text-sm">
          {confirmDelete ? (
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={onDeleteConfirm}
                disabled={isDeleting}
                className="text-red-600 hover:text-red-700 disabled:opacity-50"
              >
                {isDeleting ? 'Removing...' : 'Confirm'}
              </button>
              <button
                onClick={onDeleteCancel}
                disabled={isDeleting}
                className="text-gray-500 hover:text-gray-700"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-end gap-3">
              <Link
                href={`/products/${link.product_id}`}
                className="text-indigo-600 hover:text-indigo-500"
              >
                View
              </Link>
              <button
                onClick={onDeleteClick}
                className="text-gray-400 hover:text-red-600"
              >
                Unlink
              </button>
            </div>
          )}
        </td>
      )}
    </tr>
  );
}

// ==================== Empty State ====================

function EmptyState({ compact }: { compact: boolean }) {
  if (compact) {
    return (
      <p className="py-4 text-center text-sm text-gray-500">
        No products synced yet.
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
      <PackageIcon className="mx-auto h-10 w-10 text-gray-400" />
      <h3 className="mt-2 text-sm font-medium text-gray-900">
        No linked products
      </h3>
      <p className="mt-1 text-sm text-gray-500">
        Products will appear here after syncing with your store.
      </p>
    </div>
  );
}

// ==================== Loading Skeleton ====================

function LoadingSkeleton({ compact }: { compact: boolean }) {
  const rows = compact ? 3 : 5;
  
  return (
    <div className={compact ? '' : 'rounded-lg border border-gray-200 bg-white p-4'}>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="h-4 w-24 animate-pulse rounded bg-gray-200" />
            <div className="h-4 w-16 animate-pulse rounded bg-gray-200" />
            <div className="h-4 w-20 animate-pulse rounded bg-gray-200" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ==================== Icons ====================

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

function PackageIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
    </svg>
  );
}

// ==================== Export ====================

export default LinkedProducts;
