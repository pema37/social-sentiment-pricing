'use client';

import { memo, useMemo } from 'react';
import { Card } from '@/components/ui';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface SentimentChartProps {
  data: Array<{ timestamp: string; score: number; mention_count: number }>;
  className?: string;
}

// Helper to safely convert any value to a number (handles strings!)
function toSafeNumber(value: unknown, fallback = 0): number {
  if (value == null) return fallback;
  const num = Number(value);
  return isNaN(num) ? fallback : num;
}

function formatDate(timestamp: string): string {
  return new Date(timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export const SentimentChart = memo(function SentimentChart({ data, className }: SentimentChartProps) {
  const chartData = useMemo(() => data.map((point) => ({ 
    date: formatDate(point.timestamp), 
    // CRITICAL FIX: Number() converts strings to numbers, ?? does NOT
    score: toSafeNumber(point.score)
  })), [data]);

  if (chartData.length === 0) return null;

  return (
    <Card className={className}>
      <div className="p-6">
        <h3 className="text-lg font-medium mb-4">Sentiment Score Over Time</h3>
        <div className="h-72" role="img" aria-label="Line chart showing sentiment score trends">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#9ca3af" tickLine={false} />
              <YAxis 
                domain={[-1, 1]} 
                tick={{ fontSize: 12 }} 
                stroke="#9ca3af" 
                tickFormatter={(v) => (toSafeNumber(v) * 100).toFixed(0)}
                tickLine={false} 
                axisLine={false} 
              />
              <Tooltip 
                formatter={((v: unknown) => [(toSafeNumber(v) * 100).toFixed(1), 'Score']) as never} 
                contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }} 
              />
              <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2} dot={{ fill: '#3b82f6', r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
});

