// Rule Card Component
// Displays a single pricing rule with status, type, and actions

'use client';

import { ComponentType } from 'react';
import {
  TrendingUp,
  Users,
  Clock,
  Zap,
  Flame,
  Power,
  Pencil,
  Trash2,
  Copy,
  LucideProps,
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { cn } from '@/lib/utils';
import type { PricingRule, RuleType, RuleAction } from '@/types';

// ============================================
// TYPES
// ============================================

interface RuleCardProps {
  rule: PricingRule;
  productNames?: Record<string, string>;
  competitorNames?: Record<string, string>;
  onToggle?: (id: string, isActive: boolean) => void;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
  onDuplicate?: (id: string) => void;
  isLoading?: boolean;
}

interface RuleTypeInfo {
  label: string;
  color: string;
  icon: ComponentType<LucideProps>;
}

// ============================================
// CONFIG
// ============================================

const ruleTypeConfig: { [key in RuleType]: RuleTypeInfo } = {
  sentiment_threshold: {
    label: 'Sentiment',
    color: 'bg-purple-100 text-purple-800',
    icon: TrendingUp,
  },
  competitor_relative: {
    label: 'Competitor',
    color: 'bg-blue-100 text-blue-800',
    icon: Users,
  },
  time_based: {
    label: 'Time-Based',
    color: 'bg-orange-100 text-orange-800',
    icon: Clock,
  },
  volume_surge: {
    label: 'Volume Surge',
    color: 'bg-green-100 text-green-800',
    icon: Zap,
  },
  viral_detection: {
    label: 'Viral Detection',
    color: 'bg-red-100 text-red-800',
    icon: Flame,
  },
};

const actionLabels: { [key in RuleAction]: string } = {
  increase_percent: 'Increase by %',
  decrease_percent: 'Decrease by %',
  set_absolute: 'Set to price',
  match_competitor: 'Match competitor',
  undercut_competitor: 'Undercut competitor',
};

// ============================================
// COMPONENT
// ============================================

export function RuleCard({
  rule,
  productNames = {},
  competitorNames = {},
  onToggle,
  onEdit,
  onDelete,
  onDuplicate,
  isLoading = false,
}: RuleCardProps) {
  const {
    id,
    name,
    description,
    rule_type,
    is_active,
    priority,
    action,
    action_value,
    cooldown_hours,
    applies_to_all_products,
    applies_to_products,
    applies_to_categories,
    competitor_id,
    competitor_margin_percent,
    sentiment_threshold,
    sentiment_direction,
    volume_threshold,
    volume_window_hours,
    viral_threshold_reach,
    viral_threshold_engagement,
    viral_sentiment_min,
    min_price,
    max_price,
    max_change_percent,
  } = rule;

  const typeInfo = ruleTypeConfig[rule_type];
  const TypeIcon = typeInfo.icon;
  const actionLabel = actionLabels[action];

  // Build scope text — now shows actual names
  const getScopeText = () => {
    if (applies_to_all_products) {
      return 'All products';
    }
    if (applies_to_products?.length) {
      const names = applies_to_products
        .map((pid) => productNames[pid] || pid.slice(0, 8) + '…')
        .slice(0, 3);
      const remaining = applies_to_products.length - 3;
      if (remaining > 0) {
        return `${names.join(', ')} +${remaining} more`;
      }
      return names.join(', ');
    }
    if (applies_to_categories?.length) {
      return applies_to_categories.join(', ');
    }
    return 'All products';
  };

  // Build condition details based on rule type
  const getConditionDetails = (): string[] => {
    const details: string[] = [];

    switch (rule_type) {
      case 'sentiment_threshold':
        if (sentiment_threshold) {
          const dir = sentiment_direction === 'above' ? '>' : sentiment_direction === 'below' ? '<' : '';
          details.push(`Sentiment ${dir} ${sentiment_threshold}`);
        }
        break;

      case 'competitor_relative':
        if (competitor_id) {
          const compName = competitorNames[competitor_id];
          details.push(`Competitor: ${compName || competitor_id.slice(0, 8) + '…'}`);
        }
        if (competitor_margin_percent) {
          details.push(`Margin: ${competitor_margin_percent}%`);
        }
        break;

      case 'volume_surge':
        if (volume_threshold) {
          details.push(`Threshold: ${volume_threshold} mentions`);
        }
        if (volume_window_hours) {
          details.push(`Window: ${volume_window_hours}h`);
        }
        break;

      case 'viral_detection':
        if (viral_threshold_reach) {
          details.push(`Reach: ${viral_threshold_reach.toLocaleString()}`);
        }
        if (viral_threshold_engagement) {
          details.push(`Engagement: ${viral_threshold_engagement.toLocaleString()}`);
        }
        if (viral_sentiment_min) {
          details.push(`Min sentiment: ${viral_sentiment_min}`);
        }
        break;

      case 'time_based':
        // time_days, time_start, time_end are available
        break;
    }

    // Guardrails — show if set
    if (min_price) details.push(`Floor: $${min_price}`);
    if (max_price) details.push(`Ceiling: $${max_price}`);
    if (max_change_percent && max_change_percent !== '15.0') {
      details.push(`Max change: ${max_change_percent}%`);
    }

    return details;
  };

  const conditionDetails = getConditionDetails();

  return (
    <Card
      padding="sm"
      className={cn(
        'hover:shadow-md transition-shadow',
        !is_active && 'opacity-60'
      )}
    >
      {/* Header: Name + Type Badge + Menu */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-gray-900 truncate">{name}</h3>
            {!is_active && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                Inactive
              </span>
            )}
          </div>
          {description && (
            <p className="text-sm text-gray-500 line-clamp-1">{description}</p>
          )}
        </div>

        {/* Type Badge */}
        <span
          className={cn(
            'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ml-2',
            typeInfo.color
          )}
        >
          <TypeIcon className="h-3 w-3" />
          {typeInfo.label}
        </span>
      </div>

      {/* Rule Details */}
      <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
        <div>
          <p className="text-gray-500 text-xs uppercase tracking-wide mb-1">Action</p>
          <p className="text-gray-900 font-medium">
            {actionLabel}: {action_value}
          </p>
        </div>
        <div>
          <p className="text-gray-500 text-xs uppercase tracking-wide mb-1">Priority</p>
          <p className="text-gray-900 font-medium">{priority}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs uppercase tracking-wide mb-1">Scope</p>
          <p className="text-gray-900 font-medium">{getScopeText()}</p>
        </div>
        <div>
          <p className="text-gray-500 text-xs uppercase tracking-wide mb-1">Cooldown</p>
          <p className="text-gray-900 font-medium">{cooldown_hours}h</p>
        </div>
      </div>

      {/* Condition Details — NEW */}
      {conditionDetails.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {conditionDetails.map((detail, i) => (
            <span
              key={i}
              className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-700"
            >
              {detail}
            </span>
          ))}
        </div>
      )}

      {/* Footer: Actions */}
      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        {/* Toggle */}
        {onToggle && (
          <button
            onClick={() => onToggle(id, !is_active)}
            disabled={isLoading}
            className={cn(
              'inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors',
              is_active
                ? 'text-green-700 bg-green-50 hover:bg-green-100'
                : 'text-gray-600 bg-gray-50 hover:bg-gray-100',
              isLoading && 'opacity-50 cursor-not-allowed'
            )}
          >
            <Power className="h-4 w-4" />
            {is_active ? 'Active' : 'Inactive'}
          </button>
        )}

        {/* Action Buttons */}
        <div className="flex items-center gap-1">
          {onDuplicate && (
            <button
              onClick={() => onDuplicate(id)}
              disabled={isLoading}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
              title="Duplicate rule"
            >
              <Copy className="h-4 w-4" />
            </button>
          )}
          {onEdit && (
            <button
              onClick={() => onEdit(id)}
              disabled={isLoading}
              className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors disabled:opacity-50"
              title="Edit rule"
            >
              <Pencil className="h-4 w-4" />
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(id)}
              disabled={isLoading}
              className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
              title="Delete rule"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </Card>
  );
}


