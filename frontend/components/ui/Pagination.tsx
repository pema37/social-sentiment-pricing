// components/ui/Pagination.tsx
'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Button } from './Button';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface PaginationProps {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function getShowingRange(page: number, pageSize: number, total: number) {
  if (total === 0) return { start: 0, end: 0 };
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);
  return { start, end };
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function Pagination({
  page,
  totalPages,
  total,
  pageSize,
  onPageChange,
}: PaginationProps) {
  // BUG FIX #1: Defensive number conversion
  // API responses may return strings or undefined - ensure we have valid numbers
  const numPage = Number(page) || 1;
  const numTotalPages = Number(totalPages) || 1;
  const numTotal = Number(total) || 0;
  const numPageSize = Number(pageSize) || 10;

  // Don't render if only one page or no results
  if (numTotalPages <= 1) return null;

  const { start, end } = getShowingRange(numPage, numPageSize, numTotal);
  const canGoPrevious = numPage > 1;
  const canGoNext = numPage < numTotalPages;

  return (
    <div className="flex items-center justify-between px-6 py-4 border-t">
      <p className="text-sm text-gray-500">
        Showing {start} to {end} of {numTotal} results
      </p>

      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(numPage - 1)}
          disabled={!canGoPrevious}
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>

        <span className="text-sm text-gray-600 px-3">
          Page {numPage} of {numTotalPages}
        </span>

        <Button
          variant="secondary"
          size="sm"
          onClick={() => onPageChange(numPage + 1)}
          disabled={!canGoNext}
        >
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

export default Pagination;




