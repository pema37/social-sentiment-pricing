// frontend/components/features/trust-scoring/AuthorTrustCard.tsx

'use client';

import { Card } from '@/components/ui/Card';
import { 
  User, 
  Calendar, 
  Users, 
  MessageSquare,
  CheckCircle,
  ExternalLink
} from 'lucide-react';
import { TrustLevelBadge } from './TrustLevelBadge';
import { TrustScoreGauge, TrustScoreBar } from './TrustScoreGauge';
import { RiskFlagList } from './RiskFlagBadge';
import type { AuthorScoreResponse, ComponentScores } from '@/types/trust-scoring';

interface AuthorTrustCardProps {
  data: AuthorScoreResponse;
  showDetails?: boolean;
  className?: string;
}

export function AuthorTrustCard({ 
  data, 
  showDetails = true,
  className = '' 
}: AuthorTrustCardProps) {
  const { 
    author_id, 
    source, 
    trust_score, 
    trust_level, 
    risk_flags, 
    risk_score,
    component_scores,
    confidence,
  } = data;

  return (
    <Card className={`p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gray-100 rounded-full">
            <User size={20} className="text-gray-600" />
          </div>
          <div>
            <p className="font-medium text-gray-900">{author_id}</p>
            <p className="text-sm text-gray-500 capitalize">{source}</p>
          </div>
        </div>
        <TrustLevelBadge level={trust_level} score={trust_score} showScore />
      </div>

      {/* Trust Score Gauge */}
      <div className="flex justify-center mb-4">
        <TrustScoreGauge score={trust_score} size="md" />
      </div>

      {/* Risk Flags */}
      {risk_flags.length > 0 && (
        <div className="mb-4">
          <p className="text-xs text-gray-500 mb-2">Risk Flags</p>
          <RiskFlagList flags={risk_flags} maxVisible={4} />
        </div>
      )}

      {/* Component Scores */}
      {showDetails && (
        <div className="border-t pt-4">
          <p className="text-xs text-gray-500 mb-3">Score Breakdown</p>
          <ComponentScoresBreakdown scores={component_scores} />
        </div>
      )}

      {/* Footer Stats */}
      <div className="flex items-center justify-between mt-4 pt-4 border-t text-xs text-gray-500">
        <span>Risk Score: {Math.round(risk_score * 100)}%</span>
        <span>Confidence: {Math.round(confidence * 100)}%</span>
      </div>
    </Card>
  );
}

// Component scores breakdown
interface ComponentScoresBreakdownProps {
  scores: ComponentScores;
}

function ComponentScoresBreakdown({ scores }: ComponentScoresBreakdownProps) {
  const items = [
    { label: 'Account Age', value: scores.account_age, icon: Calendar },
    { label: 'Followers', value: scores.followers, icon: Users },
    { label: 'Engagement', value: scores.engagement, icon: MessageSquare },
    { label: 'History', value: scores.history, icon: User },
    { label: 'Verification', value: scores.verification_bonus, icon: CheckCircle },
  ];

  return (
    <div className="space-y-2">
      {items.map(({ label, value, icon: Icon }) => (
        <div key={label} className="flex items-center gap-2">
          <Icon size={12} className="text-gray-400 shrink-0" />
          <span className="text-xs text-gray-600 w-20">{label}</span>
          <div className="flex-1">
            <TrustScoreBar score={value} height="sm" showPercentage={false} />
          </div>
          <span className="text-xs font-medium text-gray-700 w-10 text-right">
            {Math.round(value * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}

// Compact row version for lists
interface AuthorTrustRowProps {
  data: AuthorScoreResponse;
  onClick?: () => void;
  className?: string;
}

export function AuthorTrustRow({ data, onClick, className = '' }: AuthorTrustRowProps) {
  const { author_id, source, trust_score, trust_level, risk_flags } = data;

  return (
    <div 
      className={`flex items-center justify-between p-3 bg-white border rounded-lg hover:bg-gray-50 transition-colors ${
        onClick ? 'cursor-pointer' : ''
      } ${className}`}
      onClick={onClick}
    >
      <div className="flex items-center gap-3">
        <div className="p-1.5 bg-gray-100 rounded-full">
          <User size={16} className="text-gray-600" />
        </div>
        <div>
          <p className="text-sm font-medium text-gray-900">{author_id}</p>
          <p className="text-xs text-gray-500 capitalize">{source}</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {risk_flags.length > 0 && (
          <span className="text-xs text-orange-600">
            {risk_flags.length} risk{risk_flags.length !== 1 ? 's' : ''}
          </span>
        )}
        <TrustLevelBadge level={trust_level} size="sm" />
        <span className="text-sm font-semibold text-gray-700 w-12 text-right">
          {Math.round(trust_score * 100)}%
        </span>
        {onClick && (
          <ExternalLink size={14} className="text-gray-400" />
        )}
      </div>
    </div>
  );
}

// Mini inline author trust indicator
interface AuthorTrustInlineProps {
  trustScore: number;
  trustLevel: AuthorScoreResponse['trust_level'];
  authorId?: string;
  className?: string;
}

export function AuthorTrustInline({ 
  trustScore, 
  trustLevel, 
  authorId,
  className = '' 
}: AuthorTrustInlineProps) {
  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      {authorId && (
        <span className="text-sm text-gray-600">{authorId}</span>
      )}
      <TrustLevelBadge level={trustLevel} score={trustScore} size="sm" />
    </div>
  );
}

export default AuthorTrustCard;


