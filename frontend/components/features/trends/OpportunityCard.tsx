'use client';

import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  TrendingUp,
  TrendingDown,
  Pause,
  Tag,
  Star,
  ArrowRight,
  Clock,
} from 'lucide-react';
import type { PricingOpportunity } from '@/types/trend-analysis';
import { getConfidenceDisplayInfo, getOpportunityTypeLabel } from '@/types/trend-analysis';

interface OpportunityCardProps {
  opportunity: PricingOpportunity;
  onApply?: (opportunity: PricingOpportunity) => void;
  onDismiss?: (opportunity: PricingOpportunity) => void;
}

export function OpportunityCard({ opportunity, onApply, onDismiss }: OpportunityCardProps) {
  const confidenceInfo = getConfidenceDisplayInfo(opportunity.confidence);
  
  const getIcon = () => {
    switch (opportunity.opportunity_type) {
      case 'price_increase':
        return <TrendingUp className="h-5 w-5 text-green-500" />;
      case 'price_decrease':
        return <TrendingDown className="h-5 w-5 text-red-500" />;
      case 'hold':
        return <Pause className="h-5 w-5 text-gray-500" />;
      case 'promotional':
        return <Tag className="h-5 w-5 text-purple-500" />;
      case 'premium_positioning':
        return <Star className="h-5 w-5 text-yellow-500" />;
      default:
        return <TrendingUp className="h-5 w-5 text-blue-500" />;
    }
  };

  const getBgColor = () => {
    switch (opportunity.opportunity_type) {
      case 'price_increase':
        return 'bg-green-50 border-green-200';
      case 'price_decrease':
        return 'bg-red-50 border-red-200';
      case 'promotional':
        return 'bg-purple-50 border-purple-200';
      case 'premium_positioning':
        return 'bg-yellow-50 border-yellow-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const currentPrice = parseFloat(opportunity.current_price);
  const suggestedPrice = parseFloat(opportunity.suggested_price);
  const priceChange = suggestedPrice - currentPrice;
  const priceChangePercent = (priceChange / currentPrice) * 100;

  const validUntil = new Date(opportunity.valid_until);
  const now = new Date();
  const hoursRemaining = Math.max(0, Math.round((validUntil.getTime() - now.getTime()) / (1000 * 60 * 60)));

  return (
    <Card className={`p-4 border-2 ${getBgColor()}`}>
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className="p-2 bg-white rounded-lg shadow-sm">{getIcon()}</div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-1">
            <h4 className="font-medium text-gray-900 truncate">
              {opportunity.product_name}
            </h4>
            <Badge variant="info" className="ml-2 shrink-0">
              {getOpportunityTypeLabel(opportunity.opportunity_type)}
            </Badge>
          </div>

          {/* Price Change */}
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm text-gray-500">
              ${currentPrice.toFixed(2)}
            </span>
            <ArrowRight className="h-3 w-3 text-gray-400" />
            <span className="text-sm font-medium">
              ${suggestedPrice.toFixed(2)}
            </span>
            <span
              className={`text-xs font-medium ${
                priceChange >= 0 ? 'text-green-600' : 'text-red-600'
              }`}
            >
              ({priceChange >= 0 ? '+' : ''}{priceChangePercent.toFixed(1)}%)
            </span>
          </div>

          {/* Expected Impact */}
          <p className="text-sm text-gray-600 mb-2">
            Expected impact: <span className="font-medium">{opportunity.expected_impact}</span>
          </p>

          {/* Reasoning */}
          <p className="text-xs text-gray-500 mb-3">{opportunity.reasoning}</p>

          {/* Triggers */}
          {opportunity.triggers.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {opportunity.triggers.slice(0, 3).map((trigger, i) => (
                <Badge key={i} variant="default" className="text-xs">
                  {trigger}
                </Badge>
              ))}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center justify-between pt-2 border-t border-gray-200">
            {/* Confidence */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">Confidence:</span>
              <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
                <div
                  className={`h-full ${confidenceInfo.color}`}
                  style={{ width: `${opportunity.confidence_score}%` }}
                />
              </div>
              <span className="text-xs font-medium">{opportunity.confidence_score}%</span>
            </div>

            {/* Time Remaining */}
            <div className="flex items-center gap-1 text-xs text-gray-500">
              <Clock className="h-3 w-3" />
              <span>{hoursRemaining}h left</span>
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      {(onApply || onDismiss) && (
        <div className="flex gap-2 mt-4 pt-3 border-t border-gray-200">
          {onApply && (
            <Button
              size="sm"
              variant="primary"
              onClick={() => onApply(opportunity)}
              className="flex-1"
            >
              Apply Price
            </Button>
          )}
          {onDismiss && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => onDismiss(opportunity)}
            >
              Dismiss
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}



