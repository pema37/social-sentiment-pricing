// Competitors Page
'use client';

import { useState } from 'react';
import { Plus } from 'lucide-react';
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

  const { data, isLoading, error } = useCompetitors();
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

        <button
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" />
          Add Competitor
        </button>
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

      {/* Competitors list */}
      <CompetitorsList
        competitors={data?.items ?? []}
        isLoading={isLoading}
        error={error as Error | null}
        onEdit={handleEdit}
        onAdd={() => setShowForm(true)}
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
