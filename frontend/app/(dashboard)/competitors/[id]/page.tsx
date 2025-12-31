// Competitor detail page
'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Globe, ExternalLink, Pencil, Plus } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import {
  useCompetitor,
  useCompetitorProducts,
  useUpdateCompetitor,
  useCreateCompetitorProduct,
} from '@/lib/hooks/use-competitors';
import { 
  CompetitorForm, 
  LinkProductForm,
  CompetitorProductCard,
  AIAnalysisCard,
} from '@/components/features/competitors';
import type { CreateCompetitorRequest, CreateCompetitorProductRequest } from '@/types';

export default function CompetitorDetailPage() {
  const params = useParams();
  const competitorId = params.id as string;
  const [showEditForm, setShowEditForm] = useState(false);
  const [showLinkForm, setShowLinkForm] = useState(false);

  const { data: competitor, isLoading, error } = useCompetitor(competitorId);
  const { data: productsData, isLoading: productsLoading } = useCompetitorProducts({ 
    competitor_id: competitorId 
  });
  const updateCompetitor = useUpdateCompetitor();
  const createCompetitorProduct = useCreateCompetitorProduct();

  const handleUpdate = async (formData: CreateCompetitorRequest) => {
    await updateCompetitor.mutateAsync({ id: competitorId, data: formData });
    setShowEditForm(false);
  };

  const handleLinkProduct = async (formData: CreateCompetitorProductRequest) => {
    await createCompetitorProduct.mutateAsync(formData);
    setShowLinkForm(false);
  };

  if (isLoading) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="animate-pulse">
          <div className="h-6 w-32 bg-gray-200 rounded mb-6" />
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="h-8 w-1/2 bg-gray-200 rounded mb-4" />
            <div className="h-4 w-full bg-gray-100 rounded mb-2" />
            <div className="h-4 w-2/3 bg-gray-100 rounded" />
          </div>
        </div>
      </div>
    );
  }

  if (error || !competitor) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <Link
          href="/competitors"
          className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Competitors
        </Link>
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-red-600 font-medium">Failed to load competitor</p>
          <p className="text-sm text-gray-500 mt-1">
            {(error as Error)?.message || 'Competitor not found'}
          </p>
        </div>
      </div>
    );
  }

  const products = productsData?.items ?? [];

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Back link */}
      <Link
        href="/competitors"
        className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Competitors
      </Link>

      {/* Competitor info card */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden mb-6">
        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <h1 className="text-2xl font-bold text-gray-900">{competitor.name}</h1>
                {!competitor.is_active && (
                  <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-500 rounded-full">
                    Inactive
                  </span>
                )}
              </div>

              {competitor.description && (
                <p className="text-gray-600 mb-3">{competitor.description}</p>
              )}

              {competitor.website && (
                <a
                  href={competitor.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-blue-600 hover:underline"
                >
                  <Globe className="w-4 h-4" />
                  {competitor.website}
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>

            <button
              onClick={() => setShowEditForm(true)}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <Pencil className="w-4 h-4" />
              Edit
            </button>
          </div>
        </div>

        <div className="px-6 py-3 bg-gray-50 border-t border-gray-100 text-sm text-gray-500">
          Added {formatDistanceToNow(new Date(competitor.created_at), { addSuffix: true })}
        </div>
      </div>

      {/* AI Strategy Analysis Card */}
      <div className="mb-6">
        <AIAnalysisCard 
          competitorId={competitorId} 
          competitorName={competitor.name} 
        />
      </div>

      {/* Linked Products */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-gray-900">Tracked Products</h2>
            <p className="text-sm text-gray-500">
              Products linked to this competitor for price tracking
            </p>
          </div>
          <button
            onClick={() => setShowLinkForm(true)}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" />
            Link Product
          </button>
        </div>

        {productsLoading ? (
          <div className="p-6 space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="animate-pulse">
                <div className="h-5 w-1/2 bg-gray-200 rounded mb-2" />
                <div className="h-4 w-1/3 bg-gray-100 rounded" />
              </div>
            ))}
          </div>
        ) : products.length > 0 ? (
          <div className="p-4 space-y-4">
            {products.map((product) => (
              <CompetitorProductCard
                key={product.id}
                competitorProduct={product}
                competitorName={competitor.name}
              />
            ))}
          </div>
        ) : (
          <div className="p-8 text-center">
            <div className="text-4xl mb-3">📦</div>
            <p className="text-gray-600 font-medium">No products linked yet</p>
            <p className="text-sm text-gray-500 mt-1">
              Link your products to track competitor pricing
            </p>
            <button
              onClick={() => setShowLinkForm(true)}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50"
            >
              <Plus className="w-4 h-4" />
              Link Your First Product
            </button>
          </div>
        )}
      </div>

      {/* Edit Form Modal */}
      {showEditForm && (
        <CompetitorForm
          competitor={competitor}
          onSubmit={handleUpdate}
          onCancel={() => setShowEditForm(false)}
          isSubmitting={updateCompetitor.isPending}
        />
      )}

      {/* Link Product Form Modal */}
      {showLinkForm && (
        <LinkProductForm
          preselectedCompetitorId={competitorId}
          onSubmit={handleLinkProduct}
          onCancel={() => setShowLinkForm(false)}
          isSubmitting={createCompetitorProduct.isPending}
        />
      )}
    </div>
  );
}
