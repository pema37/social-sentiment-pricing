// components/features/products/ProductsTable.tsx
'use client';

import { Package, AlertTriangle, RefreshCw, ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ProductRow } from './ProductRow';
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
    label: 'SSP Price',  // FIXED: Changed from "Current Price" to "SSP Price"
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
      <Card className="overflow-visible">
        <LoadingState />
      </Card>
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

  // Table with data
  return (
    <Card className="overflow-visible">
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
  );
}

export default ProductsTable;



