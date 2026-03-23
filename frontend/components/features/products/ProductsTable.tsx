// components/features/products/ProductsTable.tsx
'use client';

import { Package, AlertTriangle, RefreshCw, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ProductRow } from './ProductRow';
import { ProductCard } from './ProductCard';
import type { Product } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type SortField = 'name' | 'category' | 'base_price' | 'current_price' | 'status';
export type SortOrder = 'asc' | 'desc';

export interface SortConfig {
  field: SortField | null;
  order: SortOrder;
}

interface ProductsTableProps {
  products: Product[];
  isLoading: boolean;
  error: Error | null;
  emptyMessage?: string;
  onPriceSuggestion: (product: Product) => void;
  onDelete: (product: Product) => void;
  onRetry?: () => void;
  // Sorting props
  sortConfig?: SortConfig;
  onSort?: (field: SortField) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
    </div>
  );
}

// Mobile loading skeleton
function MobileLoadingState() {
  return (
    <div className="space-y-4">
      {[1, 2, 3].map((i) => (
        <Card key={i} className="p-4 animate-pulse">
          <div className="flex gap-3">
            <div className="w-16 h-16 bg-gray-200 rounded-lg" />
            <div className="flex-1">
              <div className="h-4 bg-gray-200 rounded w-3/4 mb-2" />
              <div className="h-3 bg-gray-200 rounded w-1/2" />
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div className="h-8 bg-gray-200 rounded" />
            <div className="h-8 bg-gray-200 rounded" />
          </div>
        </Card>
      ))}
    </div>
  );
}

interface ErrorStateProps {
  onRetry?: () => void;
  errorMessage?: string;
}

function ErrorState({ onRetry, errorMessage }: ErrorStateProps) {
  return (
    <div className="text-center py-20">
      <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-3" />
      <p className="text-gray-600 font-medium">Failed to load products</p>
      <p className="text-sm text-gray-500 mt-1">
        {errorMessage || 'Something went wrong. Please try again.'}
      </p>
      {onRetry && (
        <Button
          variant="secondary"
          onClick={onRetry}
          className="mt-4"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Try Again
        </Button>
      )}
    </div>
  );
}

interface EmptyStateProps {
  message: string;
}

