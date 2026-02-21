'use client';

import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import {
  Sparkles,
  Brain,
  Lightbulb,
  BarChart3,
  Clock,
} from 'lucide-react';
import type { AIInsight } from '@/types/trend-analysis';

interface AIInsightPanelProps {
  insight?: AIInsight;
  isLoading?: boolean;
}

export function AIInsightPanel({ insight, isLoading }: AIInsightPanelProps) {
  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <div className="h-5 w-5 bg-gray-200 rounded animate-pulse" />
          <div className="h-6 w-48 bg-gray-200 rounded animate-pulse" />
        </div>
        <div className="h-4 w-full bg-gray-200 rounded animate-pulse mb-2" />
        <div className="h-4 w-3/4 bg-gray-200 rounded animate-pulse mb-4" />
        <div className="h-32 w-full bg-gray-200 rounded animate-pulse mb-4" />
        <div className="space-y-2">
          <div className="h-4 w-1/2 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-2/3 bg-gray-200 rounded animate-pulse" />
          <div className="h-4 w-1/2 bg-gray-200 rounded animate-pulse" />
        </div>
      </Card>
    );
  }

  if (!insight) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="h-5 w-5 text-purple-500" />
          <h3 className="text-lg font-semibold">AI Market Insight</h3>
        </div>
        <div className="text-center py-8">
          <Brain className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">
            Run AI analysis to generate market insights
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-purple-500" />
          <h3 className="text-lg font-semibold">{insight.title}</h3>
        </div>
        <Badge variant="info">
          {insight.model_used === 'openai' ? 'GPT-4' : 'Gemini'}
        </Badge>
      </div>

      {/* Summary */}
      <div className="bg-linear-to-r from-purple-50 to-blue-50 rounded-lg p-4 mb-4">
        <p className="text-gray-700 leading-relaxed">{insight.summary}</p>
      </div>

      {/* Detailed Analysis */}
      <div className="mb-4">
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 className="h-4 w-4 text-gray-500" />
          <h4 className="font-medium text-gray-700">Detailed Analysis</h4>
        </div>
        <div className="prose prose-sm max-w-none text-gray-600">
          {insight.detailed_analysis.split('\n').map((paragraph, i) => (
            <p key={i} className="mb-2">
              {paragraph}
            </p>
          ))}
        </div>
      </div>

      {/* Key Factors */}
      {insight.key_factors.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-2">
            <Lightbulb className="h-4 w-4 text-yellow-500" />
            <h4 className="font-medium text-gray-700">Key Factors</h4>
          </div>
          <ul className="space-y-2">
            {insight.key_factors.map((factor, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm text-gray-600"
              >
                <span className="text-purple-500 mt-1">•</span>
                <span>{factor}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-200 text-xs text-gray-500">
        <div className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          <span>
            Generated {new Date(insight.generated_at).toLocaleString()}
          </span>
        </div>
        <span>{insight.data_points_analyzed.toLocaleString()} data points analyzed</span>
      </div>
    </Card>
  );
}



