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

export function SentimentTrendChart({ productId, days = 30 }: SentimentTrendChartProps) {
  const { data, isLoading } = useSentimentTrend({ product_id: productId, days });

  const chartData = useMemo(() => {
    if (!data?.timeline) return [];
    
    return data.timeline.map((point) => ({
      date: new Date(point.timestamp).toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
      }),
      score: point.score,
      mentions: point.mention_count,
    }));
  }, [data]);

  const trendConfig: Record<string, { icon: React.ElementType; color: string; label: string }> = {
    up: { icon: TrendingUp, color: 'text-green-500', label: 'Improving' },
    down: { icon: TrendingDown, color: 'text-red-500', label: 'Declining' },
    stable: { icon: Minus, color: 'text-gray-500', label: 'Stable' },
  };

  const currentTrend = data?.trend || 'stable';
  const TrendIcon = trendConfig[currentTrend]?.icon || Minus;

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
          <TrendIcon className={`w-5 h-5 ${trendConfig[currentTrend].color}`} />
          <span className={`text-sm font-medium ${trendConfig[currentTrend].color}`}>
            {trendConfig[currentTrend].label}
          </span>
          {typeof data?.change === 'number' && (
            <span className={`text-sm ${data.change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ({data.change >= 0 ? '+' : ''}{data.change.toFixed(2)})
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
                tickFormatter={(value) => (typeof value === 'number' ? value : 0).toFixed(1)}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  fontSize: '12px',
                }}
                formatter={((value: unknown, name: unknown) => {
                  const numValue = typeof value === 'number' ? value : 0;
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
