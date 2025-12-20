'use client';

import { memo, useMemo } from 'react';
import { Card } from '@/components/ui';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface MentionVolumeChartProps {
  data: Array<{ timestamp: string; score: number; mention_count: number }>;
  className?: string;
}

function formatDate(timestamp: string): string {
  return new Date(timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export const MentionVolumeChart = memo(function MentionVolumeChart({ data, className }: MentionVolumeChartProps) {
  const chartData = useMemo(() => data.map((point) => ({ date: formatDate(point.timestamp), mentions: point.mention_count })), [data]);

  if (chartData.length === 0) return null;

  return (
    <Card className={className}>
      <div className="p-6">
        <h3 className="text-lg font-medium mb-4">Mention Volume</h3>
        <div className="h-72" role="img" aria-label="Bar chart showing mention volume">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tick={{ fontSize: 12 }} stroke="#9ca3af" tickLine={false} />
              <YAxis tick={{ fontSize: 12 }} stroke="#9ca3af" allowDecimals={false} tickLine={false} axisLine={false} />
              <Tooltip 
                formatter={((v: unknown) => [v, 'Mentions']) as never} 
                contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb' }} 
                cursor={{ fill: 'rgba(59, 130, 246, 0.1)' }} 
              />
              <Bar dataKey="mentions" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Card>
  );
});

