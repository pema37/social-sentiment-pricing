// frontend/app/(dashboard)/dashboard/loading.tsx

/**
 * Dashboard Loading Skeleton
 *
 * Next.js automatically renders this file while dashboard/page.tsx is loading
 * data from the server. The skeleton layout matches the real page structure
 * so content doesn't jump around when data arrives.
 *
 * Layout (matches DashboardPage):
 * 1. Page header (title + refresh button)
 * 2. 4-column stats grid (Products, Recommendations, Alerts, Competitors)
 * 3. AI Features card
 * 4. Sentiment trend chart
 * 5. Quick Actions card
 * 6. 3-column grid: products (2 cols) + alerts/recommendations (1 col)
 *
 * Uses the shared Skeleton primitives from components/ui/skeleton.tsx.
 */

import {
  Skeleton,
  SkeletonCard,
  SkeletonChart,
} from '@/components/ui/skeleton';

export default function DashboardLoading() {
  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <Skeleton className="h-7 w-36 mb-1" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-9 w-24 rounded-md" />
      </div>

      {/* Stats grid — 4 cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>

      {/* AI Features card */}
      <div className="p-6 rounded-lg border border-gray-200 bg-white">
        <Skeleton className="h-5 w-40 mb-3" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Skeleton className="h-24 rounded-lg" />
          <Skeleton className="h-24 rounded-lg" />
          <Skeleton className="h-24 rounded-lg" />
        </div>
      </div>

      {/* Sentiment trend chart */}
      <SkeletonChart />

      {/* Quick actions card */}
      <div className="p-6 rounded-lg border border-gray-200 bg-white">
        <Skeleton className="h-5 w-28 mb-4" />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
      </div>

      {/* Main content grid — products (2 cols) + sidebar (1 col) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Products section */}
        <div className="lg:col-span-2">
          <div className="p-6 rounded-lg border border-gray-200 bg-white">
            <div className="flex items-center justify-between mb-4">
              <Skeleton className="h-5 w-28" />
              <Skeleton className="h-8 w-20 rounded-md" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-32 rounded-lg" />
              ))}
            </div>
          </div>
        </div>

        {/* Right column — alerts + recommendations */}
        <div className="space-y-6">
          {/* Pending alerts */}
          <div className="p-6 rounded-lg border border-gray-200 bg-white">
            <div className="flex items-center justify-between mb-4">
              <Skeleton className="h-5 w-28" />
              <Skeleton className="h-8 w-16 rounded-md" />
            </div>
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                  <Skeleton className="h-8 w-8 rounded-full shrink-0" />
                  <div className="flex-1">
                    <Skeleton className="h-4 w-full mb-1" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Price recommendations */}
          <div className="p-6 rounded-lg border border-gray-200 bg-white">
            <div className="flex items-center justify-between mb-4">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-8 w-16 rounded-md" />
            </div>
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-gray-100">
                  <div>
                    <Skeleton className="h-4 w-32 mb-1" />
                    <Skeleton className="h-3 w-20" />
                  </div>
                  <Skeleton className="h-8 w-20 rounded-md" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}



