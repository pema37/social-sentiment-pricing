// Recommendation Card Component
// Displays a single price recommendation with product info, price change, and status

'use client';

import { ComponentType } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Clock,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Zap,
  LucideProps,
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { cn, formatCurrency, formatPercentage, formatRelativeTime } from '@/lib/utils';
import { ConfidenceIndicator } from './ConfidenceIndicator';
import type { PriceRecommendation, RecommendationStatus } from '@/types';

// ============================================
// TYPES
// ============================================

interface RecommendationCardProps {
  recommendation: PriceRecommendation;
  productName: string;
  productSku?: string | null;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
  onView?: (id: string) => void;
  isLoading?: boolean;
}

interface StatusInfo {
  label: string;
  color: string;
  icon: ComponentType<LucideProps>;
}

// ============================================
// STATUS CONFIG
// ============================================

const statusConfig: { [key in RecommendationStatus]: StatusInfo } = {
  pending: {
    label: 'Pending Review',
    color: 'bg-yellow-100 text-yellow-800',
    icon: Clock,
  },
  auto_approved: {
    label: 'Auto-Approved',
    color: 'bg-blue-100 text-blue-800',
    icon: Zap,
  },
  approved: {
    label: 'Approved',
    color: 'bg-green-100 text-green-800',
    icon: CheckCircle2,
  },
  rejected: {
    label: 'Rejected',
    color: 'bg-red-100 text-red-800',
    icon: XCircle,
  },
  applied: {
    label: 'Applied',
    color: 'bg-emerald-100 text-emerald-800',
    icon: CheckCircle2,
  },
  expired: {
    label: 'Expired',
    color: 'bg-gray-100 text-gray-800',
    icon: AlertCircle,
  },
};

// ============================================
// HELPERS
// ============================================

/** Parse "woocommerce, shopify" into ["woocommerce", "shopify"] */
function parsePlatforms(raw?: string | null): string[] {
  if (!raw) return [];
  return raw.split(',').map((p) => p.trim().toLowerCase()).filter(Boolean);
}

/** Capitalize platform name for display */
function displayPlatform(platform: string): string {
  const names: Record<string, string> = {
    shopify: 'Shopify',
    woocommerce: 'WooCommerce',
  };
  return names[platform] || platform.charAt(0).toUpperCase() + platform.slice(1);
}

// ============================================
// COMPONENT
// ============================================

export function RecommendationCard({
  recommendation,
  productName,
  productSku,
  onApprove,
  onReject,
  onView,
  isLoading = false,
}: RecommendationCardProps) {
  const {
    id,
    current_price,
    recommended_price,
    change_percent,
    confidence_score,
    reasoning,
    status,
    applied_to_platform,
    expires_at,
    created_at,
  } = recommendation;

  const isPending = status === 'pending';
  const isApplied = status === 'applied';
  const isIncrease = change_percent > 0;
  const statusInfo = statusConfig[status];
  const StatusIcon = statusInfo.icon;

  // Parse which platforms received the push
  const appliedPlatforms = parsePlatforms(applied_to_platform);

  // Check if expiring soon (within 24 hours)
  // eslint-disable-next-line
  const isExpiringSoon = new Date(expires_at).getTime() - Date.now() < 24 * 60 * 60 * 1000;

  return (
    <Card padding="sm" className="hover:shadow-md transition-shadow">
      {/* Header: Product + Status */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">{productName}</h3>
          {productSku && (
            <p className="text-sm text-gray-500">SKU: {productSku}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-1">
          <span
            className={cn(
              'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
              statusInfo.color
            )}
          >
            <StatusIcon className="h-3 w-3" />
            {statusInfo.label}
          </span>

          {/* Platform badges — only shown for applied recommendations */}
          {isApplied && appliedPlatforms.length > 0 && (
            <div className="flex flex-wrap gap-1 justify-end">
              {appliedPlatforms.map((platform) => (
                <span
                  key={platform}
                  className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"
                >
                  {displayPlatform(platform)}
                </span>
              ))}
            </div>
          )}

          {/* Warning if applied but no platform recorded */}
          {isApplied && appliedPlatforms.length === 0 && (
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-orange-50 text-orange-600 border border-orange-200">
              <AlertCircle className="h-2.5 w-2.5" />
              Platform unknown
            </span>
          )}
        </div>
      </div>

      {/* Price Change */}
      <div className="flex items-center gap-4 mb-4">
        <div className="flex-1">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
            Current
          </p>
          <p className="text-lg font-semibold text-gray-700">
            {formatCurrency(parseFloat(current_price))}
          </p>
        </div>

        <div className="flex items-center">
          {isIncrease ? (
            <TrendingUp className="h-5 w-5 text-green-500" />
          ) : (
            <TrendingDown className="h-5 w-5 text-red-500" />
          )}
        </div>

        <div className="flex-1 text-right">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">
            Recommended
          </p>
          <p className="text-lg font-semibold text-gray-900">
            {formatCurrency(parseFloat(recommended_price))}
          </p>
        </div>
      </div>

      {/* Change Percent Badge */}
      <div className="flex items-center justify-center mb-4">
        <span
          className={cn(
            'px-3 py-1 rounded-full text-sm font-medium',
            isIncrease
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          )}
        >
          {formatPercentage(change_percent)}
        </span>
      </div>

      {/* Confidence Score */}
      <div className="flex items-center justify-between mb-3 p-2 bg-gray-50 rounded-lg">
        <span className="text-sm text-gray-600">Confidence</span>
        <ConfidenceIndicator score={confidence_score} size="sm" />
      </div>

      {/* Reasoning */}
      <p className="text-sm text-gray-600 mb-4 line-clamp-2">{reasoning}</p>

      {/* Footer: Time + Actions */}
      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <div className="text-xs text-gray-500">
          <span>{formatRelativeTime(created_at)}</span>
          {isPending && (
            <span
              className={cn('ml-2', isExpiringSoon && 'text-orange-600 font-medium')}
            >
              · Expires {formatRelativeTime(expires_at)}
            </span>
          )}
        </div>

        {isPending && (onApprove || onReject) && (
          <div className="flex items-center gap-2">
            {onReject && (
              <button
                onClick={() => onReject(id)}
                disabled={isLoading}
                className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-50"
              >
                Reject
              </button>
            )}
            {onApprove && (
              <button
                onClick={() => onApprove(id)}
                disabled={isLoading}
                className="px-3 py-1 text-sm text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors disabled:opacity-50"
              >
                Approve
              </button>
            )}
          </div>
        )}

        {!isPending && onView && (
          <button
            onClick={() => onView(id)}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            View Details
          </button>
        )}
      </div>
    </Card>
  );
}


