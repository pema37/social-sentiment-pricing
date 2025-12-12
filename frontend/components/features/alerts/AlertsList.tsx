// Alerts list component
'use client';

import { AlertItem } from './AlertItem';
import type { Alert } from '@/types';

interface AlertsListProps {
  alerts: Alert[];
  isLoading?: boolean;
  error?: Error | null;
}

export function AlertsList({ alerts, isLoading, error }: AlertsListProps) {
  if (isLoading) {
    return (
      <div className="divide-y divide-gray-100">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="p-4 animate-pulse">
            <div className="flex items-center gap-2 mb-2">
              <div className="h-5 w-16 bg-gray-200 rounded-full" />
              <div className="h-5 w-20 bg-gray-200 rounded-full" />
            </div>
            <div className="h-5 w-3/4 bg-gray-200 rounded mb-2" />
            <div className="h-4 w-full bg-gray-100 rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-center">
        <p className="text-red-600 font-medium">Failed to load alerts</p>
        <p className="text-sm text-gray-500 mt-1">{error.message}</p>
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="p-8 text-center">
        <div className="text-4xl mb-3">🔔</div>
        <p className="text-gray-600 font-medium">No alerts</p>
        <p className="text-sm text-gray-500 mt-1">
          {"You'"}re all caught up! New alerts will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-gray-100">
      {alerts.map((alert) => (
        <AlertItem key={alert.id} alert={alert} />
      ))}
    </div>
  );
}
