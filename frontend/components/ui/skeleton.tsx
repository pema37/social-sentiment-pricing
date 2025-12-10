import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ className, style }: SkeletonProps) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-gray-200', className)}
      style={style}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('p-6 rounded-lg border border-gray-200 bg-white', className)}>
      <Skeleton className="h-4 w-24 mb-2" />
      <Skeleton className="h-8 w-16 mb-1" />
      <Skeleton className="h-3 w-20" />
    </div>
  );
}

// Pre-generated heights to avoid Math.random() during render
const BAR_HEIGHTS = ['45%', '72%', '38%', '85%', '52%', '67%', '41%', '78%', '55%', '63%', '48%', '70%'];

export function SkeletonChart({ className }: { className?: string }) {
  return (
    <div className={cn('p-6 rounded-lg border border-gray-200 bg-white', className)}>
      <Skeleton className="h-5 w-48 mb-4" />
      <div className="h-72 flex items-end gap-2 pt-8">
        {BAR_HEIGHTS.map((height, i) => (
          <Skeleton key={i} className="flex-1" style={{ height }} />
        ))}
      </div>
    </div>
  );
}

export function SkeletonMention({ className }: { className?: string }) {
  return (
    <div className={cn('p-4 rounded-lg border border-gray-100', className)}>
      <div className="flex items-center gap-2 mb-2">
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-12 ml-auto" />
      </div>
      <Skeleton className="h-4 w-full mb-1" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}

export function SkeletonKpiGrid() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4" role="status" aria-label="Loading metrics">
      {[0, 1, 2, 3].map((i) => <SkeletonCard key={i} />)}
    </div>
  );
}

export function SkeletonChartGrid() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" role="status" aria-label="Loading charts">
      <SkeletonChart />
      <SkeletonChart />
    </div>
  );
}

export function SkeletonMentionsFeed() {
  return (
    <div className="space-y-3" role="status" aria-label="Loading mentions">
      {[0, 1, 2, 3, 4].map((i) => <SkeletonMention key={i} />)}
    </div>
  );
}
