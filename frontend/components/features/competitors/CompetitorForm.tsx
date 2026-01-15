// Competitor form component
'use client';

import { useState, useCallback } from 'react';
import { X } from 'lucide-react';
import { toast } from 'sonner';
import type { Competitor, CreateCompetitorRequest, UpdateCompetitorRequest } from '@/types/competitor';

// Domain layer
import {
  competitorToFormData,
  validateAndCreateCompetitor,
  validateAndUpdateCompetitor,
  DEFAULT_COMPETITOR_FORM,
  type CompetitorFormData,
  type CompetitorFormErrors,
} from '@/lib/domain/competitors';

interface CompetitorFormProps {
  competitor?: Competitor | null;
  onSubmit: (data: CreateCompetitorRequest | UpdateCompetitorRequest) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export function CompetitorForm({
  competitor,
  onSubmit,
  onCancel,
  isSubmitting,
}: CompetitorFormProps) {
  const [formData, setFormData] = useState<CompetitorFormData>(() =>
    competitor ? competitorToFormData(competitor) : DEFAULT_COMPETITOR_FORM
  );
  const [errors, setErrors] = useState<CompetitorFormErrors>({});

  const isEditing = !!competitor;

  const handleChange = useCallback((field: keyof CompetitorFormData, value: string | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: undefined }));
  }, [errors]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const result = isEditing
      ? validateAndUpdateCompetitor(formData)
      : validateAndCreateCompetitor(formData);

    if (!result.success) {
      setErrors(result.errors);
      toast.error('Please fix the errors');
      return;
    }

    onSubmit(result.data);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEditing ? 'Edit Competitor' : 'Add Competitor'}
          </h2>
          <button
            onClick={onCancel}
            className="p-1 text-gray-400 hover:text-gray-600 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Competitor Name *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="e.g., Amazon, Walmart"
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                errors.name ? 'border-red-500' : 'border-gray-300'
              }`}
            />
            {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name}</p>}
          </div>

          {/* Website */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Website
            </label>
            <input
              type="text"
              value={formData.website}
              onChange={(e) => handleChange('website', e.target.value)}
              placeholder="example.com"
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                errors.website ? 'border-red-500' : 'border-gray-300'
              }`}
            />
            {errors.website && <p className="text-red-500 text-xs mt-1">{errors.website}</p>}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Optional notes about this competitor..."
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Saving...' : isEditing ? 'Update' : 'Add Competitor'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


