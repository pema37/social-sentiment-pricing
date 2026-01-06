// Recommendation statistics card
'use client';

import { Card, CardTitle } from '@/components/ui';
import { useRecommendationStats } from '@/lib/hooks/use-analytics';
import { 
  Clock, 
  CheckCircle, 
  XCircle, 
  Zap, 
  AlertCircle,
  TrendingUp,
  Percent,
} from 'lucide-react';

interface RecommendationStatsCardProps {
  days?: number;
}

export function RecommendationStatsCard({ days = 30 }: RecommendationStatsCardProps) {
  const { data, isLoading } = useRecommendationStats(days);

  const stats = [
    {
      label: 'Pending',
      value: data?.total_pending ?? 0,
      icon: Clock,
      color: 'text-amber-600',
      bgColor: 'bg-amber-50',
    },
    {
      label: 'Approved',
      value: data?.total_approved ?? 0,
      icon: CheckCircle,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      label: 'Applied',
      value: data?.total_applied ?? 0,
      icon: Zap,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      label: 'Rejected',
      value: data?.total_rejected ?? 0,
      icon: XCircle,
      color: 'text-red-600',
      bgColor: 'bg-red-50',
    },
    {
      label: 'Expired',
      value: data?.total_expired ?? 0,
      icon: AlertCircle,
      color: 'text-gray-600',
      bgColor: 'bg-gray-50',
    },
  ];

  if (isLoading) {
    return (
      <Card>
        <CardTitle>Recommendation Stats</CardTitle>
        <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <CardTitle>Recommendation Stats</CardTitle>
          <p className="text-sm text-gray-500 mt-1">Last {days} days</p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-4">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="flex flex-col items-center p-3 rounded-lg border border-gray-100"
          >
            <div className={`p-2 rounded-lg ${stat.bgColor} mb-2`}>
              <stat.icon className={`w-5 h-5 ${stat.color}`} />
            </div>
            <p className="text-2xl font-semibold text-gray-900">{stat.value}</p>
            <p className="text-xs text-gray-500">{stat.label}</p>
          </div>
        ))}
      </div>

      {/* Additional Metrics */}
      <div className="mt-6 pt-4 border-t border-gray-100 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
          <div className="p-2 rounded-lg bg-white">
            <TrendingUp className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500">Avg Confidence</p>
            <p className="text-lg font-semibold text-gray-900">
              {data?.avg_confidence_score != null 
                ? `${(Number(data.avg_confidence_score ?? 0) * 100).toFixed(0)}%` 
                : 'N/A'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
          <div className="p-2 rounded-lg bg-white">
            <Percent className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500">Avg Price Change</p>
            <p className="text-lg font-semibold text-gray-900">
              {data?.avg_adjustment_percent != null 
                ? `${data.avg_adjustment_percent >= 0 ? '+' : ''}${(Number(data.avg_adjustment_percent ?? 0)).toFixed(1)}%` 
                : 'N/A'}
            </p>
          </div>
        </div>
      </div>
    </Card>
  );
}
