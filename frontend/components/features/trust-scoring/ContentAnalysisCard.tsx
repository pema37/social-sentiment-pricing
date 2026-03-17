// frontend/components/features/trust-scoring/ContentAnalysisCard.tsx

'use client';

import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { 
  FileText, 
  Copy, 
  Hash, 
  Link, 
  AlertTriangle,
  CheckCircle,
  Type,
  Sparkles
} from 'lucide-react';
import { TrustScoreBar } from './TrustScoreGauge';
import { RiskFlagList } from './RiskFlagBadge';
import type { ContentAnalysisResponse, SpamIndicators } from '@/types/trust-scoring';

interface ContentAnalysisCardProps {
  data: ContentAnalysisResponse;
  content?: string;
  showContent?: boolean;
  className?: string;
}

export function ContentAnalysisCard({ 
  data, 
  content,
  showContent = true,
  className = '' 
}: ContentAnalysisCardProps) {
  const { 
    word_count,
    is_duplicate,
    duplicate_count,
    content_quality_score,
    originality_score,
    risk_flags,
    spam_indicators,
    is_spam,
  } = data;

  return (
    <Card className={`p-5 ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-full ${is_spam ? 'bg-red-100' : 'bg-gray-100'}`}>
            <FileText size={20} className={is_spam ? 'text-red-600' : 'text-gray-600'} />
          </div>
          <div>
            <p className="font-medium text-gray-900">Content Analysis</p>
            <p className="text-sm text-gray-500">{word_count} words</p>
          </div>
        </div>
        {is_spam ? (
          <Badge variant="danger" className="flex items-center gap-1">
            <AlertTriangle size={12} />
            Spam Detected
          </Badge>
        ) : (
          <Badge variant="success" className="flex items-center gap-1">
            <CheckCircle size={12} />
            Clean
          </Badge>
        )}
      </div>

      {/* Content Preview */}
      {showContent && content && (
        <div className="mb-4 p-3 bg-gray-50 rounded-lg">
          <p className="text-sm text-gray-700 line-clamp-3">{content}</p>
        </div>
      )}

      {/* Score Bars */}
      <div className="space-y-3 mb-4">
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-600 flex items-center gap-1">
              <Sparkles size={12} />
              Quality Score
            </span>
          </div>
          <TrustScoreBar score={content_quality_score} height="sm" />
        </div>
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-600 flex items-center gap-1">
              <Type size={12} />
              Originality Score
            </span>
          </div>
          <TrustScoreBar score={originality_score} height="sm" />
        </div>
      </div>

      {/* Duplicate Warning */}
      {is_duplicate && (
        <div className="flex items-center gap-2 p-3 bg-orange-50 rounded-lg mb-4">
          <Copy size={16} className="text-orange-600" />
          <span className="text-sm text-orange-700">
            Duplicate content detected ({duplicate_count} copies found)
          </span>
        </div>
      )}

      {/* Spam Indicators */}
      <div className="mb-4">
        <p className="text-xs text-gray-500 mb-2">Spam Indicators</p>
        <SpamIndicatorsList indicators={spam_indicators} />
      </div>

      {/* Risk Flags */}
      {risk_flags.length > 0 && (
        <div className="border-t pt-4">
          <p className="text-xs text-gray-500 mb-2">Risk Flags</p>
          <RiskFlagList flags={risk_flags} maxVisible={5} />
        </div>
      )}
    </Card>
  );
}

// Spam indicators list
interface SpamIndicatorsListProps {
  indicators: SpamIndicators;
}

