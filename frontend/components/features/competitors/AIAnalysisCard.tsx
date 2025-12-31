// components/features/competitors/AIAnalysisCard.tsx
'use client';

import { useState } from 'react';
import { Brain, RefreshCw, TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api/client';

interface AIAnalysisResponse {
  competitor_id: string;
  competitor_name: string;
  strategy_detected: string;
  analysis: string;
  recommended_response: string;
  confidence: number;
  ai_powered: boolean;
}

interface AIAnalysisCardProps {
  competitorId: string;
  competitorName: string;
}

const strategyConfig: Record<string, { label: string; color: string; icon: typeof TrendingUp }> = {
  aggressive: { label: 'Aggressive', color: 'text-red-600 bg-red-50', icon: TrendingDown },
  premium: { label: 'Premium', color: 'text-purple-600 bg-purple-50', icon: TrendingUp },
  discount: { label: 'Discount', color: 'text-orange-600 bg-orange-50', icon: TrendingDown },
  stable: { label: 'Stable', color: 'text-green-600 bg-green-50', icon: Minus },
  unknown: { label: 'Unknown', color: 'text-gray-600 bg-gray-50', icon: AlertTriangle },
};

export function AIAnalysisCard({ competitorId, competitorName }: AIAnalysisCardProps) {
  const [analysis, setAnalysis] = useState<AIAnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalysis = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const data = await api.get<AIAnalysisResponse>(
        `/api/v1/competitors/${competitorId}/ai-analysis`
      );
      setAnalysis(data);
    } catch (err) {
      setError((err as Error).message || 'Failed to generate analysis');
    } finally {
      setIsLoading(false);
    }
  };

  const strategy = analysis ? strategyConfig[analysis.strategy_detected] || strategyConfig.unknown : null;
  const StrategyIcon = strategy?.icon || Minus;

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-purple-100 rounded-lg">
            <Brain className="h-5 w-5 text-purple-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">AI Strategy Analysis</h3>
            <p className="text-xs text-gray-500">Powered by GPT-4o-mini</p>
          </div>
        </div>
        
        {analysis && (
          <button
            onClick={fetchAnalysis}
            disabled={isLoading}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      {!analysis && !isLoading && !error && (
        <div className="text-center py-6">
          <p className="text-gray-500 text-sm mb-4">
            Get AI-powered insights into {competitorName}&apos;s pricing strategy
          </p>
          <Button onClick={fetchAnalysis} disabled={isLoading}>
            <Brain className="h-4 w-4 mr-2" />
            Analyze Strategy
          </Button>
        </div>
      )}

      {isLoading && (
        <div className="py-8 text-center">
          <RefreshCw className="h-8 w-8 text-purple-500 animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Analyzing pricing patterns...</p>
        </div>
      )}

      {error && (
        <div className="py-6 text-center">
          <p className="text-red-600 text-sm mb-3">{error}</p>
          <Button variant="secondary" onClick={fetchAnalysis}>
            Try Again
          </Button>
        </div>
      )}

      {analysis && !isLoading && (
        <div className="space-y-4">
          {/* Strategy Badge */}
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500">Detected Strategy:</span>
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${strategy?.color}`}>
              <StrategyIcon className="h-4 w-4" />
              {strategy?.label}
            </span>
          </div>

          {/* Analysis */}
          <div className="bg-gray-50 rounded-lg p-4">
            <p className="text-sm text-gray-700 leading-relaxed">{analysis.analysis}</p>
          </div>

          {/* Recommendation */}
          <div className="border-l-4 border-purple-500 pl-4">
            <p className="text-xs font-medium text-purple-600 uppercase mb-1">Recommended Response</p>
            <p className="text-sm text-gray-700">{analysis.recommended_response}</p>
          </div>

          {/* Confidence */}
          <div className="flex items-center gap-3 pt-2">
            <span className="text-xs text-gray-500">Confidence:</span>
            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-500 rounded-full transition-all"
                style={{ width: `${analysis.confidence * 100}%` }}
              />
            </div>
            <span className="text-xs font-medium text-gray-600">
              {(analysis.confidence * 100).toFixed(0)}%
            </span>
          </div>

          {/* AI Badge */}
          {analysis.ai_powered && (
            <div className="flex items-center justify-end gap-1 text-xs text-purple-500">
              <Brain className="h-3 w-3" />
              AI Powered
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

export default AIAnalysisCard;
