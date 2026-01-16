// frontend/components/features/trust-scoring/TrustLevelBadge.tsx

'use client';

import { Badge } from '@/components/ui/Badge';
import { 
  ShieldCheck, 
  Shield, 
  ShieldAlert, 
  ShieldX,
  ShieldQuestion,
  Ban
} from 'lucide-react';
import type { TrustLevel } from '@/types/trust-scoring';

interface TrustLevelBadgeProps {
  level: TrustLevel;
  score?: number;
  showScore?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const levelConfig: Record<TrustLevel, {
  label: string;
  variant: 'default' | 'success' | 'warning' | 'danger' | 'info';
  Icon: typeof Shield;
}> = {
  verified: {
    label: 'Verified',
    variant: 'info',
    Icon: ShieldCheck,
  },
  high: {
    label: 'High Trust',
    variant: 'success',
    Icon: Shield,
  },
  medium: {
    label: 'Medium',
    variant: 'default',
    Icon: ShieldQuestion,
  },
  low: {
    label: 'Low Trust',
    variant: 'warning',
    Icon: ShieldAlert,
  },
  untrusted: {
    label: 'Untrusted',
    variant: 'danger',
    Icon: ShieldX,
  },
  blocked: {
    label: 'Blocked',
    variant: 'danger',
    Icon: Ban,
  },
};

const sizeClasses = {
  sm: 'text-xs px-1.5 py-0.5',
  md: 'text-sm px-2 py-1',
  lg: 'text-base px-3 py-1.5',
};

const iconSizes = {
  sm: 12,
  md: 14,
  lg: 16,
};

export function TrustLevelBadge({ 
  level, 
  score, 
  showScore = false,
  size = 'md' 
}: TrustLevelBadgeProps) {
  const config = levelConfig[level] || levelConfig.medium;
  const { label, variant, Icon } = config;

  const displayText = showScore && score !== undefined
    ? `${label} (${Math.round(score * 100)}%)`
    : label;

  return (
    <Badge variant={variant} className={`inline-flex items-center gap-1 ${sizeClasses[size]}`}>
      <Icon size={iconSizes[size]} />
      <span>{displayText}</span>
    </Badge>
  );
}

// Compact version showing just the icon with tooltip wrapper
interface TrustLevelIconProps {
  level: TrustLevel;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function TrustLevelIcon({ level, size = 'md', className = '' }: TrustLevelIconProps) {
  const config = levelConfig[level] || levelConfig.medium;
  const { Icon, label } = config;

  const colorClasses: Record<TrustLevel, string> = {
    verified: 'text-blue-600',
    high: 'text-green-600',
    medium: 'text-yellow-600',
    low: 'text-orange-600',
    untrusted: 'text-red-600',
    blocked: 'text-gray-600',
  };

  return (
    <span title={label} className="inline-flex">
      <Icon 
        size={iconSizes[size]} 
        className={`${colorClasses[level]} ${className}`}
      />
    </span>
  );
}

export default TrustLevelBadge;


