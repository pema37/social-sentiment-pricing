'use client';

import { Card } from '@/components/ui/Card';
import type { TrendDirection } from '@/types/trend-analysis';
import { getTrendDisplayInfo } from '@/types/trend-analysis';

interface MarketSentimentGaugeProps {
  score: number;
  direction: TrendDirection;
}

export function MarketSentimentGauge({ score, direction }: MarketSentimentGaugeProps) {
  const trendInfo = getTrendDisplayInfo(direction);
  
  // Normalize score from -100/+100 to 0-100 for positioning
  const normalizedScore = (score + 100) / 2;
  
  const getScoreColor = () => {
    if (score >= 50) return 'text-green-600';
    if (score >= 20) return 'text-green-500';
    if (score >= -20) return 'text-gray-600';
    if (score >= -50) return 'text-orange-500';
    return 'text-red-600';
  };

  const getLabel = () => {
    if (score >= 60) return 'Very Bullish';
    if (score >= 30) return 'Bullish';
    if (score >= 10) return 'Slightly Bullish';
    if (score >= -10) return 'Neutral';
    if (score >= -30) return 'Slightly Bearish';
    if (score >= -60) return 'Bearish';
    return 'Very Bearish';
  };

  return (
    <Card className="p-6">
      <h3 className="text-sm font-medium text-gray-600 mb-4">Market Sentiment</h3>
      
      {/* Gauge */}
      <div className="relative h-24 mb-4">
        <svg className="w-full h-full" viewBox="0 0 200 100">
          {/* Background track */}
          <path
            d="M 20 90 A 80 80 0 0 1 180 90"
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="12"
            strokeLinecap="round"
          />
          
          {/* Colored arc based on score */}
          <path
            d="M 20 90 A 80 80 0 0 1 180 90"
            fill="none"
            stroke="url(#gauge-gradient)"
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={`${normalizedScore * 2.51} 251`}
          />
          
          {/* Gradient definition */}
          <defs>
            <linearGradient id="gauge-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ef4444" />
              <stop offset="25%" stopColor="#f97316" />
              <stop offset="50%" stopColor="#6b7280" />
              <stop offset="75%" stopColor="#22c55e" />
              <stop offset="100%" stopColor="#16a34a" />
            </linearGradient>
          </defs>
          
          {/* Needle indicator */}
          <circle
            cx={20 + (160 * normalizedScore / 100)}
            cy={90 - Math.sin(Math.PI * normalizedScore / 100) * 80}
            r="8"
            fill="white"
            stroke="#374151"
            strokeWidth="3"
          />
          
          {/* Labels */}
          <text x="10" y="98" className="text-xs" fill="#9ca3af">-100</text>
          <text x="96" y="20" className="text-xs" fill="#9ca3af">0</text>
          <text x="175" y="98" className="text-xs" fill="#9ca3af">+100</text>
        </svg>
      </div>

      {/* Score Display */}
      <div className="text-center">
        <div className={`text-4xl font-bold ${getScoreColor()}`}>
          {score > 0 ? '+' : ''}{score.toFixed(0)}
        </div>
        <div className="text-sm text-gray-500 mt-1">{getLabel()}</div>
        <div className={`inline-flex items-center gap-1 mt-2 px-2 py-1 rounded-full text-xs ${trendInfo.bgColor} ${trendInfo.color}`}>
          <span>{trendInfo.icon}</span>
          <span>{trendInfo.label}</span>
        </div>
      </div>
    </Card>
  );
}


