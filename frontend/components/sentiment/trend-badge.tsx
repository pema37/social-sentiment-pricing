import { cn } from '@/lib/utils';

interface TrendBadgeProps {
  trend: 'up' | 'down' | 'stable';
  change: number | null;
  className?: string;
}

const trendConfig = {
  up: { icon: '↑', colors: 'bg-green-100 text-green-800', label: 'Trending up' },
  down: { icon: '↓', colors: 'bg-red-100 text-red-800', label: 'Trending down' },
  stable: { icon: '→', colors: 'bg-gray-100 text-gray-800', label: 'Stable' },
};

export function TrendBadge({ trend, change, className }: TrendBadgeProps) {
  const config = trendConfig[trend];
  const changeText = change !== null ? ` ${Math.abs(change * 100).toFixed(1)}%` : '';
  
  return (
    <span 
      className={cn('inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm font-medium', config.colors, className)}
      role="status"
      aria-label={`${config.label}${changeText ? ` by ${changeText}` : ''}`}
    >
      <span aria-hidden="true">{config.icon}</span>
      {changeText}
    </span>
  );
}
