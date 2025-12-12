// Recent alerts widget for dashboard
'use client';

import Link from 'next/link';
import { Bell, AlertTriangle, Info, CheckCircle } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import type { Alert } from '@/types/alert';

interface RecentAlertsProps {
  alerts: Alert[];
  isLoading?: boolean;
  maxItems?: number;
}

const severityConfig = {
  critical: { bg: 'bg-red-50', border: 'border-red-200', icon: AlertTriangle, iconColor: 'text-red-500' },
  high: { bg: 'bg-orange-50', border: 'border-orange-200', icon: AlertTriangle, iconColor: 'text-orange-500' },
  medium: { bg: 'bg-amber-50', border: 'border-amber-200', icon: Bell, iconColor: 'text-amber-500' },
  low: { bg: 'bg-blue-50', border: 'border-blue-200', icon: Info, iconColor: 'text-blue-500' },
};

function AlertRow({ alert }: { alert: Alert }) {
  const config = severityConfig[alert.severity] || severityConfig.low;
  const IconComponent = config.icon;

  return (
    <Link
      href={`/alerts/${alert.id}`}
      className={`block p-3 rounded-lg border ${config.bg} ${config.border} hover:opacity-80 transition-opacity`}
    >
      <div className="flex items-start gap-3">
        <IconComponent className={`w-5 h-5 ${config.iconColor} mt-0.5 shrink-0`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{alert.title}</p>
          <p className="text-sm text-gray-600 mt-0.5 line-clamp-1">{alert.message}</p>
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                alert.status === 'pending'
                  ? 'bg-yellow-100 text-yellow-700'
                  : alert.status === 'acknowledged'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-green-100 text-green-700'
              }`}
            >
              {alert.status}
            </span>
            <span className="text-xs text-gray-400">
              {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
            </span>
          </div>
        </div>
      </div>
    </Link>
  );
}

export function RecentAlerts({ alerts, isLoading, maxItems = 5 }: RecentAlertsProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-gray-500">
        <CheckCircle className="w-8 h-8 mb-2 text-gray-400" />
        <p className="text-sm">No pending alerts</p>
      </div>
    );
  }

  const displayAlerts = alerts.slice(0, maxItems);

  return (
    <div className="space-y-3">
      {displayAlerts.map((alert) => (
        <AlertRow key={alert.id} alert={alert} />
      ))}
      {alerts.length > maxItems && (
        <p className="text-xs text-center text-gray-500">
          +{alerts.length - maxItems} more alerts
        </p>
      )}
    </div>
  );
}
