import { cn } from '@/lib/utils';

const sourceColors: Record<string, string> = {
  twitter: 'bg-blue-100 text-blue-800',
  reddit: 'bg-orange-100 text-orange-800',
  manual: 'bg-gray-100 text-gray-800',
  news: 'bg-purple-100 text-purple-800',
  instagram: 'bg-pink-100 text-pink-800',
  facebook: 'bg-indigo-100 text-indigo-800',
  youtube: 'bg-red-100 text-red-800',
};

export function SourceBadge({ source, className }: { source: string; className?: string }) {
  const colors = sourceColors[source.toLowerCase()] || 'bg-gray-100 text-gray-800';
  return <span className={cn('px-2 py-0.5 rounded text-xs font-medium capitalize', colors, className)}>{source}</span>;
}
