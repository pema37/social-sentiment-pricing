import { memo } from 'react';
import { SourceBadge } from './source-badge';
import { cn } from '@/lib/utils';

export interface Mention {
  id: string;
  content: string;
  source: string;
  author: string | null;
  author_followers: number | null;
  engagement_count: number | null;
  url: string | null;
  collected_at: string;
}

function formatRelativeTime(timestamp: string): string {
  const diffMs = Date.now() - new Date(timestamp).getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export const MentionCard = memo(function MentionCard({ mention, className }: { mention: Mention; className?: string }) {
  return (
    <article className={cn('p-4 border border-gray-100 rounded-lg hover:bg-gray-50 transition-colors', className)}>
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <SourceBadge source={mention.source} />
          {mention.author && <span className="text-sm text-gray-600">@{mention.author}</span>}
          {mention.author_followers && mention.author_followers > 1000 && (
            <span className="text-xs text-gray-400">{((mention.author_followers ?? 0) / 1000).toFixed(1)}K followers</span>
          )}
        </div>
        <time dateTime={mention.collected_at} className="text-xs text-gray-400 whitespace-nowrap">{formatRelativeTime(mention.collected_at)}</time>
      </div>
      <p className="text-gray-700 text-sm leading-relaxed">{mention.content}</p>
      <div className="flex items-center gap-4 mt-3">
        {mention.engagement_count !== null && mention.engagement_count > 0 && (
          <span className="text-xs text-gray-500"><span className="font-medium">{mention.engagement_count.toLocaleString()}</span> engagements</span>
        )}
        {mention.url && (
          <a href={mention.url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline">View source →</a>
        )}
      </div>
    </article>
  );
});
