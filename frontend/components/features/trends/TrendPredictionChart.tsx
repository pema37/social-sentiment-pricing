'use client';

import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  Calendar,
  Target,
} from 'lucide-react';
import type { TrendPrediction } from '@/types/trend-analysis';
import {
  getTrendDisplayInfo,
  getConfidenceDisplayInfo,
  getCategoryLabel,
  formatPercentChange,
} from '@/types/trend-analysis';

interface TrendPredictionChartProps {
  predictions: TrendPrediction[];
}

export function TrendPredictionChart({ predictions }: TrendPredictionChartProps) {
  if (predictions.length === 0) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="h-5 w-5 text-blue-500" />
          <h3 className="text-lg font-semibold">Trend Predictions</h3>
        </div>
        <div className="text-center py-8">
          <Target className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">No predictions available yet</p>
          <p className="text-sm text-gray-400 mt-1">
            Run AI analysis to generate predictions
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="h-5 w-5 text-blue-500" />
        <h3 className="text-lg font-semibold">Trend Predictions</h3>
        <Badge variant="default" className="ml-auto">
          {predictions.length} prediction{predictions.length !== 1 ? 's' : ''}
        </Badge>
      </div>

      <div className="space-y-4">
        {predictions.map((prediction, index) => {
          const trendInfo = getTrendDisplayInfo(prediction.direction);
          const confidenceInfo = getConfidenceDisplayInfo(prediction.confidence);
          const TrendIcon =
            prediction.direction === 'rising'
              ? TrendingUp
              : prediction.direction === 'falling'
              ? TrendingDown
              : Minus;

          const getTrendBadgeVariant = (): 'success' | 'danger' | 'default' => {
            if (prediction.direction === 'rising') return 'success';
            if (prediction.direction === 'falling') return 'danger';
            return 'default';
          };

          return (
            <div
              key={index}
              className="p-4 bg-gray-50 rounded-lg border border-gray-200"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded ${trendInfo.bgColor}`}>
                    <TrendIcon className={`h-4 w-4 ${trendInfo.color}`} />
                  </div>
                  <Badge variant={getTrendBadgeVariant()}>{getCategoryLabel(prediction.category)}</Badge>
                </div>
                <span
                  className={`text-lg font-bold ${
                    prediction.predicted_change >= 0
                      ? 'text-green-600'
                      : 'text-red-600'
                  }`}
                >
                  {formatPercentChange(prediction.predicted_change)}
                </span>
              </div>

              {/* Visual Bar */}
              <div className="relative h-8 mb-3">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full h-2 bg-gray-200 rounded-full">
                    <div
                      className={`h-full rounded-full ${
                        prediction.predicted_change >= 0
                          ? 'bg-linear-to-r from-green-400 to-green-600'
                          : 'bg-linear-to-r from-red-400 to-red-600'
                      }`}
                      style={{
                        width: `${Math.min(Math.abs(prediction.predicted_change) * 5, 100)}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Reasoning */}
              <p className="text-sm text-gray-600 mb-3">{prediction.reasoning}</p>

              {/* Footer */}
              <div className="flex items-center justify-between text-xs">
                {/* Timeframe */}
                <div className="flex items-center gap-1 text-gray-500">
                  <Calendar className="h-3 w-3" />
                  <span>Next {prediction.timeframe_days} days</span>
                </div>

                {/* Confidence */}
                <div className="flex items-center gap-2">
                  <span className="text-gray-500">Confidence:</span>
                  <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full ${confidenceInfo.color}`}
                      style={{ width: `${prediction.confidence_score}%` }}
                    />
                  </div>
                  <span className="font-medium">{prediction.confidence_score}%</span>
                </div>
              </div>

              {/* Supporting Signals */}
              {prediction.supporting_signals.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-200">
                  <span className="text-xs text-gray-500">Supporting signals:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {prediction.supporting_signals.slice(0, 3).map((signal, i) => (
                      <Badge key={i} variant="default" className="text-xs">
                        {signal.source}: {signal.description}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}


