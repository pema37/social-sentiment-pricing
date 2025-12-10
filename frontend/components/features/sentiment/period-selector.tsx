import { memo } from 'react';
import { cn } from '@/lib/utils';

interface PeriodSelectorProps {
  value: number;
  onChange: (days: number) => void;
  className?: string;
}

const periods = [
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
];

export const PeriodSelector = memo(function PeriodSelector({ value, onChange, className }: PeriodSelectorProps) {
  return (
    <div className={cn('flex gap-2', className)} role="group" aria-label="Select time period">
      {periods.map((period) => (
        <button
          key={period.days}
          onClick={() => onChange(period.days)}
          className={cn(
            'px-3 py-1.5 text-sm rounded-md transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
            value === period.days ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          )}
          aria-pressed={value === period.days}
          aria-label={`Show data for last ${period.label}`}
        >
          {period.label}
        </button>
      ))}
    </div>
  );
});
