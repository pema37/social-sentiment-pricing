// frontend/app/(dashboard)/sentiment/loading.tsx

/**
 * Sentiment Page Loading Skeleton
 *
 * Next.js renders this automatically while sentiment/page.tsx fetches data.
 * Layout matches SentimentPage:
 * 1. Header row (title + AI badge + product selector, period selector, analyze button)
 * 2. 4-column KPI cards (Current Sentiment, Previous, Total Mentions, 24h Mentions)
 * 3. 2-column chart grid (Sentiment Chart + Mention Volume Chart)
 * 4. "Select a product" prompt card
 *
 * Uses Skeleton primitives from components/ui/skeleton.tsx.
 */

import {
  Skeleton,
  SkeletonCard,
  SkeletonChart,
} from '@/components/ui/skeleton';

export default function SentimentLoading() {
  return (
    <div className="space-y-6">
      {/* Header — title left, filters right */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-7 w-44" />
            <Skeleton className="h-5 w-10 rounded-full" />
          </div>
          <Skeleton className="h-4 w-72 mt-1" />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Skeleton className="h-9 w-40 rounded-md" />
          <Skeleton className="h-9 w-28 rounded-md" />
          <Skeleton className="h-9 w-32 rounded-md" />
        </div>
      </div>

      {/* KPI Cards — 4 columns */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>

      {/* Charts — 2 columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SkeletonChart />
        <SkeletonChart />
      </div>

      {/* Prompt card — "Select a product" placeholder */}
      <div className="p-6 rounded-lg border border-gray-200 bg-white">
        <div className="flex flex-col items-center justify-center h-32">
          <Skeleton className="h-8 w-8 rounded-full mb-2" />
          <Skeleton className="h-4 w-64 mb-1" />
          <Skeleton className="h-3 w-80" />
        </div>
      </div>
    </div>
  );
}



