'use client';

import { memo } from 'react';
import { Card } from '@/components/ui';
import { MentionCard, type Mention } from './mention-card';
import { SkeletonMentionsFeed } from '@/components/ui/skeleton';

interface MentionsFeedProps {
  mentions: Mention[] | undefined;
  total: number;
  isLoading: boolean;
  productSelected: boolean;
  className?: string;
}

export const MentionsFeed = memo(function MentionsFeed({ mentions, total, isLoading, productSelected, className }: MentionsFeedProps) {
  if (!productSelected) {
    return (
      <Card className={className}>
        <div className="p-6 flex flex-col items-center justify-center h-32 text-gray-500">
          <p className="text-sm font-medium">Select a product to view mentions</p>
          <p className="text-xs mt-1">Choose a product from the dropdown above</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium">Recent Mentions</h3>
          {!isLoading && total > 0 && <span className="text-sm text-gray-500">{total.toLocaleString()} total</span>}
        </div>
        {isLoading && <SkeletonMentionsFeed />}
        {!isLoading && mentions && mentions.length > 0 && (
          <div className="space-y-3" role="feed">{mentions.map((m) => <MentionCard key={m.id} mention={m} />)}</div>
        )}
        {!isLoading && (!mentions || mentions.length === 0) && (
          <div className="flex flex-col items-center justify-center h-32 text-gray-500">
            <p className="text-sm font-medium">No mentions found</p>
          </div>
        )}
      </div>
    </Card>
  );
});
