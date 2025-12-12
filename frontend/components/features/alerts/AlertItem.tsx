// Single alert item component
'use client';

import { formatDistanceToNow } from 'date-fns';
import { AlertBadge } from './AlertBadge';
import { AlertStatusBadge } from './AlertStatusBadge';
import { useAcknowledgeAlert, useResolveAlert } from '@/lib/hooks/use-alerts';
import type { Alert } from '@/types';

interface AlertItemProps {
  alert: Alert;
}

const alertTypeLabels: Record<string, string> = {
  sentiment_drop: 'Sentiment Drop',
  sentiment_spike: 'Sentiment Spike',
  price_recommendation: 'Price Recommendation',
  competitor_price_change: 'Competitor Price Change',
  volume_surge: 'Volume Surge',
  viral_mention: 'Viral Mention',
};

export function AlertItem({ alert }: AlertItemProps) {
  const acknowledgeAlert = useAcknowledgeAlert();
  const resolveAlert = useResolveAlert();

  const isPending = alert.status === 'pending';
  const isAcknowledged = alert.status === 'acknowledged';

  const handleAcknowledge = () => {
    acknowledgeAlert.mutate(alert.id);
  };

  const handleResolve = () => {
    resolveAlert.mutate(alert.id);
  };

  return (
    <div
      className={`p-4 border-b border-gray-100 hover:bg-gray-50 transition-colors ${
        isPending ? 'bg-blue-50/30' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <AlertBadge severity={alert.severity} size="sm" />
            <AlertStatusBadge status={alert.status} size="sm" />
            <span className="text-xs text-gray-500">
              {alertTypeLabels[alert.alert_type] || alert.alert_type}
            </span>
          </div>
          
          <h4 className="font-medium text-gray-900 truncate">{alert.title}</h4>
          <p className="text-sm text-gray-600 mt-1 line-clamp-2">{alert.message}</p>
          
          <p className="text-xs text-gray-400 mt-2">
            {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {isPending && (
            <button
              onClick={handleAcknowledge}
              disabled={acknowledgeAlert.isPending}
              className="px-3 py-1.5 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              {acknowledgeAlert.isPending ? 'Acknowledging...' : 'Acknowledge'}
            </button>
          )}
          
          {isAcknowledged && (
            <button
              onClick={handleResolve}
              disabled={resolveAlert.isPending}
              className="px-3 py-1.5 text-xs font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50"
            >
              {resolveAlert.isPending ? 'Resolving...' : 'Resolve'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
