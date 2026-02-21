// app/(dashboard)/products/page.tsx
'use client';

import { useState, useMemo } from 'react';
import Link from 'next/link';
import { Plus, Search, Upload } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Pagination } from '@/components/ui/Pagination';
import {
  ProductsTable,
  PriceSuggestionModal,
  DeleteProductModal,
  ImportCSVModal,
} from '@/components/features/products';
import type { SortField, SortOrder, SortConfig } from '@/components/features/products/ProductsTable';
import { useProducts, useDeleteProduct, type Product } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Sorting Helper
// ─────────────────────────────────────────────────────────────────────────────

function safeNumber(value: unknown, defaultValue = 0): number {
  if (value == null) return defaultValue;
  const num = Number(value);
  return isNaN(num) ? defaultValue : num;
}

function sortProducts(products: Product[], sortConfig: SortConfig): Product[] {
  if (!sortConfig.field) return products;
  
  const sorted = [...products].sort((a, b) => {
    let comparison = 0;
    
    switch (sortConfig.field) {
      case 'name':
        comparison = a.name.localeCompare(b.name);
        break;
      case 'category':
        const catA = a.category || '';
        const catB = b.category || '';
        comparison = catA.localeCompare(catB);
        break;
      case 'base_price':
        comparison = safeNumber(a.base_price) - safeNumber(b.base_price);
        break;
      case 'current_price':
        comparison = safeNumber(a.current_price) - safeNumber(b.current_price);
        break;
      case 'status':
        // Active products first when ascending
        comparison = (a.is_active === b.is_active) ? 0 : a.is_active ? -1 : 1;
        break;
      default:
        comparison = 0;
    }
    
    return sortConfig.order === 'asc' ? comparison : -comparison;
  });
  
  return sorted;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export default function ProductsPage() {
  // Pagination & Search
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const pageSize = 10;

  // Sorting state (default: by name ascending, like WooCommerce)
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    field: 'name',
    order: 'asc',
  });

  // Modal states
  const [suggestionProduct, setSuggestionProduct] = useState<Product | null>(null);
  const [deleteProduct, setDeleteProduct] = useState<Product | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);

  // Data fetching
  const { data, isLoading, error, refetch } = useProducts({ page, page_size: pageSize });
  const deleteProductMutation = useDeleteProduct();

  // Filter products by search (client-side)
  const filteredProducts = useMemo(() => {
    return data?.items.filter(
      (product) =>
        product.name.toLowerCase().includes(search.toLowerCase()) ||
        product.sku?.toLowerCase().includes(search.toLowerCase())
    ) ?? [];
  }, [data?.items, search]);

  // Sort products (client-side)
  const sortedProducts = useMemo(() => {
    return sortProducts(filteredProducts, sortConfig);
  }, [filteredProducts, sortConfig]);

  // Handle sort toggle
  const handleSort = (field: SortField) => {
    setSortConfig((prev) => {
      // If clicking same field, toggle order
      if (prev.field === field) {
        return {
          field,
          order: prev.order === 'asc' ? 'desc' : 'asc',
        };
      }
      // New field: default to ascending
      return {
        field,
        order: 'asc',
      };
    });
  };

  // Delete handler
  const handleDeleteConfirm = () => {
    if (deleteProduct) {
      setDeleteProduct(null);
    }
  };

  const handleImportSuccess = () => {
    setShowImportModal(false);
    refetch();
  };

  const handleRetry = () => {
    refetch();
  };

  return (
    <div className="space-y-6">
      {/* Header - Responsive */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Products</h1>
          <p className="text-gray-500 mt-1">Manage your products and pricing</p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="secondary" 
            onClick={() => setShowImportModal(true)}
            className="flex-1 sm:flex-none"
          >
            <Upload className="w-4 h-4 sm:mr-2" />
            <span className="hidden sm:inline">Import CSV</span>
          </Button>
          <Link href="/products/new" className="flex-1 sm:flex-none">
            <Button className="w-full">
              <Plus className="w-4 h-4 sm:mr-2" />
              <span className="hidden sm:inline">Add Product</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* Search & Sort Info */}
      <Card className="p-4">
        <div className="flex items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <Input
              placeholder="Search products..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
            />
          </div>
          {/* Sort indicator badge */}
          {sortConfig.field && (
            <div className="text-sm text-gray-500 flex items-center gap-1">
              <span>Sorted by:</span>
              <span className="font-medium text-gray-700 capitalize">
                {sortConfig.field === 'current_price' ? 'SSP Price' : sortConfig.field.replace('_', ' ')}
              </span>
              <span className="text-gray-400">
                ({sortConfig.order === 'asc' ? '↑' : '↓'})
              </span>
            </div>
          )}
        </div>
      </Card>

      {/* Table with sorting */}
      <ProductsTable
        products={sortedProducts}
        isLoading={isLoading}
        error={error}
        emptyMessage={search ? 'Try a different search term' : 'Add your first product to get started'}
        onPriceSuggestion={setSuggestionProduct}
        onDelete={setDeleteProduct}
        onRetry={handleRetry}
        sortConfig={sortConfig}
        onSort={handleSort}
      />

      {/* Pagination */}
      {data && (
        <Pagination
          page={page}
          totalPages={data.pages}
          total={data.total}
          pageSize={pageSize}
          onPageChange={setPage}
        />
      )}

      {/* Modals */}
      {suggestionProduct && (
        <PriceSuggestionModal
          product={suggestionProduct}
          onClose={() => setSuggestionProduct(null)}
        />
      )}

      {deleteProduct && (
        <DeleteProductModal
          productId={deleteProduct.id}
          productName={deleteProduct.name}
          isOpen={true}
          onClose={() => setDeleteProduct(null)}
          onSuccess={handleDeleteConfirm}
        />
      )}

      {showImportModal && (
        <ImportCSVModal
          isOpen={showImportModal}
          onClose={() => setShowImportModal(false)}
          onSuccess={handleImportSuccess}
        />
      )}
    </div>
  );
}




