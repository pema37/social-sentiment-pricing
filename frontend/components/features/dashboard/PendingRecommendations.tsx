// Pending recommendations widget for dashboard
'use client';

import Link from 'next/link';
import { DollarSign, ArrowRight, Clock } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import type { PriceRecommendation } from '@/types/pricing';

interface PendingRecommendationsProps {
  recommendations: PriceRecommendation[];
  isLoading?: boolean;
  maxItems?: number;
}

function RecommendationRow({ recommendation }: { recommendation: PriceRecommendation }) {
  const changePercent = recommendation.change_percent ?? 0;  
  const isIncrease = changePercent > 0;

  return (
    <Link
      href={`/pricing/recommendations/${recommendation.id}`}
      className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 hover:border-blue-300 hover:bg-blue-50/50 transition-all group"
    >
      <div
        className={`p-2 rounded-lg shrink-0 ${
          isIncrease ? 'bg-green-50' : 'bg-red-50'
        }`}
      >
        <DollarSign
          className={`w-4 h-4 ${isIncrease ? 'text-green-600' : 'text-red-600'}`}
        />
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">
          Price Recommendation
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-gray-500">
            ${parseFloat(recommendation.current_price || '0').toFixed(2)}
          </span>
          <ArrowRight className="w-3 h-3 text-gray-400" />
          <span
            className={`text-xs font-medium ${
              isIncrease ? 'text-green-600' : 'text-red-600'
            }`}
          >
            ${parseFloat(recommendation.recommended_price || '0').toFixed(2)}
          </span>
        </div>
      </div>

      <div className="text-right shrink-0">
        <p
          className={`text-sm font-semibold ${
            isIncrease ? 'text-green-600' : 'text-red-600'
          }`}
        >
          {isIncrease ? '+' : ''}
          {changePercent.toFixed(1)}%
        </p>
        <p className="text-xs text-gray-400 flex items-center gap-1 justify-end">
          <Clock className="w-3 h-3" />
          {formatDistanceToNow(new Date(recommendation.created_at), { addSuffix: true })}
        </p>
      </div>
    </Link>
  );
}

export function PendingRecommendations({
  recommendations,
  isLoading,
  maxItems = 5,
}: PendingRecommendationsProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-16 bg-gray-100 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (recommendations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-gray-500">
        <DollarSign className="w-8 h-8 mb-2 text-gray-400" />
        <p className="text-sm">No pending recommendations</p>
        <p className="text-xs text-gray-400 mt-1">
          Recommendations will appear here when generated
        </p>
      </div>
    );
  }

  const displayItems = recommendations.slice(0, maxItems);

  return (
    <div className="space-y-3">
      {displayItems.map((rec) => (
        <RecommendationRow key={rec.id} recommendation={rec} />
      ))}
      {recommendations.length > maxItems && (
        <Link
          href="/pricing"
          className="block text-center text-sm text-blue-600 hover:text-blue-700 py-2"
        >
          View all {recommendations.length} recommendations →
        </Link>
      )}
    </div>
  );
}
