// Alert configuration card component
'use client';

import { useState } from 'react';
import { Trash2, Pencil } from 'lucide-react';
import { 
  useUpdateAlertConfiguration, 
  useDeleteAlertConfiguration 
} from '@/lib/hooks/use-alerts';
import type { AlertConfiguration, AlertChannel } from '@/types';

interface AlertConfigurationCardProps {
  configuration: AlertConfiguration;
  onEdit: (config: AlertConfiguration) => void;
}

const alertTypeLabels: Record<string, string> = {
  sentiment_drop: 'Sentiment Drop',
  sentiment_spike: 'Sentiment Spike',
  price_recommendation: 'Price Recommendation',
  competitor_price_change: 'Competitor Price Change',
  volume_surge: 'Volume Surge',
  viral_mention: 'Viral Mention',
};

const channelLabels: Record<AlertChannel, string> = {
  email: 'Email',
  in_app: 'In-App',
  slack: 'Slack',
  webhook: 'Webhook',
};

export function AlertConfigurationCard({ configuration, onEdit }: AlertConfigurationCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  
  const updateConfig = useUpdateAlertConfiguration();
  const deleteConfig = useDeleteAlertConfiguration();

  const handleToggleActive = () => {
    updateConfig.mutate({
      id: configuration.id,
      data: { is_active: !configuration.is_active },
    });
  };

  const handleDelete = async () => {
    if (!confirm('Delete this alert configuration?')) return;
    
    setIsDeleting(true);
    try {
      await deleteConfig.mutateAsync(configuration.id);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className={`bg-white rounded-lg border p-4 ${
      configuration.is_active ? 'border-gray-200' : 'border-gray-100 opacity-60'
    }`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-gray-900 truncate">{configuration.name}</h3>
            <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-full">
              {alertTypeLabels[configuration.alert_type] || configuration.alert_type}
            </span>
          </div>
          
          {configuration.description && (
            <p className="text-sm text-gray-500 mb-2">{configuration.description}</p>
          )}

          <div className="flex flex-wrap gap-1 mt-2">
            {configuration.channels.map((channel) => (
              <span
                key={channel}
                className="px-2 py-0.5 text-xs bg-blue-50 text-blue-700 rounded"
              >
                {channelLabels[channel] || channel}
              </span>
            ))}
          </div>

          <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
            <span>Cooldown: {configuration.cooldown_minutes}m</span>
            {configuration.max_per_day && (
              <span>Max/day: {configuration.max_per_day}</span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {/* Toggle */}
          <button
            onClick={handleToggleActive}
            disabled={updateConfig.isPending}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              configuration.is_active ? 'bg-blue-600' : 'bg-gray-200'
            }`}
            aria-label={configuration.is_active ? 'Disable' : 'Enable'}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                configuration.is_active ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>

          {/* Edit */}
          <button
            onClick={() => onEdit(configuration)}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
            aria-label="Edit"
          >
            <Pencil className="w-4 h-4" />
          </button>

          {/* Delete */}
          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded disabled:opacity-50"
            aria-label="Delete"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
