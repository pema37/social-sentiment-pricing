'use client';

import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  MessageSquare,
  AlertTriangle,
  Lightbulb,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import type { QuickStatsResponse } from '@/types/trend-analysis';
import { getTrendDisplayInfo, formatPercentChange } from '@/types/trend-analysis';

interface QuickStatsGridProps {
  data?: QuickStatsResponse;
  isLoading?: boolean;
}

export function QuickStatsGrid({ data, isLoading }: QuickStatsGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="p-4">
            <div className="h-4 w-24 mb-2 bg-gray-200 rounded animate-pulse" />
            <div className="h-8 w-16 mb-1 bg-gray-200 rounded animate-pulse" />
            <div className="h-3 w-20 bg-gray-200 rounded animate-pulse" />
          </Card>
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 text-center text-gray-500">
          No data available
        </Card>
      </div>
    );
  }

  const trendInfo = getTrendDisplayInfo(data.sentiment_trend);
  const TrendIcon =
    data.sentiment_trend === 'rising'
      ? TrendingUp
      : data.sentiment_trend === 'falling'
      ? TrendingDown
      : Minus;

  const getTrendBadgeVariant = () => {
    if (data.sentiment_trend === 'rising') return 'success';
    if (data.sentiment_trend === 'falling') return 'danger';
    return 'default';
  };

  const getRiskBadgeVariant = () => {
    if (data.highest_risk_level === 'critical' || data.highest_risk_level === 'high') return 'danger';
    if (data.highest_risk_level === 'medium') return 'warning';
    return 'success';
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Sentiment Card */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-600">Market Sentiment</span>
          <Activity className="h-4 w-4 text-gray-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold">
            {data.current_sentiment > 0 ? '+' : ''}
            {data.current_sentiment.toFixed(1)}
          </span>
          <Badge variant={getTrendBadgeVariant()}>
            <TrendIcon className="h-3 w-3 mr-1" />
            {trendInfo.label}
          </Badge>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {formatPercentChange(data.sentiment_change_7d)} from last week
        </p>
      </Card>

      {/* Volume Card */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-600">Mention Volume</span>
          <MessageSquare className="h-4 w-4 text-gray-400" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold">{data.mentions_7d.toLocaleString()}</span>
          <span className="text-sm text-gray-500">this week</span>
        </div>
        <div className="flex items-center gap-1 mt-1">
          {data.volume_change_percent >= 0 ? (
            <ArrowUp className="h-3 w-3 text-green-500" />
          ) : (
            <ArrowDown className="h-3 w-3 text-red-500" />
          )}
          <span
            className={`text-xs ${
              data.volume_change_percent >= 0 ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {formatPercentChange(data.volume_change_percent)} vs last week
          </span>
        </div>
      </Card>

      {/* Opportunities Card */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-600">Opportunities</span>
          <Lightbulb className="h-4 w-4 text-yellow-500" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold">{data.active_opportunities}</span>
          <span className="text-sm text-gray-500">active</span>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          Potential impact: {data.potential_revenue_impact}
        </p>
      </Card>

      {/* Risks Card */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-600">Active Risks</span>
          <AlertTriangle
            className={`h-4 w-4 ${
              data.highest_risk_level === 'critical'
                ? 'text-red-500'
                : data.highest_risk_level === 'high'
                ? 'text-orange-500'
                : data.highest_risk_level === 'medium'
                ? 'text-yellow-500'
                : 'text-green-500'
            }`}
          />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold">{data.active_risks}</span>
          {data.active_risks > 0 && (
            <Badge variant={getRiskBadgeVariant()}>
              {data.highest_risk_level}
            </Badge>
          )}
        </div>
        {data.active_risks === 0 && (
          <p className="text-xs text-green-600 mt-1">All clear!</p>
        )}
      </Card>

      {/* Trending Products - Up */}
      {data.trending_up.length > 0 && (
        <Card className="p-4 md:col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="h-4 w-4 text-green-500" />
            <span className="text-sm font-medium text-gray-600">Trending Up</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.trending_up.map((product) => (
              <Badge key={product} variant="success">
                {product}
              </Badge>
            ))}
          </div>
        </Card>
      )}

      {/* Trending Products - Down */}
      {data.trending_down.length > 0 && (
        <Card className="p-4 md:col-span-2">
          <div className="flex items-center gap-2 mb-3">
            <TrendingDown className="h-4 w-4 text-red-500" />
            <span className="text-sm font-medium text-gray-600">Trending Down</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.trending_down.map((product) => (
              <Badge key={product} variant="danger">
                {product}
              </Badge>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}


