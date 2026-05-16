'use client';

// app/(dashboard)/products/[id]/edit/page.tsx
import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, AlertCircle, RefreshCw } from 'lucide-react';
import { useProduct } from '@/lib/hooks/use-products';
import { ProductForm } from '@/components/features/products';

// ─────────────────────────────────────────────────────────────────────────────
// Loading Skeleton
// ─────────────────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-48" />
      <div className="bg-white rounded-lg border p-6 h-64" />
      <div className="bg-white rounded-lg border p-6 h-48" />
      <div className="bg-white rounded-lg border p-6 h-32" />
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
      <h3 className="text-lg font-semibold text-red-800 mb-2">Error Loading Product</h3>
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
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export default function EditProductPage() {
  const params = useParams();
  const router = useRouter();
  const productId = params.id as string;

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

  const handleSuccess = () => {
    router.push(`/products/${productId}`);
  };

  const handleCancel = () => {
    router.back();
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Render States
  // ─────────────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto">
        <PageSkeleton />
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="max-w-3xl mx-auto">
        <ErrorState
          message={error?.message || 'Product not found'}
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Main Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href={`/products/${productId}`}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Edit Product</h1>
          <p className="text-gray-500">{product.name}</p>
        </div>
      </div>

      {/* Form */}
      <ProductForm
        product={product}
        onSuccess={handleSuccess}
        onCancel={handleCancel}
      />
    </div>
  );
}
