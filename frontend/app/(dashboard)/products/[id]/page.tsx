// app/(dashboard)/products/[id]/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Edit, Trash2, AlertCircle, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useProduct } from '@/lib/hooks/use-products';
import {
  ProductInfoCard,
  AutoPricingCard,
  PriceSuggestionCard,
  PriceHistoryCard,
  DeleteProductModal,
  KeywordsManager,
} from '@/components/features/products';

// ─────────────────────────────────────────────────────────────────────────────
// Loading Skeleton
// ─────────────────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header skeleton */}
      <div className="flex items-center gap-4">
        <div className="h-10 w-10 bg-gray-200 rounded-lg" />
        <div className="h-8 bg-gray-200 rounded w-48" />
      </div>
      
      {/* Info card skeleton */}
      <div className="bg-white rounded-lg border p-6 h-48" />
      
      {/* Keywords skeleton */}
      <div className="bg-white rounded-lg border p-6 h-32" />
      
      {/* Grid skeleton */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border p-6 h-40" />
        <div className="bg-white rounded-lg border p-6 h-40" />
      </div>
      
      {/* History skeleton */}
      <div className="bg-white rounded-lg border p-6 h-64" />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Error State
// ─────────────────────────────────────────────────────────────────────────────

interface ErrorStateProps {
  message: string;
  onRetry: () => void;
}

function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
      <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
      <h3 className="text-lg font-semibold text-red-800 mb-2">
        Error Loading Product
      </h3>
      <p className="text-red-600 mb-4">{message}</p>
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
      >
        <RefreshCw className="h-4 w-4" />
        Try Again
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page Header
// ─────────────────────────────────────────────────────────────────────────────

interface PageHeaderProps {
  productId: string;
  productName: string;
  onDelete: () => void;
}

function PageHeader({ productId, productName, onDelete }: PageHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-4">
        <Link
          href="/products"
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">{productName}</h1>
      </div>
      
      <div className="flex gap-2">
        <Link href={`/products/${productId}/edit`}>
          <Button variant="secondary">
            <Edit className="h-4 w-4 mr-2" />
            Edit
          </Button>
        </Link>
        <Button variant="danger" onClick={onDelete}>
          <Trash2 className="h-4 w-4 mr-2" />
          Delete
        </Button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productId = params.id as string;

  const [showDeleteModal, setShowDeleteModal] = useState(false);

  const {
    data: product,
    isLoading,
    error,
    refetch,
  } = useProduct(productId);

  // Scroll to top on page load
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Handlers
  // ─────────────────────────────────────────────────────────────────────────

  const handleDeleteSuccess = () => {
    router.push('/products');
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Render States
  // ─────────────────────────────────────────────────────────────────────────

  if (isLoading) {
    return <PageSkeleton />;
  }

  if (error || !product) {
    return (
      <ErrorState
        message={error?.message || 'Product not found'}
        onRetry={() => refetch()}
      />
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Main Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <PageHeader
        productId={productId}
        productName={product.name}
        onDelete={() => setShowDeleteModal(true)}
      />

      <ProductInfoCard product={product} />

      {/* Keywords Manager - for sentiment tracking */}
      <KeywordsManager
        productId={productId}
        keywords={product.keywords || []}
      />

      <div className="grid md:grid-cols-2 gap-6">
        <AutoPricingCard product={product} />
        <PriceSuggestionCard
          productId={productId}
          currentPrice={product.current_price}
        />
      </div>

      <PriceHistoryCard productId={productId} />

      <DeleteProductModal
        productId={productId}
        productName={product.name}
        isOpen={showDeleteModal}
        onClose={() => setShowDeleteModal(false)}
        onSuccess={handleDeleteSuccess}
      />
    </div>
  );
}
