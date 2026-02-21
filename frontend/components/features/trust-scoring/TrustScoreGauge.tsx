// frontend/components/features/trust-scoring/TrustScoreGauge.tsx

'use client';

import { useMemo } from 'react';
import type { TrustLevel } from '@/types/trust-scoring';

interface TrustScoreGaugeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  showPercentage?: boolean;
  className?: string;
}

const sizeConfig = {
  sm: { width: 60, height: 60, strokeWidth: 6, fontSize: 12 },
  md: { width: 100, height: 100, strokeWidth: 8, fontSize: 16 },
  lg: { width: 140, height: 140, strokeWidth: 10, fontSize: 20 },
};

function getScoreColor(score: number): string {
  if (score >= 0.7) return '#22c55e'; // green-500
  if (score >= 0.4) return '#eab308'; // yellow-500
  if (score >= 0.2) return '#f97316'; // orange-500
  return '#ef4444'; // red-500
}

function getScoreLabel(score: number): TrustLevel {
  if (score >= 0.9) return 'verified';
  if (score >= 0.7) return 'high';
  if (score >= 0.4) return 'medium';
  if (score >= 0.2) return 'low';
  return 'untrusted';
}

export function TrustScoreGauge({
  score,
  size = 'md',
  showLabel = true,
  showPercentage = true,
  className = '',
}: TrustScoreGaugeProps) {
  const config = sizeConfig[size];
  const { width, height, strokeWidth, fontSize } = config;

  const normalizedScore = Math.max(0, Math.min(1, score));
  const percentage = Math.round(normalizedScore * 100);
  const color = getScoreColor(normalizedScore);
  const label = getScoreLabel(normalizedScore);

  // Calculate circle properties
  const radius = (width - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference * (1 - normalizedScore);
  const center = width / 2;

  return (
    <div className={`inline-flex flex-col items-center ${className}`}>
      <div className="relative" style={{ width, height }}>
        <svg width={width} height={height} className="transform -rotate-90">
          {/* Background circle */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={strokeWidth}
          />
          {/* Progress circle */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-500 ease-out"
          />
        </svg>
        {/* Center text */}
        {showPercentage && (
          <div 
            className="absolute inset-0 flex items-center justify-center"
            style={{ fontSize }}
          >
            <span className="font-semibold" style={{ color }}>
              {percentage}%
            </span>
          </div>
        )}
      </div>
      {showLabel && (
        <span 
          className="mt-1 text-xs font-medium capitalize"
          style={{ color }}
        >
          {label.replace('_', ' ')}
        </span>
      )}
    </div>
  );
}

// Horizontal progress bar version
interface TrustScoreBarProps {
  score: number;
  showPercentage?: boolean;
  showLabel?: boolean;
  height?: 'sm' | 'md' | 'lg';
  className?: string;
}

const barHeights = {
  sm: 'h-1.5',
  md: 'h-2.5',
  lg: 'h-4',
};

export function TrustScoreBar({
  score,
  showPercentage = true,
  showLabel = false,
  height = 'md',
  className = '',
}: TrustScoreBarProps) {
  const normalizedScore = Math.max(0, Math.min(1, score));
  const percentage = Math.round(normalizedScore * 100);
  const color = getScoreColor(normalizedScore);
  const label = getScoreLabel(normalizedScore);

  const bgColorClass = useMemo(() => {
    if (normalizedScore >= 0.7) return 'bg-green-500';
    if (normalizedScore >= 0.4) return 'bg-yellow-500';
    if (normalizedScore >= 0.2) return 'bg-orange-500';
    return 'bg-red-500';
  }, [normalizedScore]);

  return (
    <div className={`w-full ${className}`}>
      <div className="flex items-center justify-between mb-1">
        {showLabel && (
          <span className="text-xs font-medium text-gray-600 capitalize">
            {label.replace('_', ' ')}
          </span>
        )}
        {showPercentage && (
          <span className="text-xs font-semibold" style={{ color }}>
            {percentage}%
          </span>
        )}
      </div>
      <div className={`w-full bg-gray-200 rounded-full ${barHeights[height]}`}>
        <div
          className={`${barHeights[height]} rounded-full transition-all duration-500 ease-out ${bgColorClass}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

// Mini inline score indicator
interface TrustScoreInlineProps {
  score: number;
  showValue?: boolean;
  className?: string;
}

export function TrustScoreInline({ 
  score, 
  showValue = true,
  className = '' 
}: TrustScoreInlineProps) {
  const normalizedScore = Math.max(0, Math.min(1, score));
  const percentage = Math.round(normalizedScore * 100);
  const color = getScoreColor(normalizedScore);

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <span
        className="inline-block w-2.5 h-2.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {showValue && (
        <span className="text-sm font-medium" style={{ color }}>
          {percentage}%
        </span>
      )}
    </span>
  );
}

export default TrustScoreGauge;