function EmptyState({ message }: EmptyStateProps) {
  return (
    <div className="text-center py-20">
      <Package className="w-12 h-12 text-gray-300 mx-auto mb-3" />
      <p className="text-gray-600">No products found</p>
      <p className="text-sm text-gray-500 mt-1">{message}</p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Sortable Table Header
// ─────────────────────────────────────────────────────────────────────────────

interface ColumnConfig {
  key: string;
  label: string;
  sortField?: SortField;
  tooltip?: string;
}

const columns: ColumnConfig[] = [
  { key: 'product', label: 'Product', sortField: 'name' },
  { key: 'category', label: 'Category', sortField: 'category' },
  { key: 'base_price', label: 'Base Price', sortField: 'base_price' },
  { 
    key: 'current_price', 
    label: 'SSP Price',
    sortField: 'current_price',
    tooltip: 'Price set by SSP auto-pricing (may differ from your store until synced)'
  },
  { key: 'auto_pricing', label: 'Auto-Pricing' },
  { key: 'status', label: 'Status', sortField: 'status' },
  { key: 'actions', label: 'Actions' },
];

interface SortIndicatorProps {
  field: SortField;
  sortConfig?: SortConfig;
}

function SortIndicator({ field, sortConfig }: SortIndicatorProps) {
  if (!sortConfig || sortConfig.field !== field) {
    return <ChevronsUpDown className="w-4 h-4 text-gray-400" />;
  }
  
  return sortConfig.order === 'asc' 
    ? <ChevronUp className="w-4 h-4 text-blue-600" />
    : <ChevronDown className="w-4 h-4 text-blue-600" />;
}

interface TableHeaderProps {
  sortConfig?: SortConfig;
  onSort?: (field: SortField) => void;
}

function TableHeader({ sortConfig, onSort }: TableHeaderProps) {
  return (
    <thead className="bg-gray-50 border-b">
      <tr>
        {columns.map((column) => {
          const isSortable = !!column.sortField && !!onSort;
          const isActive = sortConfig?.field === column.sortField;
          
          return (
            <th
              key={column.key}
              className={`px-6 py-3 text-left text-xs font-medium uppercase tracking-wider ${
                isSortable 
                  ? 'cursor-pointer hover:bg-gray-100 select-none transition-colors' 
                  : ''
              } ${isActive ? 'text-blue-600 bg-blue-50' : 'text-gray-500'}`}
              onClick={() => {
                if (isSortable && column.sortField) {
                  onSort(column.sortField);
                }
              }}
              title={column.tooltip}
            >
              <div className="flex items-center gap-1">
                <span>{column.label}</span>
                {column.tooltip && (
                  <span className="text-gray-400 text-[10px] normal-case font-normal">ⓘ</span>
                )}
                {isSortable && column.sortField && (
                  <SortIndicator field={column.sortField} sortConfig={sortConfig} />
                )}
              </div>
            </th>
          );
        })}
      </tr>
    </thead>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Mobile Sort Dropdown
// ─────────────────────────────────────────────────────────────────────────────

interface MobileSortProps {
  sortConfig?: SortConfig;
  onSort?: (field: SortField) => void;
}

function MobileSort({ sortConfig, onSort }: MobileSortProps) {
  if (!onSort) return null;
  
  const sortableColumns = columns.filter(c => c.sortField);
  
  return (
    <div className="flex items-center gap-2 mb-4">
      <span className="text-sm text-gray-500">Sort by:</span>
      <select
        value={sortConfig?.field || ''}
        onChange={(e) => {
          const value = e.target.value;
          if (value && sortableColumns.some(c => c.sortField === value)) {
            onSort(value as SortField);
          }
        }}
        className="text-sm border border-gray-300 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="">Default</option>
        {sortableColumns.map((col) => (
          <option key={col.key} value={col.sortField}>
            {col.label} {sortConfig?.field === col.sortField ? (sortConfig?.order === 'asc' ? '↑' : '↓') : ''}
          </option>
        ))}
      </select>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function ProductsTable({
  products,
  isLoading,
  error,
  emptyMessage = 'Add your first product to get started',
  onPriceSuggestion,
  onDelete,
  onRetry,
  sortConfig,
  onSort,
}: ProductsTableProps) {
  // Loading state
  if (isLoading) {
    return (
      <>
        {/* Desktop loading */}
        <Card className="overflow-visible hidden md:block">
          <LoadingState />
        </Card>
        {/* Mobile loading */}
        <div className="md:hidden">
          <MobileLoadingState />
        </div>
      </>
    );
  }

  // Error state
  if (error) {
    return (
      <Card className="overflow-visible">
        <ErrorState 
          onRetry={onRetry} 
          errorMessage={error.message}
        />
      </Card>
    );
  }

  // Empty state
  if (products.length === 0) {
    return (
      <Card className="overflow-visible">
        <EmptyState message={emptyMessage} />
      </Card>
    );
  }

  // Data view - responsive
  return (
    <>
      {/* Mobile Card View (< md) */}
      <div className="md:hidden">
        <MobileSort sortConfig={sortConfig} onSort={onSort} />
        <div className="space-y-4">
          {products.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              onPriceSuggestion={onPriceSuggestion}
              onDelete={onDelete}
            />
          ))}
        </div>
      </div>

      {/* Desktop Table View (≥ md) */}
      <Card className="overflow-visible hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full">
            <TableHeader sortConfig={sortConfig} onSort={onSort} />
            <tbody className="divide-y divide-gray-200">
              {products.map((product) => (
                <ProductRow
                  key={product.id}
                  product={product}
                  onPriceSuggestion={onPriceSuggestion}
                  onDelete={onDelete}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

export default ProductsTable;



