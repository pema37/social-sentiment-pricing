// frontend/components/features/trust-scoring/RiskFlagBadge.tsx

'use client';

import { Badge } from '@/components/ui/Badge';
import { 
  Clock, 
  Users, 
  Zap, 
  Copy, 
  Timer,
  ThumbsUp,
  Hash,
  Link,
  FileText,
  TrendingUp,
  Bot,
  HeartHandshake
} from 'lucide-react';
import type { RiskFlag } from '@/types/trust-scoring';

interface RiskFlagBadgeProps {
  flag: RiskFlag;
  showDescription?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

type Severity = 'low' | 'medium' | 'high';

const flagConfig: Record<RiskFlag, {
  label: string;
  severity: Severity;
  description: string;
  Icon: typeof Clock;
}> = {
  new_account: {
    label: 'New Account',
    severity: 'low',
    description: 'Account is less than 30 days old',
    Icon: Clock,
  },
  low_followers: {
    label: 'Low Followers',
    severity: 'low',
    description: 'Account has very few followers',
    Icon: Users,
  },
  high_post_frequency: {
    label: 'High Frequency',
    severity: 'medium',
    description: 'Posting unusually frequently',
    Icon: Zap,
  },
  repetitive_content: {
    label: 'Repetitive',
    severity: 'medium',
    description: 'Similar content posted multiple times',
    Icon: Copy,
  },
  coordinated_timing: {
    label: 'Coordinated',
    severity: 'high',
    description: 'Posts synchronized with other accounts',
    Icon: Timer,
  },
  suspicious_engagement: {
    label: 'Suspicious Engagement',
    severity: 'medium',
    description: 'Engagement patterns appear artificial',
    Icon: ThumbsUp,
  },
  keyword_stuffing: {
    label: 'Keyword Stuffing',
    severity: 'medium',
    description: 'Excessive use of hashtags or keywords',
    Icon: Hash,
  },
  link_spam: {
    label: 'Link Spam',
    severity: 'medium',
    description: 'Contains excessive promotional links',
    Icon: Link,
  },
  copy_paste: {
    label: 'Copy/Paste',
    severity: 'high',
    description: 'Exact duplicate of other content',
    Icon: FileText,
  },
  sentiment_extreme: {
    label: 'Extreme Sentiment',
    severity: 'low',
    description: 'Consistently extreme positive or negative',
    Icon: TrendingUp,
  },
  bot_pattern: {
    label: 'Bot Pattern',
    severity: 'high',
    description: 'Behavior matches known bot patterns',
    Icon: Bot,
  },
  fake_engagement: {
    label: 'Fake Engagement',
    severity: 'high',
    description: 'Engagement appears artificially inflated',
    Icon: HeartHandshake,
  },
};

const severityVariants: Record<Severity, 'default' | 'success' | 'warning' | 'danger' | 'info'> = {
  low: 'default',
  medium: 'warning',
  high: 'danger',
};

const sizeClasses = {
  sm: 'text-xs px-1.5 py-0.5',
  md: 'text-sm px-2 py-1',
  lg: 'text-base px-3 py-1.5',
};

const iconSizes = {
  sm: 10,
  md: 12,
  lg: 14,
};

export function RiskFlagBadge({ 
  flag, 
  showDescription = false,
  size = 'sm' 
}: RiskFlagBadgeProps) {
  const config = flagConfig[flag];
  
  if (!config) {
    return (
      <Badge variant="default" className={sizeClasses[size]}>
        {flag.replace(/_/g, ' ')}
      </Badge>
    );
  }

  const { label, severity, description, Icon } = config;
  const variant = severityVariants[severity];

  return (
    <span title={showDescription ? undefined : description}>
      <Badge variant={variant} className={`inline-flex items-center gap-1 ${sizeClasses[size]}`}>
        <Icon size={iconSizes[size]} />
        <span>{label}</span>
      </Badge>
      {showDescription && (
        <span className="ml-1 text-xs text-gray-500">{description}</span>
      )}
    </span>
  );
}

// List of risk flags with severity grouping
interface RiskFlagListProps {
  flags: RiskFlag[];
  maxVisible?: number;
  size?: 'sm' | 'md' | 'lg';
}

export function RiskFlagList({ flags, maxVisible = 3, size = 'sm' }: RiskFlagListProps) {
  if (!flags || flags.length === 0) {
    return (
      <span className="text-sm text-gray-400">No risks detected</span>
    );
  }

  // Sort by severity (high first)
  const sortedFlags = [...flags].sort((a, b) => {
    const severityOrder: Record<Severity, number> = { high: 0, medium: 1, low: 2 };
    const aSeverity = flagConfig[a]?.severity || 'low';
    const bSeverity = flagConfig[b]?.severity || 'low';
    return severityOrder[aSeverity] - severityOrder[bSeverity];
  });

  const visibleFlags = sortedFlags.slice(0, maxVisible);
  const remainingCount = sortedFlags.length - maxVisible;

  return (
    <div className="flex flex-wrap items-center gap-1">
      {visibleFlags.map((flag) => (
        <RiskFlagBadge key={flag} flag={flag} size={size} />
      ))}
      {remainingCount > 0 && (
        <span 
          className="text-xs text-gray-500 ml-1"
          title={sortedFlags.slice(maxVisible).map(f => flagConfig[f]?.label || f).join(', ')}
        >
          +{remainingCount} more
        </span>
      )}
    </div>
  );
}

// Severity indicator dot
interface SeverityDotProps {
  severity: Severity;
  className?: string;
}

export function SeverityDot({ severity, className = '' }: SeverityDotProps) {
  const colorClasses: Record<Severity, string> = {
    low: 'bg-gray-400',
    medium: 'bg-yellow-500',
    high: 'bg-red-500',
  };

  return (
    <span 
      className={`inline-block w-2 h-2 rounded-full ${colorClasses[severity]} ${className}`}
      title={`${severity} severity`}
    />
  );
}

export default RiskFlagBadge;


