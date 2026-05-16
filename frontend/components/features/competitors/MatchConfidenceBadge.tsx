'use client';

// frontend/components/features/competitors/MatchConfidenceBadge.tsx

import { useMemo } from 'react';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface MatchConfidenceBadgeProps {
  score: number; // 0-1
  showPercent?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

type ConfidenceLevel = 'high' | 'medium' | 'low';

interface ConfidenceConfig {
  level: ConfidenceLevel;
  label: string;
  bgColor: string;
  textColor: string;
  ringColor: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper
// ─────────────────────────────────────────────────────────────────────────────

function getConfidenceConfig(score: number): ConfidenceConfig {
  if (score >= 0.8) {
    return {
      level: 'high',
      label: 'High Match',
      bgColor: 'bg-green-100',
      textColor: 'text-green-800',
      ringColor: 'ring-green-600/20',
    };
  } else if (score >= 0.5) {
    return {
      level: 'medium',
      label: 'Possible',
      bgColor: 'bg-yellow-100',
      textColor: 'text-yellow-800',
      ringColor: 'ring-yellow-600/20',
    };
  } else {
    return {
      level: 'low',
      label: 'Low Match',
      bgColor: 'bg-gray-100',
      textColor: 'text-gray-600',
      ringColor: 'ring-gray-500/20',
    };
  }
}

function getSizeClasses(size: 'sm' | 'md' | 'lg'): string {
  switch (size) {
    case 'sm':
      return 'px-1.5 py-0.5 text-xs';
    case 'md':
      return 'px-2 py-1 text-sm';
    case 'lg':
      return 'px-2.5 py-1.5 text-sm';
    default:
      return 'px-2 py-1 text-sm';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────────────────────────────────────

export function MatchConfidenceBadge({
  score,
  showPercent = true,
  size = 'md',
}: MatchConfidenceBadgeProps) {
  const config = useMemo(() => getConfidenceConfig(score), [score]);
  const sizeClasses = useMemo(() => getSizeClasses(size), [size]);
  const percent = Math.round(score * 100);

  return (
    <span
      className={`
        inline-flex items-center gap-1 font-medium rounded-full ring-1 ring-inset
        ${config.bgColor} ${config.textColor} ${config.ringColor} ${sizeClasses}
      `}
      title={`${percent}% confidence match`}
    >
      {/* Confidence dot indicator */}
      <span
        className={`
          w-1.5 h-1.5 rounded-full
          ${config.level === 'high' ? 'bg-green-500' : ''}
          ${config.level === 'medium' ? 'bg-yellow-500' : ''}
          ${config.level === 'low' ? 'bg-gray-400' : ''}
        `}
      />
      
      {/* Label or percent */}
      {showPercent ? (
        <span>{percent}%</span>
      ) : (
        <span>{config.label}</span>
      )}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Variant: Progress Bar Style
// ─────────────────────────────────────────────────────────────────────────────

interface ConfidenceBarProps {
  score: number;
  showLabel?: boolean;
  height?: 'sm' | 'md';
}

export function ConfidenceBar({
  score,
  showLabel = true,
  height = 'sm',
}: ConfidenceBarProps) {
  const config = useMemo(() => getConfidenceConfig(score), [score]);
  const percent = Math.round(score * 100);
  const heightClass = height === 'sm' ? 'h-1.5' : 'h-2.5';

  const barColor = useMemo(() => {
    if (score >= 0.8) return 'bg-green-500';
    if (score >= 0.5) return 'bg-yellow-500';
    return 'bg-gray-400';
  }, [score]);

  return (
    <div className="w-full">
      {showLabel && (
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-gray-500">Match Confidence</span>
          <span className={`text-xs font-medium ${config.textColor}`}>
            {percent}%
          </span>
        </div>
      )}
      <div className={`w-full bg-gray-200 rounded-full ${heightClass}`}>
        <div
          className={`${barColor} ${heightClass} rounded-full transition-all duration-300`}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

export default MatchConfidenceBadge;


