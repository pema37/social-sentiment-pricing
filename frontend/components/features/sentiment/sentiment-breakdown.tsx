'use client';

import { useMemo } from 'react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import type { SocialMention } from '@/types';

const PIE_COLORS = {
  positive: '#10b981',
  neutral: '#6b7280',
  negative: '#ef4444',
};

function classifySentiment(score: number | null): 'positive' | 'neutral' | 'negative' {
  if (score === null) return 'neutral';
  if (score >= 0.2) return 'positive';
  if (score <= -0.2) return 'negative';
  return 'neutral';
}

interface SentimentBreakdownProps {
  mentions: SocialMention[];
}

export function SentimentBreakdown({ mentions }: SentimentBreakdownProps) {
  const breakdown = useMemo(() => {
    const counts = { positive: 0, neutral: 0, negative: 0 };
    mentions.forEach((m) => {
      counts[classifySentiment(m.sentiment_score)]++;
    });
    return [
      { name: 'Positive', value: counts.positive, color: PIE_COLORS.positive },
      { name: 'Neutral', value: counts.neutral, color: PIE_COLORS.neutral },
      { name: 'Negative', value: counts.negative, color: PIE_COLORS.negative },
    ].filter((d) => d.value > 0);
  }, [mentions]);

  if (mentions.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
        No data available
      </div>
    );
  }

  const total = mentions.length || 1; // Prevent division by zero

  return (
    <div className="flex items-center gap-6">
      <div className="w-44 h-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={breakdown}
              cx="50%"
              cy="50%"
              innerRadius={40}
              outerRadius={65}
              paddingAngle={2}
              dataKey="value"
            >
              {breakdown.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={((value: unknown) => {
                const numValue = typeof value === 'number' ? value : 0;
                const percentage = ((numValue / total) * 100).toFixed(0);
                return [
                  `${numValue} (${percentage}%)`,
                  'Mentions',
                ];
              }) as never}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-col gap-3">
        {breakdown.map((item) => {
          const percentage = (((item.value ?? 0) / total) * 100).toFixed(0);
          return (
            <div key={item.name} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-sm text-gray-600 w-16">{item.name}</span>
              <span className="text-sm font-medium">
                {item.value} ({percentage}%)
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}


