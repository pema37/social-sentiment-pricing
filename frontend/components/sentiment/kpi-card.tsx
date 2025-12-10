import { memo } from 'react';
import { Card } from '@/components/ui';
import { TrendBadge } from './trend-badge';
import { cn } from '@/lib/utils';

interface KpiCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: 'up' | 'down' | 'stable';
  change?: number | null;
  className?: string;
}

export const KpiCard = memo(function KpiCard({ title, value, subtitle, trend, change, className }: KpiCardProps) {
  return (
    <Card className={cn('p-6', className)} role="region" aria-labelledby={`kpi-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <p id={`kpi-${title.toLowerCase().replace(/\s+/g, '-')}`} className="text-sm text-gray-500 mb-1">{title}</p>
      <div className="flex items-center gap-3">
        <p className="text-3xl font-semibold" aria-label={`${title}: ${value}`}>{value}</p>
        {trend && <TrendBadge trend={trend} change={change ?? null} />}
      </div>
      {subtitle && <p className="text-sm text-gray-400 mt-1">{subtitle}</p>}
    </Card>
  );
});
