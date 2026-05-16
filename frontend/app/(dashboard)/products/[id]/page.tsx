'use client';

// app/(dashboard)/products/[id]/page.tsx
import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Edit, Trash2, AlertCircle, RefreshCw, Sparkles, Search } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useProduct, useUpdateProduct } from '@/lib/hooks/use-products';
import type { UpdateProductRequest } from '@/types';
import {
  ProductInfoCard,
  AutoPricingCard,
  PriceSuggestionCard,
  PriceHistoryCard,
  DeleteProductModal,
  KeywordsManager,
  GenerateDescriptionModal,
} from '@/components/features/products';

function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="flex items-center gap-4">
        <div className="h-10 w-10 bg-gray-200 rounded-lg" />
        <div className="h-8 bg-gray-200 rounded w-48" />
      </div>
      <div className="bg-white rounded-lg border p-6 h-48" />
      <div className="bg-white rounded-lg border p-6 h-32" />
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg border p-6 h-40" />
        <div className="bg-white rounded-lg border p-6 h-40" />
      </div>
      <div className="bg-white rounded-lg border p-6 h-64" />
    </div>
  );
}

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

interface PageHeaderProps {
  productId: string;
  productName: string;
  onDelete: () => void;
  onGenerateDescription: () => void;
}

function PageHeader({ productId, productName, onDelete, onGenerateDescription }: PageHeaderProps) {
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
        <Link href={`/competitors/match?productId=${productId}`}>
          <Button variant="secondary">
            <Search className="h-4 w-4 mr-2" />
            Find Competitors
          </Button>
        </Link>
        <Button variant="secondary" onClick={onGenerateDescription}>
          <Sparkles className="h-4 w-4 mr-2" />
          AI Description
        </Button>
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

export default function ProductDetailPage() {
  const params = useParams();
  const router = useRouter();
  const productId = params.id as string;

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showGenerateModal, setShowGenerateModal] = useState(false);

  const {
    data: product,
    isLoading,
    error,
    refetch,
  } = useProduct(productId);
  const { mutateAsync: updateProduct } = useUpdateProduct();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const handleDeleteSuccess = () => {
    router.push('/products');
  };

  const handleApplyGenerated = async (fields: {
    description?: string;
    seo_title?: string;
    meta_description?: string;
    keywords?: string[];
  }) => {
    try {
      const updateData: Record<string, unknown> = {};
      if (fields.description) updateData.description = fields.description;
      if (fields.keywords) updateData.keywords = fields.keywords;
      
      if (Object.keys(updateData).length > 0) {
        await updateProduct({ id: productId, data: updateData as UpdateProductRequest });
      }
    } catch (err) {
      console.error('Failed to update product:', err);
    }
  };

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

  return (
    <div className="space-y-6">
      <PageHeader
        productId={productId}
        productName={product.name}
        onDelete={() => setShowDeleteModal(true)}
        onGenerateDescription={() => setShowGenerateModal(true)}
      />

      <ProductInfoCard product={product} />

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

      <GenerateDescriptionModal
        isOpen={showGenerateModal}
        onClose={() => setShowGenerateModal(false)}
        productId={productId}
        productName={product.name}
        onApply={handleApplyGenerated}
      />
    </div>
  );
}


