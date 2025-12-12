// Alert configuration form component
'use client';

import { useState } from 'react';
import { X } from 'lucide-react';
import type { 
  AlertConfiguration, 
  AlertConfigurationCreate, 
  AlertType, 
  AlertChannel 
} from '@/types';

interface AlertConfigurationFormProps {
  configuration?: AlertConfiguration | null;
  onSubmit: (data: AlertConfigurationCreate) => void;
  onCancel: () => void;
  isSubmitting?: boolean;
}

const alertTypes: { value: AlertType; label: string }[] = [
  { value: 'sentiment_drop', label: 'Sentiment Drop' },
  { value: 'sentiment_spike', label: 'Sentiment Spike' },
  { value: 'price_recommendation', label: 'Price Recommendation' },
  { value: 'competitor_price_change', label: 'Competitor Price Change' },
  { value: 'volume_surge', label: 'Volume Surge' },
  { value: 'viral_mention', label: 'Viral Mention' },
];

const channels: { value: AlertChannel; label: string }[] = [
  { value: 'in_app', label: 'In-App Notifications' },
  { value: 'email', label: 'Email' },
  { value: 'slack', label: 'Slack' },
  { value: 'webhook', label: 'Webhook' },
];

export function AlertConfigurationForm({
  configuration,
  onSubmit,
  onCancel,
  isSubmitting,
}: AlertConfigurationFormProps) {
  const [name, setName] = useState(configuration?.name ?? '');
  const [description, setDescription] = useState(configuration?.description ?? '');
  const [alertType, setAlertType] = useState<AlertType>(configuration?.alert_type ?? 'sentiment_drop');
  const [selectedChannels, setSelectedChannels] = useState<AlertChannel[]>(configuration?.channels ?? ['in_app']);
  const [cooldownMinutes, setCooldownMinutes] = useState(configuration?.cooldown_minutes ?? 60);
  const [maxPerDay, setMaxPerDay] = useState<number | ''>(configuration?.max_per_day ?? '');
  const [isActive, setIsActive] = useState(configuration?.is_active ?? true);

  const handleChannelToggle = (channel: AlertChannel) => {
    setSelectedChannels((prev) =>
      prev.includes(channel)
        ? prev.filter((c) => c !== channel)
        : [...prev, channel]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!name.trim() || selectedChannels.length === 0) return;

    onSubmit({
      name: name.trim(),
      description: description.trim() || undefined,
      alert_type: alertType,
      channels: selectedChannels,
      cooldown_minutes: cooldownMinutes,
      max_per_day: maxPerDay || undefined,
      is_active: isActive,
    });
  };

  const isEditing = !!configuration;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEditing ? 'Edit Alert Configuration' : 'New Alert Configuration'}
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
              Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Critical Sentiment Alerts"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Alert Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Alert Type *
            </label>
            <select
              value={alertType}
              onChange={(e) => setAlertType(e.target.value as AlertType)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {alertTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </div>

          {/* Channels */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Notification Channels *
            </label>
            <div className="space-y-2">
              {channels.map((channel) => (
                <label
                  key={channel.value}
                  className="flex items-center gap-3 p-2 border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={selectedChannels.includes(channel.value)}
                    onChange={() => handleChannelToggle(channel.value)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">{channel.label}</span>
                </label>
              ))}
            </div>
            {selectedChannels.length === 0 && (
              <p className="text-xs text-red-500 mt-1">Select at least one channel</p>
            )}
          </div>

          {/* Cooldown */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Cooldown (minutes)
            </label>
            <input
              type="number"
              value={cooldownMinutes}
              onChange={(e) => setCooldownMinutes(parseInt(e.target.value) || 0)}
              min={0}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Minimum time between alerts of this type
            </p>
          </div>

          {/* Max per day */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Alerts Per Day
            </label>
            <input
              type="number"
              value={maxPerDay}
              onChange={(e) => setMaxPerDay(e.target.value ? parseInt(e.target.value) : '')}
              min={1}
              placeholder="Unlimited"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Active toggle */}
          <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <span className="text-sm font-medium text-gray-700">Enable this configuration</span>
            <button
              type="button"
              onClick={() => setIsActive(!isActive)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                isActive ? 'bg-blue-600' : 'bg-gray-200'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  isActive ? 'translate-x-6' : 'translate-x-1'
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
              disabled={isSubmitting || !name.trim() || selectedChannels.length === 0}
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
