// Sentiment Page
'use client';

import { useState } from 'react';
import { SectionHeader, Card } from '@/components/ui';
import { useSentimentTrend, useDashboardOverview } from '@/lib/hooks/use-analytics';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';

// Format date for chart labels
function formatDate(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// Trend indicator component
function TrendBadge({ trend, change }: { trend: string; change: number | null }) {
  const colors = {
    up: 'bg-green-100 text-green-800',
    down: 'bg-red-100 text-red-800',
    stable: 'bg-gray-100 text-gray-800',
  };
  
  const icons = {
    up: '↑',
    down: '↓',
    stable: '→',
  };
  
  const trendKey = trend as keyof typeof colors;
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm font-medium ${colors[trendKey]}`}>
      {icons[trendKey]}
      {change !== null && ` ${Math.abs(change * 100).toFixed(1)}%`}
    </span>
  );
}

// KPI Card component
function KpiCard({ 
  title, 
  value, 
  subtitle,
  trend,
  change,
}: { 
  title: string; 
  value: string | number; 
  subtitle?: string;
  trend?: string;
  change?: number | null;
}) {
  return (
    <Card className="p-6">
      <p className="text-sm text-gray-500 mb-1">{title}</p>
      <div className="flex items-center gap-3">
        <p className="text-3xl font-semibold">{value}</p>
        {trend && <TrendBadge trend={trend} change={change ?? null} />}
      </div>
      {subtitle && <p className="text-sm text-gray-400 mt-1">{subtitle}</p>}
    </Card>
  );
}

// Period selector
function PeriodSelector({ 
  value, 
  onChange 
}: { 
  value: number; 
  onChange: (days: number) => void;
}) {
  const periods = [
    { label: '7 days', days: 7 },
    { label: '30 days', days: 30 },
    { label: '90 days', days: 90 },
  ];
  
  return (
    <div className="flex gap-2">
      {periods.map((period) => (
        <button
          key={period.days}
          onClick={() => onChange(period.days)}
          className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
            value === period.days
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          {period.label}
        </button>
      ))}
    </div>
  );
}

export default function SentimentPage() {
  const [days, setDays] = useState(30);
  
  // Fetch sentiment trend data
  const { data: trendData, isLoading: trendLoading, error: trendError } = useSentimentTrend({ 
    days, 
    bucket: days <= 7 ? 'day' : 'day' 
  });
  
  // Fetch dashboard overview for additional context
  const { data: dashboardData } = useDashboardOverview();
  
  // Prepare chart data
  const chartData = trendData?.timeline.map((point) => ({
    date: formatDate(point.timestamp),
    score: point.score,
    mentions: point.mention_count,
  })) || [];
  
  // Calculate sentiment label
  const getSentimentLabel = (score: number | null | undefined): string => {
    if (score === null || score === undefined) return 'No data';
    if (score >= 0.5) return 'Positive';
    if (score >= 0) return 'Neutral';
    return 'Negative';
  };
  
  // Format score for display
  const formatScore = (score: number | null | undefined): string => {
    if (score === null || score === undefined) return '—';
    return (score * 100).toFixed(0);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <SectionHeader
          title="Sentiment Analysis"
          description="Track social media sentiment for your products"
        />
        <PeriodSelector value={days} onChange={setDays} />
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KpiCard
          title="Current Sentiment"
          value={formatScore(trendData?.current_score)}
          subtitle={getSentimentLabel(trendData?.current_score)}
          trend={trendData?.trend}
          change={trendData?.change}
        />
        <KpiCard
          title="Previous Period"
          value={formatScore(trendData?.previous_score)}
          subtitle={getSentimentLabel(trendData?.previous_score)}
        />
        <KpiCard
          title="Total Mentions"
          value={chartData.reduce((sum, d) => sum + d.mentions, 0)}
          subtitle={`Last ${days} days`}
        />
        <KpiCard
          title="Mentions (24h)"
          value={dashboardData?.total_mentions_24h ?? 0}
          subtitle="Today"
        />
      </div>

      {/* Loading state */}
      {trendLoading && (
        <Card className="p-8">
          <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        </Card>
      )}

      {/* Error state */}
      {trendError && (
        <Card className="p-8">
          <div className="flex items-center justify-center h-64 text-red-500">
            Failed to load sentiment data: {trendError.message}
          </div>
        </Card>
      )}

      {/* Charts */}
      {!trendLoading && !trendError && chartData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Sentiment Score Chart */}
          <Card className="p-6">
            <h3 className="text-lg font-medium mb-4">Sentiment Score Over Time</h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
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
                    tickFormatter={(value) => (value * 100).toFixed(0)}
                  />
                  <Tooltip 
                    formatter={(value: number) => [(value * 100).toFixed(1), 'Score']}
                    labelStyle={{ color: '#374151' }}
                    contentStyle={{ 
                      borderRadius: '8px', 
                      border: '1px solid #e5e7eb',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="score"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ fill: '#3b82f6', strokeWidth: 2, r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Mention Volume Chart */}
          <Card className="p-6">
            <h3 className="text-lg font-medium mb-4">Mention Volume</h3>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis 
                    dataKey="date" 
                    tick={{ fontSize: 12 }}
                    stroke="#9ca3af"
                  />
                  <YAxis 
                    tick={{ fontSize: 12 }}
                    stroke="#9ca3af"
                    allowDecimals={false}
                  />
                  <Tooltip 
                    formatter={(value: number) => [value, 'Mentions']}
                    labelStyle={{ color: '#374151' }}
                    contentStyle={{ 
                      borderRadius: '8px', 
                      border: '1px solid #e5e7eb',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'
                    }}
                  />
                  <Bar 
                    dataKey="mentions" 
                    fill="#10b981" 
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>
      )}

      {/* Empty state */}
      {!trendLoading && !trendError && chartData.length === 0 && (
        <Card className="p-8">
          <div className="flex flex-col items-center justify-center h-64 text-gray-500">
            <svg className="w-12 h-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <p className="text-lg font-medium">No sentiment data yet</p>
            <p className="text-sm mt-1">Sentiment data will appear here once you start analyzing content</p>
          </div>
        </Card>
      )}
    </div>
  );
}
