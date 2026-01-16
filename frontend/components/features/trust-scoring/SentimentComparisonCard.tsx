// frontend/components/features/trust-scoring/SentimentComparisonCard.tsx

'use client';

import { Card } from '@/components/ui/Card';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Shield } from 'lucide-react';
import type { WeightedSentimentResponse } from '@/types/trust-scoring';

interface SentimentComparisonCardProps {
  data: WeightedSentimentResponse;
  className?: string;
}

function formatSentiment(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(1)}%`;
}

function getSentimentColor(value: number): string {
  if (value >= 0.2) return 'text-green-600';
  if (value >= 0) return 'text-green-500';
  if (value >= -0.2) return 'text-red-500';
  return 'text-red-600';
}

function getSentimentBgColor(value: number): string {
  if (value >= 0.2) return 'bg-green-100';
  if (value >= 0) return 'bg-green-50';
  if (value >= -0.2) return 'bg-red-50';
  return 'bg-red-100';
}

export function SentimentComparisonCard({ data, className = '' }: SentimentComparisonCardProps) {
  const { raw, adjusted, quality, trust_breakdown, campaign_detected } = data;
  
  const shift = adjusted.sentiment - raw.sentiment;
  const shiftPercent = raw.sentiment !== 0 
    ? Math.round((shift / Math.abs(raw.sentiment)) * 100) 
    : 0;
  
  const isSignificantShift = Math.abs(shift) >= 0.05;

  return (
    <Card className={`p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Trust-Adjusted Sentiment</h3>
        {campaign_detected && (
          <div className="flex items-center gap-1.5 px-2 py-1 bg-red-100 rounded-full">
            <AlertTriangle size={14} className="text-red-600" />
            <span className="text-xs font-medium text-red-700">Campaign Detected</span>
          </div>
        )}
      </div>

      {/* Sentiment Comparison */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Raw Sentiment */}
        <div className={`p-4 rounded-lg ${getSentimentBgColor(raw.sentiment)}`}>
          <p className="text-sm text-gray-600 mb-1">Raw Sentiment</p>
          <p className={`text-2xl font-bold ${getSentimentColor(raw.sentiment)}`}>
            {formatSentiment(raw.sentiment)}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {raw.mention_count} mentions
          </p>
        </div>

        {/* Adjusted Sentiment */}
        <div className={`p-4 rounded-lg ${getSentimentBgColor(adjusted.sentiment)}`}>
          <div className="flex items-center gap-2 mb-1">
            <p className="text-sm text-gray-600">Adjusted Sentiment</p>
            <Shield size={14} className="text-blue-500" />
          </div>
          <p className={`text-2xl font-bold ${getSentimentColor(adjusted.sentiment)}`}>
            {formatSentiment(adjusted.sentiment)}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {adjusted.effective_mentions.toFixed(1)} effective mentions
          </p>
        </div>
      </div>

      {/* Shift Indicator */}
      {isSignificantShift && (
        <div className={`flex items-center gap-2 p-3 rounded-lg mb-6 ${
          shift > 0 ? 'bg-green-50' : 'bg-red-50'
        }`}>
          {shift > 0 ? (
            <TrendingUp size={18} className="text-green-600" />
          ) : shift < 0 ? (
            <TrendingDown size={18} className="text-red-600" />
          ) : (
            <Minus size={18} className="text-gray-600" />
          )}
          <span className={`text-sm font-medium ${
            shift > 0 ? 'text-green-700' : 'text-red-700'
          }`}>
            {shift > 0 ? 'Sentiment improved' : 'Sentiment decreased'} by {Math.abs(shiftPercent)}% 
            after filtering bots/spam
          </span>
        </div>
      )}

      {/* Quality Metrics */}
      <div className="border-t pt-4">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Quality Metrics</h4>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-gray-500">High Trust Ratio</p>
            <p className="text-lg font-semibold text-gray-900">
              {Math.round(quality.high_trust_ratio * 100)}%
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Filtered Out</p>
            <p className="text-lg font-semibold text-gray-900">
              {quality.filtered_count}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Confidence</p>
            <p className="text-lg font-semibold text-gray-900">
              {Math.round(quality.confidence * 100)}%
            </p>
          </div>
        </div>
      </div>

      {/* Trust Breakdown */}
      <div className="border-t pt-4 mt-4">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Trust Distribution</h4>
        <TrustBreakdownBar breakdown={trust_breakdown} />
      </div>
    </Card>
  );
}

// Trust breakdown horizontal stacked bar
interface TrustBreakdownBarProps {
  breakdown: WeightedSentimentResponse['trust_breakdown'];
}

function TrustBreakdownBar({ breakdown }: TrustBreakdownBarProps) {
  const total = Object.values(breakdown).reduce((sum, val) => sum + val, 0);
  
  if (total === 0) {
    return <p className="text-sm text-gray-400">No data</p>;
  }

  const segments = [
    { key: 'verified', label: 'Verified', color: 'bg-blue-500', count: breakdown.verified },
    { key: 'high', label: 'High', color: 'bg-green-500', count: breakdown.high },
    { key: 'medium', label: 'Medium', color: 'bg-yellow-500', count: breakdown.medium },
    { key: 'low', label: 'Low', color: 'bg-orange-500', count: breakdown.low },
    { key: 'untrusted', label: 'Untrusted', color: 'bg-red-500', count: breakdown.untrusted },
    { key: 'blocked', label: 'Blocked', color: 'bg-gray-500', count: breakdown.blocked },
  ].filter(s => s.count > 0);

  return (
    <div>
      {/* Stacked bar */}
      <div className="flex h-3 rounded-full overflow-hidden mb-2">
        {segments.map(({ key, color, count }) => (
          <div
            key={key}
            className={`${color} transition-all duration-300`}
            style={{ width: `${(count / total) * 100}%` }}
          />
        ))}
      </div>
      
      {/* Legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {segments.map(({ key, label, color, count }) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-full ${color}`} />
            <span className="text-xs text-gray-600">
              {label}: {count} ({Math.round((count / total) * 100)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Compact version for dashboard cards
interface SentimentComparisonMiniProps {
  rawSentiment: number;
  adjustedSentiment: number;
  className?: string;
}

export function SentimentComparisonMini({ 
  rawSentiment, 
  adjustedSentiment,
  className = '' 
}: SentimentComparisonMiniProps) {
  const shift = adjustedSentiment - rawSentiment;
  const isPositiveShift = shift > 0.02;
  const isNegativeShift = shift < -0.02;

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className="text-center">
        <p className="text-xs text-gray-500">Raw</p>
        <p className={`text-sm font-semibold ${getSentimentColor(rawSentiment)}`}>
          {formatSentiment(rawSentiment)}
        </p>
      </div>
      
      <div className="flex items-center">
        {isPositiveShift ? (
          <TrendingUp size={16} className="text-green-500" />
        ) : isNegativeShift ? (
          <TrendingDown size={16} className="text-red-500" />
        ) : (
          <Minus size={16} className="text-gray-400" />
        )}
      </div>
      
      <div className="text-center">
        <p className="text-xs text-gray-500">Adjusted</p>
        <p className={`text-sm font-semibold ${getSentimentColor(adjustedSentiment)}`}>
          {formatSentiment(adjustedSentiment)}
        </p>
      </div>
    </div>
  );
}

export default SentimentComparisonCard;



