'use client';

// Competitors Page
import { useState } from 'react';
import Link from 'next/link';
import { Plus, Sparkles } from 'lucide-react';
import {
  useCompetitors,
  useCreateCompetitor,
  useUpdateCompetitor,
} from '@/lib/hooks/use-competitors';
import {
  CompetitorsList,
  CompetitorForm,
} from '@/components/features/competitors';
import type { Competitor, CreateCompetitorRequest, UpdateCompetitorRequest } from '@/types';

export default function CompetitorsPage() {
  const [showForm, setShowForm] = useState(false);
  const [editingCompetitor, setEditingCompetitor] = useState<Competitor | null>(null);

  const { data, isLoading, error, refetch } = useCompetitors();
  const createCompetitor = useCreateCompetitor();
  const updateCompetitor = useUpdateCompetitor();

  const handleCreate = async (formData: CreateCompetitorRequest | UpdateCompetitorRequest) => {
    await createCompetitor.mutateAsync(formData as CreateCompetitorRequest);
    setShowForm(false);
  };

  const handleUpdate = async (formData: CreateCompetitorRequest | UpdateCompetitorRequest) => {
    if (!editingCompetitor) return;
    await updateCompetitor.mutateAsync({ id: editingCompetitor.id, data: formData as UpdateCompetitorRequest });
    setEditingCompetitor(null);
  };

  const handleEdit = (competitor: Competitor) => {
    setEditingCompetitor(competitor);
  };

  const handleCloseForm = () => {
    setShowForm(false);
    setEditingCompetitor(null);
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Competitors</h1>
          <p className="text-gray-600 mt-1">
            Track and compare competitor pricing
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* NEW: Auto-find button */}
          <Link
            href="/competitors/match"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            Auto-Find
          </Link>

          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" />
            Add Competitor
          </button>
        </div>
      </div>

      {/* Stats */}
      {data && data.items.length > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Total Competitors</p>
            <p className="text-2xl font-bold text-gray-900">{data.total}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Active</p>
            <p className="text-2xl font-bold text-green-600">
              {data.items.filter((c) => c.is_active).length}
            </p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Inactive</p>
            <p className="text-2xl font-bold text-gray-400">
              {data.items.filter((c) => !c.is_active).length}
            </p>
          </div>
        </div>
      )}

      {/* Auto-Find CTA when no competitors */}
      {data && data.items.length === 0 && !isLoading && (
        <div className="mb-6 p-6 bg-linear-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-blue-100 rounded-lg">
              <Sparkles className="w-6 h-6 text-blue-600" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-gray-900">
                Automatically discover competitors
              </h3>
              <p className="text-sm text-gray-600 mt-1">
                Use our AI-powered search to find competitor products across Amazon, Walmart, 
                Best Buy, and more. Just enter a product name and we&apos;ll find matching listings.
              </p>
              <Link
                href="/competitors/match"
                className="inline-flex items-center gap-2 mt-3 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
              >
                <Sparkles className="w-4 h-4" />
                Find Competitors Automatically
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Competitors list */}
      <CompetitorsList
        competitors={data?.items ?? []}
        isLoading={isLoading}
        error={error as Error | null}
        onEdit={handleEdit}
        onAdd={() => setShowForm(true)}
        onRetry={() => refetch()}
      />

      {/* Create/Edit Form Modal */}
      {(showForm || editingCompetitor) && (
        <CompetitorForm
          competitor={editingCompetitor}
          onSubmit={editingCompetitor ? handleUpdate : handleCreate}
          onCancel={handleCloseForm}
          isSubmitting={createCompetitor.isPending || updateCompetitor.isPending}
        />
      )}
    </div>
  );
}



