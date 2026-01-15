// Alert configuration form component
'use client';

import { useState, useCallback } from 'react';
import { X } from 'lucide-react';
import { toast } from 'sonner';
import type { AlertConfiguration } from '@/types/alert';

// Domain layer
import {
  alertConfigToFormData,
  validateAndCreateAlertConfig,
  validateAndUpdateAlertConfig,
  DEFAULT_ALERT_CONFIG_FORM,
  ALERT_TYPES,
  ALERT_CHANNELS,
  type AlertConfigFormData,
  type AlertConfigFormErrors,
} from '@/lib/domain/alerts';
import type { AlertChannel } from '@/types/alert';

interface AlertConfigurationFormProps {
  configuration?: AlertConfiguration | null;
  onSubmit: (data: ReturnType<typeof validateAndCreateAlertConfig> extends { success: true; data: infer D } ? D : never) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

export function AlertConfigurationForm({
  configuration,
  onSubmit,
  onCancel,
  isSubmitting,
}: AlertConfigurationFormProps) {
  const [formData, setFormData] = useState<AlertConfigFormData>(() =>
    configuration ? alertConfigToFormData(configuration) : DEFAULT_ALERT_CONFIG_FORM
  );
  const [errors, setErrors] = useState<AlertConfigFormErrors>({});

  const isEditing = !!configuration;

  const handleChange = useCallback((field: keyof AlertConfigFormData, value: string | boolean | string[]) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: undefined }));
  }, [errors]);

  const handleChannelToggle = useCallback((channel: AlertChannel) => {
    setFormData(prev => ({
      ...prev,
      channels: prev.channels.includes(channel)
        ? prev.channels.filter(c => c !== channel)
        : [...prev.channels, channel],
    }));
    if (errors.channels) setErrors(prev => ({ ...prev, channels: undefined }));
  }, [errors]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const result = isEditing
      ? validateAndUpdateAlertConfig(formData)
      : validateAndCreateAlertConfig(formData);

    if (!result.success) {
      setErrors(result.errors);
      toast.error('Please fix the errors');
      return;
    }

    onSubmit(result.data as Parameters<typeof onSubmit>[0]);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEditing ? 'Edit Alert Configuration' : 'New Alert Configuration'}
          </h2>
          <button onClick={onCancel} className="p-1 text-gray-400 hover:text-gray-600 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              placeholder="e.g., Critical Sentiment Alerts"
              className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 ${
                errors.name ? 'border-red-500' : 'border-gray-300'
              }`}
            />
            {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name}</p>}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Optional description..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Alert Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Alert Type *</label>
            <select
              value={formData.alert_type}
              onChange={(e) => handleChange('alert_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {ALERT_TYPES.map((type) => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>
          </div>

          {/* Channels */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Notification Channels *</label>
            <div className="space-y-2">
              {ALERT_CHANNELS.map((channel) => (
                <label
                  key={channel.value}
                  className="flex items-center gap-3 p-2 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={formData.channels.includes(channel.value)}
                    onChange={() => handleChannelToggle(channel.value)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{channel.label}</span>
                </label>
              ))}
            </div>
            {errors.channels && <p className="text-red-500 text-xs mt-1">{errors.channels}</p>}
          </div>

          {/* Cooldown */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cooldown (minutes)</label>
            <input
              type="number"
              value={formData.cooldown_minutes}
              onChange={(e) => handleChange('cooldown_minutes', e.target.value)}
              min={1}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">Minimum time between alerts of this type</p>
          </div>

          {/* Max per day */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Alerts Per Day</label>
            <input
              type="number"
              value={formData.max_per_day}
              onChange={(e) => handleChange('max_per_day', e.target.value)}
              min={1}
              placeholder="10"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Active toggle */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span className="text-sm font-medium text-gray-700">Enable this configuration</span>
            <button
              type="button"
              onClick={() => handleChange('is_active', !formData.is_active)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                formData.is_active ? 'bg-blue-600' : 'bg-gray-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  formData.is_active ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
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
              {isSubmitting ? 'Saving...' : isEditing ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


