// frontend/app/(dashboard)/products/loading.tsx

/**
 * Products Page Loading Skeleton
 *
 * Next.js renders this automatically while products/page.tsx fetches data.
 * Layout matches ProductsPage:
 * 1. Header row (title + Import CSV / Add Product buttons)
 * 2. Search bar card
 * 3. Table with header row + 8 product rows
 * 4. Pagination bar
 *
 * Uses Skeleton primitives from components/ui/skeleton.tsx.
 */

import { Skeleton } from '@/components/ui/skeleton';

export default function ProductsLoading() {
  return (
    <div className="space-y-6">
      {/* Header — title left, buttons right */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Skeleton className="h-7 w-32 mb-1" />
          <Skeleton className="h-4 w-56" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-9 w-28 rounded-md" />
          <Skeleton className="h-9 w-32 rounded-md" />
        </div>
      </div>

      {/* Search bar card */}
      <div className="p-4 rounded-lg border border-gray-200 bg-white">
        <Skeleton className="h-10 w-full rounded-md" />
      </div>

      {/* Table */}
      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        {/* Table header */}
        <div className="grid grid-cols-6 gap-4 px-6 py-3 border-b border-gray-200 bg-gray-50">
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-14" />
          <Skeleton className="h-4 w-16" />
        </div>

        {/* Table rows */}
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="grid grid-cols-6 gap-4 px-6 py-4 border-b border-gray-100 items-center"
          >
            {/* Product name + SKU */}
            <div>
              <Skeleton className="h-4 w-32 mb-1" />
              <Skeleton className="h-3 w-20" />
            </div>
            {/* Category */}
            <Skeleton className="h-4 w-20" />
            {/* Base price */}
            <Skeleton className="h-4 w-16" />
            {/* Current price */}
            <Skeleton className="h-4 w-16" />
            {/* Status badge */}
            <Skeleton className="h-6 w-14 rounded-full" />
            {/* Actions */}
            <div className="flex gap-2 justify-end">
              <Skeleton className="h-8 w-8 rounded-md" />
              <Skeleton className="h-8 w-8 rounded-md" />
            </div>
          </div>
        ))}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-32" />
        <div className="flex gap-1">
          <Skeleton className="h-8 w-8 rounded-md" />
          <Skeleton className="h-8 w-8 rounded-md" />
          <Skeleton className="h-8 w-8 rounded-md" />
          <Skeleton className="h-8 w-8 rounded-md" />
        </div>
      </div>
    </div>
  );
}



