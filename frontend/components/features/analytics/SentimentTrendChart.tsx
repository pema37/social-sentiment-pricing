// Sentiment trend line chart
'use client';

import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { Card, CardTitle } from '@/components/ui';
import { useSentimentTrend } from '@/lib/hooks/use-analytics';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface SentimentTrendChartProps {
  productId?: string;
  days?: number;
}

// Helper to safely convert any value to a number (handles strings!)
function toSafeNumber(value: unknown, fallback = 0): number {
  if (value == null) return fallback;
  const num = Number(value);
  return isNaN(num) ? fallback : num;
}

export function SentimentTrendChart({ productId, days = 30 }: SentimentTrendChartProps) {
  const { data, isLoading } = useSentimentTrend({ product_id: productId, days });

  const chartData = useMemo(() => {
    if (!data?.timeline) return [];
    
    return data.timeline.map((point) => ({
      date: new Date(point.timestamp).toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
      }),
      // CRITICAL FIX: Number() converts strings to numbers, ?? does NOT
      score: toSafeNumber(point.score),
      mentions: toSafeNumber(point.mention_count),
    }));
  }, [data]);

  const trendConfig: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    up: { icon: TrendingUp, color: 'text-green-500', label: 'Improving' },
    down: { icon: TrendingDown, color: 'text-red-500', label: 'Declining' },
    stable: { icon: Minus, color: 'text-gray-500', label: 'Stable' },
  };

  const currentTrend = data?.trend || 'stable';
  const TrendIcon = trendConfig[currentTrend]?.icon || Minus;

  // Safe change value - must be a real number
  const changeValue = toSafeNumber(data?.change, NaN);
  const hasValidChange = !isNaN(changeValue);

  if (isLoading) {
    return (
      <Card>
        <CardTitle>Sentiment Trend</CardTitle>
        <div className="h-64 mt-4 bg-gray-100 rounded animate-pulse" />
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <CardTitle>Sentiment Trend</CardTitle>
          <p className="text-sm text-gray-500 mt-1">Last {days} days</p>
        </div>
        <div className="flex items-center gap-2">
          <TrendIcon className={`w-5 h-5 ${trendConfig[currentTrend]?.color || 'text-gray-500'}`} />
          <span className={`text-sm font-medium ${trendConfig[currentTrend]?.color || 'text-gray-500'}`}>
            {trendConfig[currentTrend]?.label || 'Stable'}
          </span>
          {hasValidChange && (
            <span className={`text-sm ${changeValue >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ({changeValue >= 0 ? '+' : ''}{changeValue.toFixed(2)})
            </span>
          )}
        </div>
      </div>

      <div className="h-64 mt-4">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="date" 
                tick={{ fontSize: 12 }} 
                stroke="#9ca3af"
              />
              <YAxis 
                domain={[-1, 1]} 
                tick={{ fontSize: 12 }} 
                stroke="#9ca3af"
                tickFormatter={(value) => toSafeNumber(value).toFixed(1)}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={((value: unknown, name: unknown) => {
                  const numValue = toSafeNumber(value);
                  const strName = String(name || '');
                  return [
                    strName === 'score' ? numValue.toFixed(3) : numValue,
                    strName === 'score' ? 'Sentiment' : 'Mentions',
                  ];
                }) as never}
              />
              <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#3b82f6' }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex items-center justify-center text-gray-500">
            <p className="text-sm">No sentiment data available</p>
          </div>
        )}
      </div>
    </Card>
  );
}

