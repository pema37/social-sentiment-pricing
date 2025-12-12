// Sentiment overview widget for dashboard
'use client';

import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface SentimentOverviewProps {
  trend: 'improving' | 'declining' | 'stable';
  score: number | null;
  mentions24h: number;
  isLoading?: boolean;
}

const trendConfig = {
  improving: {
    icon: TrendingUp,
    color: 'text-green-500',
    bgColor: 'bg-green-50',
    label: 'Improving',
  },
  declining: {
    icon: TrendingDown,
    color: 'text-red-500',
    bgColor: 'bg-red-50',
    label: 'Declining',
  },
  stable: {
    icon: Minus,
    color: 'text-gray-500',
    bgColor: 'bg-gray-50',
    label: 'Stable',
  },
};

export function SentimentOverview({
  trend,
  score,
  mentions24h,
  isLoading,
}: SentimentOverviewProps) {
  const config = trendConfig[trend];
  const Icon = config.icon;

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="h-5 w-32 bg-gray-200 rounded animate-pulse" />
            <div className="h-8 w-24 bg-gray-100 rounded animate-pulse mt-2" />
          </div>
          <div className="text-right">
            <div className="h-4 w-20 bg-gray-200 rounded animate-pulse" />
            <div className="h-7 w-16 bg-gray-100 rounded animate-pulse mt-1" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-gray-500">Overall Sentiment</h3>
          <div className="flex items-center gap-3 mt-2">
            <div className={`p-2 rounded-lg ${config.bgColor}`}>
              <Icon className={`w-5 h-5 ${config.color}`} />
            </div>
            <div>
              <p className="text-lg font-semibold text-gray-900">{config.label}</p>
              {score !== null && (
                <p
                  className={`text-sm font-medium ${
                    score >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {score >= 0 ? '+' : ''}
                  {score.toFixed(2)} avg score
                </p>
              )}
            </div>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-500">24h Mentions</p>
          <p className="text-2xl font-semibold text-gray-900">
            {mentions24h.toLocaleString()}
          </p>
        </div>
      </div>
    </div>
  );
}
