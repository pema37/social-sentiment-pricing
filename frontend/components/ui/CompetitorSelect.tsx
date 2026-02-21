// components/ui/CompetitorSelect.tsx
'use client';

import { ChevronDown } from 'lucide-react';
import { useCompetitors } from '@/lib/hooks/use-competitors';

interface CompetitorSelectProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  allowAny?: boolean;
}

export function CompetitorSelect({ 
  value, 
  onChange, 
  placeholder = 'Select a competitor',
  allowAny = true,
}: CompetitorSelectProps) {
  const { data: competitorsData, isLoading } = useCompetitors({ page_size: 100 });
  const competitors = competitorsData?.items ?? [];

  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={isLoading}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 appearance-none bg-white text-sm"
      >
        {allowAny && <option value="">Any competitor</option>}
        {!allowAny && <option value="">{placeholder}</option>}
        {competitors.map((comp) => (
          <option key={comp.id} value={comp.id}>
            {comp.name}
          </option>
        ))}
      </select>
      <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
      {isLoading && (
        <span className="absolute right-8 top-1/2 -translate-y-1/2 text-xs text-gray-400">
          Loading...
        </span>
      )}
    </div>
  );
}

