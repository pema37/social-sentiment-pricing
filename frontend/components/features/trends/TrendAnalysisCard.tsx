'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  Sparkles,
  Play,
  RefreshCw,
  CheckCircle,
  Clock,
  Brain,
  Zap,
} from 'lucide-react';
import type { TrendAnalysisResponse } from '@/types/trend-analysis';
import { getTrendDisplayInfo } from '@/types/trend-analysis';

interface TrendAnalysisCardProps {
  analysis?: TrendAnalysisResponse;
  isLoading?: boolean;
  onRunAnalysis?: (params: { days: number; useModel: 'openai' | 'gemini' }) => void;
}

export function TrendAnalysisCard({
  analysis,
  isLoading,
  onRunAnalysis,
}: TrendAnalysisCardProps) {
  const [days, setDays] = useState(30);
  const [model, setModel] = useState<'openai' | 'gemini'>('openai');

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="animate-spin">
            <RefreshCw className="h-6 w-6 text-blue-500" />
          </div>
          <div>
            <h3 className="text-lg font-semibold">Running AI Analysis...</h3>
            <p className="text-sm text-gray-500">This may take a moment</p>
          </div>
        </div>
        <div className="space-y-3">
          <div className="h-4 w-full bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-3/4 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-1/2 bg-gray-200 rounded animate-pulse" />
        </div>
      </Card>
    );
  }

  // Show analysis trigger if no analysis
  if (!analysis) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="h-5 w-5 text-purple-500" />
          <h3 className="text-lg font-semibold">AI Trend Analysis</h3>
        </div>

        <p className="text-gray-600 mb-6">
          Use AI to analyze your market data and get actionable insights,
          predictions, and risk alerts.
        </p>

        {/* Configuration */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          {/* Time Period */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">
              Analysis Period
            </label>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
              <option value={60}>Last 60 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>

          {/* AI Model */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">
              AI Model
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value as 'openai' | 'gemini')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="openai">OpenAI GPT-4</option>
              <option value="gemini">Google Gemini</option>
            </select>
          </div>
        </div>

        {/* Run Button */}
        <Button
          onClick={() => onRunAnalysis?.({ days, useModel: model })}
          variant="primary"
          className="w-full flex items-center justify-center gap-2"
          size="lg"
        >
          <Play className="h-4 w-4" />
          Run AI Analysis
        </Button>

        {/* Info */}
        <div className="mt-4 flex items-center gap-2 text-xs text-gray-500">
          <Brain className="h-4 w-4" />
          <span>
            Analysis uses {model === 'openai' ? 'GPT-4o-mini' : 'Gemini 1.5 Flash'} for
            fast, accurate insights
          </span>
        </div>
      </Card>
    );
  }

  // Show analysis results summary
  const trendInfo = getTrendDisplayInfo(analysis.market_sentiment);

  return (
    <Card className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-purple-500" />
          <h3 className="text-lg font-semibold">AI Analysis Results</h3>
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onRunAnalysis?.({ days, useModel: model })}
          className="flex items-center gap-1"
        >
          <RefreshCw className="h-3 w-3" />
          Refresh
        </Button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold">
            {analysis.predictions.length}
          </div>
          <div className="text-xs text-gray-500">Predictions</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-green-600">
            {analysis.opportunities.length}
          </div>
          <div className="text-xs text-gray-500">Opportunities</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-orange-600">
            {analysis.risks.length}
          </div>
          <div className="text-xs text-gray-500">Risks</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className={`text-2xl font-bold ${trendInfo.color}`}>
            {analysis.market_sentiment_score > 0 ? '+' : ''}
            {analysis.market_sentiment_score.toFixed(0)}
          </div>
          <div className="text-xs text-gray-500">Sentiment</div>
        </div>
      </div>

      {/* Executive Summary */}
      <div className="bg-linear-to-r from-blue-50 to-purple-50 rounded-lg p-4 mb-4">
        <h4 className="font-medium text-gray-700 mb-2 flex items-center gap-2">
          <Zap className="h-4 w-4 text-yellow-500" />
          Executive Summary
        </h4>
        <p className="text-sm text-gray-600">{analysis.executive_summary}</p>
      </div>

      {/* Recommended Actions */}
      {analysis.recommended_actions.length > 0 && (
        <div>
          <h4 className="font-medium text-gray-700 mb-2">Recommended Actions</h4>
          <ul className="space-y-2">
            {analysis.recommended_actions.slice(0, 5).map((action, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm text-gray-600"
              >
                <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                <span>{action}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Metadata */}
      <div className="mt-4 pt-4 border-t border-gray-200 flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          <span>
            Generated {new Date(analysis.generated_at).toLocaleString()}
          </span>
        </div>
        <span>
          {analysis.products_analyzed} products • {analysis.mentions_analyzed}{' '}
          mentions • {analysis.time_range_days} days
        </span>
      </div>
    </Card>
  );
}


