// Alert severity badge component
'use client';

import type { AlertSeverity } from '@/types';

interface AlertBadgeProps {
  severity: AlertSeverity;
  size?: 'sm' | 'md';
}

const severityConfig: Record<AlertSeverity, { label: string; className: string }> = {
  low: {
    label: 'Low',
    className: 'bg-slate-100 text-slate-700',
  },
  medium: {
    label: 'Medium',
    className: 'bg-yellow-100 text-yellow-800',
  },
  high: {
    label: 'High',
    className: 'bg-orange-100 text-orange-800',
  },
  critical: {
    label: 'Critical',
    className: 'bg-red-100 text-red-800',
  },
};

export function AlertBadge({ severity, size = 'md' }: AlertBadgeProps) {
  const config = severityConfig[severity];
  
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
