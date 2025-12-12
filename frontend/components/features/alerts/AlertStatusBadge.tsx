// Alert status badge component
'use client';

import type { AlertStatus } from '@/types';

interface AlertStatusBadgeProps {
  status: AlertStatus;
  size?: 'sm' | 'md';
}

const statusConfig: Record<AlertStatus, { label: string; className: string }> = {
  pending: {
    label: 'Pending',
    className: 'bg-blue-100 text-blue-800',
  },
  acknowledged: {
    label: 'Acknowledged',
    className: 'bg-purple-100 text-purple-800',
  },
  resolved: {
    label: 'Resolved',
    className: 'bg-green-100 text-green-800',
  },
};

export function AlertStatusBadge({ status, size = 'md' }: AlertStatusBadgeProps) {
  const config = statusConfig[status];
  
  const sizeClasses = size === 'sm' 
    ? 'px-1.5 py-0.5 text-xs' 
    : 'px-2 py-1 text-xs';

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full ${sizeClasses} ${config.className}`}
    >
      {config.label}
    </span>
  );
}
