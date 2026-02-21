// Analytics Page
// Charts and deeper insights into pricing, sentiment, and alerts

'use client';

import { useState } from 'react';
import { SectionHeader, Card, CardTitle } from '@/components/ui';
import { Button } from '@/components/ui/Button';
import {
  SentimentTrendChart,
  RecommendationStatsCard,
  AlertsBreakdownChart,
} from '@/components/features/analytics';
import { useDashboardOverview } from '@/lib/hooks/use-analytics';
import { 
  RefreshCw, 
  Calendar,
  TrendingUp,
  Package,
  Users,
  Bell,
} from 'lucide-react';
import { useRefreshDashboard } from '@/lib/hooks/use-analytics';

type TimeRange = 7 | 14 | 30 | 90;

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>(30);
  const { data: overview, isLoading: overviewLoading, isFetching } = useDashboardOverview();
  const { refresh } = useRefreshDashboard();

  const timeRangeOptions: { value: TimeRange; label: string }[] = [
    { value: 7, label: '7 days' },
    { value: 14, label: '14 days' },
    { value: 30, label: '30 days' },
    { value: 90, label: '90 days' },
  ];

  const summaryStats = [
    {
      label: 'Total Products',
      value: overview?.total_products ?? 0,
      icon: Package,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50',
    },
    {
      label: 'Competitors Tracked',
      value: overview?.total_competitors ?? 0,
      icon: Users,
      color: 'text-purple-600',
      bgColor: 'bg-purple-50',
    },
    {
      label: 'Pending Recommendations',
      value: overview?.pending_recommendations ?? 0,
      icon: TrendingUp,
      color: 'text-green-600',
      bgColor: 'bg-green-50',
    },
    {
      label: 'Unread Alerts',
      value: overview?.unread_alerts ?? 0,
      icon: Bell,
      color: 'text-amber-600',
      bgColor: 'bg-amber-50',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <SectionHeader
        title="Analytics"
        description="Insights into your pricing, sentiment, and alerts"
        action={
          <div className="flex items-center gap-3">
            {/* Time Range Selector */}
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {timeRangeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setTimeRange(option.value)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                    timeRange === option.value
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            {/* Refresh Button */}
            <Button
              variant="secondary"
              size="sm"
              onClick={refresh}
              disabled={isFetching}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        }
      />

      {/* Summary Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryStats.map((stat) => (
          <Card key={stat.label}>
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${stat.bgColor}`}>
                <stat.icon className={`w-5 h-5 ${stat.color}`} />
              </div>
              <div>
                {overviewLoading ? (
                  <div className="h-6 w-12 bg-gray-200 rounded animate-pulse" />
                ) : (
                  <p className="text-xl font-semibold text-gray-900">{stat.value}</p>
                )}
                <p className="text-xs text-gray-500">{stat.label}</p>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Sentiment Trend Chart */}
      <SentimentTrendChart days={timeRange} />

      {/* Recommendation Stats */}
      <RecommendationStatsCard days={timeRange} />

      {/* Alert Analytics */}
      <AlertsBreakdownChart days={timeRange} />

      {/* Additional Insights Card */}
      <Card>
        <CardTitle>Key Insights</CardTitle>
        <p className="text-sm text-gray-500 mt-1">
          Automated observations based on your data
        </p>

        <div className="mt-4 space-y-3">
          {overviewLoading ? (
            <>
              <div className="h-12 bg-gray-100 rounded-lg animate-pulse" />
              <div className="h-12 bg-gray-100 rounded-lg animate-pulse" />
              <div className="h-12 bg-gray-100 rounded-lg animate-pulse" />
            </>
          ) : (
            <>
              {/* Sentiment Insight */}
              <div className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                <div className={`p-1.5 rounded-full ${
                  overview?.sentiment_trend === 'improving' 
                    ? 'bg-green-100' 
                    : overview?.sentiment_trend === 'declining'
                    ? 'bg-red-100'
                    : 'bg-gray-100'
                }`}>
                  <TrendingUp className={`w-4 h-4 ${
                    overview?.sentiment_trend === 'improving'
                      ? 'text-green-600'
                      : overview?.sentiment_trend === 'declining'
                      ? 'text-red-600'
                      : 'text-gray-600'
                  }`} />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    Sentiment is {overview?.sentiment_trend || 'stable'}
                  </p>
                  <p className="text-xs text-gray-500">
                    {overview?.total_mentions_24h?.toLocaleString() || 0} mentions in the last 24 hours
                  </p>
                </div>
              </div>

              {/* Recommendations Insight */}
              <div className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                <div className={`p-1.5 rounded-full ${
                  (overview?.pending_recommendations ?? 0) > 0 
                    ? 'bg-amber-100' 
                    : 'bg-green-100'
                }`}>
                  <Calendar className={`w-4 h-4 ${
                    (overview?.pending_recommendations ?? 0) > 0 
                      ? 'text-amber-600' 
                      : 'text-green-600'
                  }`} />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {(overview?.pending_recommendations ?? 0) > 0
                      ? `${overview?.pending_recommendations} recommendations awaiting review`
                      : 'All recommendations reviewed'}
                  </p>
                  <p className="text-xs text-gray-500">
                    {overview?.applied_recommendations_7d || 0} applied in the last 7 days
                  </p>
                </div>
              </div>

              {/* Auto-pricing Insight */}
              <div className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                <div className="p-1.5 rounded-full bg-blue-100">
                  <Package className="w-4 h-4 text-blue-600" />
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {overview?.products_with_auto_pricing || 0} of {overview?.total_products || 0} products with auto-pricing
                  </p>
                  <p className="text-xs text-gray-500">
                    {overview?.total_products && overview.total_products > 0 && overview?.products_with_auto_pricing != null
                      ? `${(((overview.products_with_auto_pricing ?? 0) / overview.total_products) * 100).toFixed(0)}% coverage`
                      : '0% coverage'}
                  </p>
                </div>
              </div>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}