function SpamIndicatorsList({ indicators }: SpamIndicatorsListProps) {
  const items = [
    { key: 'excessive_hashtags', label: 'Excessive Hashtags', icon: Hash, value: indicators.excessive_hashtags },
    { key: 'excessive_links', label: 'Excessive Links', icon: Link, value: indicators.excessive_links },
    { key: 'keyword_stuffing', label: 'Keyword Stuffing', icon: Type, value: indicators.keyword_stuffing },
    { key: 'all_caps', label: 'All Caps', icon: Type, value: indicators.all_caps },
    { key: 'spam_phrases', label: 'Spam Phrases', icon: AlertTriangle, value: indicators.spam_phrases },
  ];

  const hasAnyIndicator = Object.values(indicators).some(v => v);

  if (!hasAnyIndicator) {
    return (
      <p className="text-sm text-green-600 flex items-center gap-1">
        <CheckCircle size={14} />
        No spam indicators detected
      </p>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map(({ key, label, icon: Icon, value }) => (
        <div
          key={key}
          className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs ${
            value 
              ? 'bg-red-100 text-red-700' 
              : 'bg-gray-100 text-gray-500'
          }`}
        >
          <Icon size={12} />
          <span>{label}</span>
          {value ? (
            <AlertTriangle size={10} />
          ) : (
            <CheckCircle size={10} />
          )}
        </div>
      ))}
    </div>
  );
}

// Compact row version for lists
interface ContentAnalysisRowProps {
  data: ContentAnalysisResponse;
  content?: string;
  onClick?: () => void;
  className?: string;
}

export function ContentAnalysisRow({ 
  data, 
  content,
  onClick, 
  className = '' 
}: ContentAnalysisRowProps) {
  const { content_quality_score, is_spam, is_duplicate, risk_flags } = data;

  return (
    <div 
      className={`flex items-center justify-between p-3 bg-white border rounded-lg hover:bg-gray-50 transition-colors ${
        onClick ? 'cursor-pointer' : ''
      } ${className}`}
      onClick={onClick}
    >
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <div className={`p-1.5 rounded-full shrink-0 ${
          is_spam ? 'bg-red-100' : 'bg-gray-100'
        }`}>
          <FileText size={16} className={is_spam ? 'text-red-600' : 'text-gray-600'} />
        </div>
        {content && (
          <p className="text-sm text-gray-700 truncate">{content}</p>
        )}
      </div>

      <div className="flex items-center gap-3 shrink-0 ml-4">
        {is_duplicate && (
          <Badge variant="warning" className="text-xs">
            <Copy size={10} className="mr-1" />
            Duplicate
          </Badge>
        )}
        {is_spam && (
          <Badge variant="danger" className="text-xs">
            Spam
          </Badge>
        )}
        {risk_flags.length > 0 && !is_spam && (
          <span className="text-xs text-orange-600">
            {risk_flags.length} flag{risk_flags.length !== 1 ? 's' : ''}
          </span>
        )}
        <span className={`text-sm font-semibold w-12 text-right ${
          content_quality_score >= 0.7 ? 'text-green-600' :
          content_quality_score >= 0.4 ? 'text-yellow-600' :
          'text-red-600'
        }`}>
          {Math.round(content_quality_score * 100)}%
        </span>
      </div>
    </div>
  );
}

// Quick spam check result display
interface SpamCheckResultProps {
  isSpam: boolean;
  spamScore: number;
  reasons: string[];
  className?: string;
}

export function SpamCheckResult({ 
  isSpam, 
  spamScore, 
  reasons,
  className = '' 
}: SpamCheckResultProps) {
  return (
    <div className={`p-4 rounded-lg ${
      isSpam ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'
    } ${className}`}>
      <div className="flex items-center gap-2 mb-2">
        {isSpam ? (
          <>
            <AlertTriangle size={18} className="text-red-600" />
            <span className="font-medium text-red-800">Likely Spam</span>
          </>
        ) : (
          <>
            <CheckCircle size={18} className="text-green-600" />
            <span className="font-medium text-green-800">Content Looks Clean</span>
          </>
        )}
        <span className={`ml-auto text-sm font-semibold ${
          isSpam ? 'text-red-700' : 'text-green-700'
        }`}>
          {Math.round(spamScore * 100)}% spam score
        </span>
      </div>
      
      {reasons.length > 0 && (
        <ul className="mt-2 space-y-1">
          {reasons.map((reason, index) => (
            <li key={index} className="text-sm text-gray-600 flex items-center gap-1.5">
              <span className="w-1 h-1 bg-gray-400 rounded-full" />
              {reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default ContentAnalysisCard;


