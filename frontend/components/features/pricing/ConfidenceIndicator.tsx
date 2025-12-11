// Confidence Indicator Component
// Visual display of confidence scores with progress bar and labels

import { cn } from '@/lib/utils';

// ============================================
// TYPES
// ============================================

interface ConfidenceIndicatorProps {
  /** Confidence score between 0 and 1 */
  score: number;
  /** Show numeric percentage */
  showPercent?: boolean;
  /** Show text label (High/Medium/Low) */
  showLabel?: boolean;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Additional CSS classes */
  className?: string;
}

// ============================================
// HELPERS
// ============================================

function getConfidenceLevel(score: number): 'high' | 'medium' | 'low' {
  if (score >= 0.8) return 'high';
  if (score >= 0.6) return 'medium';
  return 'low';
}

function getConfidenceLabel(level: 'high' | 'medium' | 'low'): string {
  const labels = {
    high: 'High',
    medium: 'Medium',
    low: 'Low',
  };
  return labels[level];
}

function getConfidenceColors(level: 'high' | 'medium' | 'low') {
  const colors = {
    high: {
      bar: 'bg-green-500',
      text: 'text-green-600',
      bg: 'bg-green-100',
    },
    medium: {
      bar: 'bg-yellow-500',
      text: 'text-yellow-600',
      bg: 'bg-yellow-100',
    },
    low: {
      bar: 'bg-red-500',
      text: 'text-red-600',
      bg: 'bg-red-100',
    },
  };
  return colors[level];
}

// ============================================
// SIZE CONFIG
// ============================================

const sizes = {
  sm: {
    bar: 'h-1.5',
    barWidth: 'w-12',
    text: 'text-xs',
    gap: 'gap-1.5',
  },
  md: {
    bar: 'h-2',
    barWidth: 'w-16',
    text: 'text-sm',
    gap: 'gap-2',
  },
  lg: {
    bar: 'h-2.5',
    barWidth: 'w-20',
    text: 'text-base',
    gap: 'gap-2.5',
  },
};

// ============================================
// MAIN COMPONENT
// ============================================

export function ConfidenceIndicator({
  score,
  showPercent = true,
  showLabel = true,
  size = 'md',
  className,
}: ConfidenceIndicatorProps) {
  // Clamp score between 0 and 1
  const clampedScore = Math.max(0, Math.min(1, score));
  const percent = Math.round(clampedScore * 100);
  const level = getConfidenceLevel(clampedScore);
  const colors = getConfidenceColors(level);
  const label = getConfidenceLabel(level);
  const sizeConfig = sizes[size];

  return (
    <div
      className={cn('flex items-center', sizeConfig.gap, className)}
      role="meter"
      aria-valuenow={percent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Confidence: ${percent}% (${label})`}
    >
      {/* Progress Bar */}
      <div
        className={cn(
          'bg-gray-200 rounded-full overflow-hidden',
          sizeConfig.bar,
          sizeConfig.barWidth
        )}
      >
        <div
          className={cn('h-full rounded-full transition-all duration-300', colors.bar)}
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Text Display */}
      <div className={cn('flex items-center', sizeConfig.gap)}>
        {showLabel && (
          <span className={cn('font-medium', sizeConfig.text, colors.text)}>
            {label}
          </span>
        )}
        {showPercent && (
          <span className={cn('text-gray-600', sizeConfig.text)}>
            {percent}%
          </span>
        )}
      </div>
    </div>
  );
}

// ============================================
// BADGE VARIANT
// ============================================

interface ConfidenceBadgeProps {
  score: number;
  className?: string;
}

/** Compact badge version showing confidence level */
export function ConfidenceBadge({ score, className }: ConfidenceBadgeProps) {
  const clampedScore = Math.max(0, Math.min(1, score));
  const percent = Math.round(clampedScore * 100);
  const level = getConfidenceLevel(clampedScore);
  const colors = getConfidenceColors(level);
  const label = getConfidenceLabel(level);

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        colors.bg,
        colors.text,
        className
      )}
    >
      {label} ({percent}%)
    </span>
  );
}
