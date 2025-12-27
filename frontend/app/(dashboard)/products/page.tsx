// app/(dashboard)/products/page.tsx
'use client';

import { useState } from 'react';
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
import { useProducts, useDeleteProduct, type Product } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export default function ProductsPage() {
  // Pagination & Search
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const pageSize = 10;

  // Modal states
  const [suggestionProduct, setSuggestionProduct] = useState<Product | null>(null);
  const [deleteProduct, setDeleteProduct] = useState<Product | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);

  // Data fetching
  const { data, isLoading, error, refetch } = useProducts({ page, page_size: pageSize });
  const deleteProductMutation = useDeleteProduct();

  // Filter products by search (client-side)
  const filteredProducts =
    data?.items.filter(
      (product) =>
        product.name.toLowerCase().includes(search.toLowerCase()) ||
        product.sku?.toLowerCase().includes(search.toLowerCase())
    ) ?? [];

  // FIXED: Proper delete handler that doesn't cause double-toast
  const handleDeleteConfirm = () => {
    if (deleteProduct) {
      setDeleteProduct(null); // Close modal immediately
    }
  };

  const handleImportSuccess = () => {
    setShowImportModal(false);
    refetch();
  };

  // ADDED: Retry handler for error state
  const handleRetry = () => {
    refetch();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Products</h1>
          <p className="text-gray-500 mt-1">Manage your products and pricing</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setShowImportModal(true)}>
            <Upload className="w-4 h-4 mr-2" />
            Import CSV
          </Button>
          <Link href="/products/new">
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              Add Product
            </Button>
          </Link>
        </div>
      </div>

      {/* Search */}
      <Card className="p-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <Input
            placeholder="Search products..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>
      </Card>

      {/* Table - FIXED: Added onRetry prop */}
      <ProductsTable
        products={filteredProducts}
        isLoading={isLoading}
        error={error}
        emptyMessage={search ? 'Try a different search term' : 'Add your first product to get started'}
        onPriceSuggestion={setSuggestionProduct}
        onDelete={setDeleteProduct}
        onRetry={handleRetry}
      />

      {/* Pagination */}
      {data && (
        <Pagination
          page={page}
          totalPages={data.total_pages}
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
