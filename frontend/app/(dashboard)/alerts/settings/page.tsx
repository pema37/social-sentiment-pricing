// Alert settings page
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Plus } from 'lucide-react';
import {
  useAlertConfigurations,
  useCreateAlertConfiguration,
  useUpdateAlertConfiguration,
} from '@/lib/hooks/use-alerts';
import {
  AlertConfigurationCard,
  AlertConfigurationForm,
} from '@/components/features/alerts';
import type { AlertConfiguration, AlertConfigurationCreate } from '@/types';

export default function AlertSettingsPage() {
  const [showForm, setShowForm] = useState(false);
  const [editingConfig, setEditingConfig] = useState<AlertConfiguration | null>(null);

  const { data: configurations, isLoading, error } = useAlertConfigurations();
  const createConfig = useCreateAlertConfiguration();
  const updateConfig = useUpdateAlertConfiguration();

  const handleCreate = async (data: AlertConfigurationCreate) => {
    await createConfig.mutateAsync(data);
    setShowForm(false);
  };

  const handleUpdate = async (data: AlertConfigurationCreate) => {
    if (!editingConfig) return;
    await updateConfig.mutateAsync({ id: editingConfig.id, data });
    setEditingConfig(null);
  };

  const handleEdit = (config: AlertConfiguration) => {
    setEditingConfig(config);
  };

  const handleCloseForm = () => {
    setShowForm(false);
    setEditingConfig(null);
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/alerts"
          className="inline-flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Alerts
        </Link>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Alert Settings</h1>
            <p className="text-gray-600 mt-1">
              Configure how and when you receive alerts
            </p>
          </div>

          <button
            onClick={() => setShowForm(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" />
            New Configuration
          </button>
        </div>
      </div>

      {/* Configurations list */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
                <div className="h-5 w-1/3 bg-gray-200 rounded mb-2" />
                <div className="h-4 w-2/3 bg-gray-100 rounded" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
            <p className="text-red-600 font-medium">Failed to load configurations</p>
            <p className="text-sm text-gray-500 mt-1">{(error as Error).message}</p>
          </div>
        ) : configurations && configurations.length > 0 ? (
          configurations.map((config) => (
            <AlertConfigurationCard
              key={config.id}
              configuration={config}
              onEdit={handleEdit}
            />
          ))
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
            <div className="text-4xl mb-3">⚙️</div>
            <p className="text-gray-600 font-medium">No alert configurations</p>
            <p className="text-sm text-gray-500 mt-1">
              Create your first configuration to customize how you receive alerts.
            </p>
            <button
              onClick={() => setShowForm(true)}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50"
            >
              <Plus className="w-4 h-4" />
              Create Configuration
            </button>
          </div>
        )}
      </div>

      {/* Create/Edit Form Modal */}
      {(showForm || editingConfig) && (
        <AlertConfigurationForm
          configuration={editingConfig}
          onSubmit={editingConfig ? handleUpdate : handleCreate}
          onCancel={handleCloseForm}
          isSubmitting={createConfig.isPending || updateConfig.isPending}
        />
      )}
    </div>
  );
}
