'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  AlertTriangle,
  AlertCircle,
  Info,
  XCircle,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  ExternalLink,
} from 'lucide-react';
import type { RiskAlert } from '@/types/trend-analysis';

interface RiskAlertCardProps {
  risk: RiskAlert;
  onAcknowledge?: (risk: RiskAlert) => void;
  onViewDetails?: (risk: RiskAlert) => void;
}

export function RiskAlertCard({ risk, onAcknowledge, onViewDetails }: RiskAlertCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getIcon = () => {
    switch (risk.risk_level) {
      case 'critical':
        return <XCircle className="h-5 w-5 text-red-500" />;
      case 'high':
        return <AlertTriangle className="h-5 w-5 text-orange-500" />;
      case 'medium':
        return <AlertCircle className="h-5 w-5 text-yellow-500" />;
      default:
        return <Info className="h-5 w-5 text-blue-500" />;
    }
  };

  const getRiskBadgeVariant = () => {
    switch (risk.risk_level) {
      case 'critical':
      case 'high':
        return 'danger';
      case 'medium':
        return 'warning';
      default:
        return 'success';
    }
  };

  const getBorderColor = () => {
    switch (risk.risk_level) {
      case 'critical':
        return 'border-l-red-500';
      case 'high':
        return 'border-l-orange-500';
      case 'medium':
        return 'border-l-yellow-500';
      default:
        return 'border-l-green-500';
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return 'Just now';
  };

  return (
    <Card
      className={`p-4 border-l-4 ${getBorderColor()} ${
        risk.risk_level === 'critical' ? 'animate-pulse' : ''
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="p-2 rounded-lg bg-gray-100">{getIcon()}</div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <h4 className="font-medium text-gray-900">{risk.title}</h4>
            <Badge variant={getRiskBadgeVariant()}>
              {risk.risk_level}
            </Badge>
          </div>

          <p className="text-sm text-gray-500 mb-2">{risk.risk_type}</p>

          <p className="text-sm text-gray-600">{risk.description}</p>

          {/* Affected Products */}
          {risk.affected_products.length > 0 && (
            <div className="mt-2">
              <span className="text-xs text-gray-500">Affected products: </span>
              <span className="text-xs font-medium">
                {risk.affected_products.slice(0, 3).join(', ')}
                {risk.affected_products.length > 3 &&
                  ` +${risk.affected_products.length - 3} more`}
              </span>
            </div>
          )}

          {/* Expandable Recommended Actions */}
          {risk.recommended_actions.length > 0 && (
            <div className="mt-3">
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
              >
                {isExpanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
                <span>
                  {isExpanded ? 'Hide' : 'Show'} recommended actions (
                  {risk.recommended_actions.length})
                </span>
              </button>

              {isExpanded && (
                <ul className="mt-2 space-y-1 pl-4">
                  {risk.recommended_actions.map((action, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-gray-600"
                    >
                      <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                      <span>{action}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-200">
            <span className="text-xs text-gray-500">
              Detected {formatTimeAgo(risk.detected_at)}
              {risk.expires_at && (
                <>
                  {' • '}
                  Expires {new Date(risk.expires_at).toLocaleDateString()}
                </>
              )}
            </span>
          </div>
        </div>
      </div>

      {/* Actions */}
      {(onAcknowledge || onViewDetails) && (
        <div className="flex gap-2 mt-4 pt-3 border-t border-gray-200">
          {onViewDetails && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onViewDetails(risk)}
              className="flex items-center gap-1"
            >
              <ExternalLink className="h-3 w-3" />
              View Details
            </Button>
          )}
          {onAcknowledge && (
            <Button
              size="sm"
              variant="primary"
              onClick={() => onAcknowledge(risk)}
              className="flex items-center gap-1"
            >
              <CheckCircle className="h-3 w-3" />
              Acknowledge
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}


