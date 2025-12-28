// Competitor card component
'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Globe, Trash2, Pencil, ExternalLink } from 'lucide-react';
import { useDeleteCompetitor } from '@/lib/hooks/use-competitors';
import type { Competitor } from '@/types';

interface CompetitorCardProps {
  competitor: Competitor;
  onEdit: (competitor: Competitor) => void;
}

export function CompetitorCard({ competitor, onEdit }: CompetitorCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const deleteCompetitor = useDeleteCompetitor();

  const handleDelete = async () => {
    if (!confirm(`Delete "${competitor.name}"? This will also remove all linked products.`)) {
      return;
    }

    setIsDeleting(true);
    try {
      await deleteCompetitor.mutateAsync(competitor.id);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div
      className={`bg-white rounded-lg border p-4 ${
        competitor.is_active ? 'border-gray-200' : 'border-gray-100 opacity-60'
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Link
              href={`/competitors/${competitor.id}`}
              className="font-medium text-gray-900 hover:text-blue-600 truncate"
            >
              {competitor.name}
            </Link>
            {!competitor.is_active && (
              <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-500 rounded-full">
                Inactive
              </span>
            )}
          </div>

          {competitor.description && (
            <p className="text-sm text-gray-500 mb-2 line-clamp-2">
              {competitor.description}
            </p>
          )}

          {competitor.website && (
            <a
              href={competitor.website}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
            >
              <Globe className="w-3.5 h-3.5" />
              <span className="truncate max-w-50">{competitor.website}</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <Link
            href={`/competitors/${competitor.id}`}
            className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded"
            title="View details"
          >
            <ExternalLink className="w-4 h-4" />
          </Link>

          <button
            onClick={() => onEdit(competitor)}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
            title="Edit"
          >
            <Pencil className="w-4 h-4" />
          </button>

          <button
            onClick={handleDelete}
            disabled={isDeleting}
            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded disabled:opacity-50"
            title="Delete"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
