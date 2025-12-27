// components/features/products/ProductsTable.tsx
'use client';

import { Package, AlertTriangle, RefreshCw } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ProductRow } from './ProductRow';
import type { Product } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ProductsTableProps {
  products: Product[];
  isLoading: boolean;
  error: Error | null;
  emptyMessage?: string;
  onPriceSuggestion: (product: Product) => void;
  onDelete: (product: Product) => void;
  onRetry?: () => void;  // ADDED: Optional retry callback
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

// FIXED: Error state now accepts onRetry callback
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

function TableHeader() {
  const columns = [
    'Product',
    'Category',
    'Base Price',
    'Current Price',
    'Auto-Pricing',
    'Status',
    'Actions',
  ];

  return (
    <thead className="bg-gray-50 border-b">
      <tr>
        {columns.map((column) => (
          <th
            key={column}
            className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
          >
            {column}
          </th>
        ))}
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
  onRetry,  // ADDED
}: ProductsTableProps) {
  // Loading state
  if (isLoading) {
    return (
      <Card className="overflow-visible">
        <LoadingState />
      </Card>
    );
  }

  // Error state - FIXED: Now shows retry button
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
          <TableHeader />
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
