// components/products/PriceSuggestionCard.tsx
'use client';

import { TrendingUp, Check, RefreshCw, AlertCircle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {
  usePriceSuggestion,
  useApplyPriceSuggestion,
} from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface PriceSuggestionCardProps {
  productId: string;
  currentPrice: string | number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(value);
}

function calculateChange(suggested: number, current: number): number {
  if (!current || current === 0) return 0;
  return ((suggested - current) / current) * 100;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-blue-500" />
        <h3 className="font-semibold text-gray-900">Price Suggestion</h3>
      </div>
      <div className="animate-pulse space-y-3">
        <div className="h-8 bg-gray-200 rounded w-24" />
        <div className="h-4 bg-gray-200 rounded w-32" />
      </div>
    </Card>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-blue-500" />
        <h3 className="font-semibold text-gray-900">Price Suggestion</h3>
      </div>
      <div className="flex items-start gap-2 mb-3">
        <AlertCircle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
        <p className="text-sm text-gray-600">{message}</p>
      </div>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RefreshCw className="h-4 w-4 mr-1" />
        Retry
      </Button>
    </Card>
  );
}

interface PriceChangeIndicatorProps {
  change: number;
}

function PriceChangeIndicator({ change }: PriceChangeIndicatorProps) {
  const isPositive = change > 0;
  const isNegative = change < 0;
  
  const colorClass = isPositive
    ? 'text-green-600'
    : isNegative
      ? 'text-red-600'
      : 'text-gray-500';

  return (
    <span className={`text-sm font-medium ${colorClass}`}>
      {isPositive && '+'}
      {(Number(change ?? 0)).toFixed(1)}% from current
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function PriceSuggestionCard({ productId, currentPrice }: PriceSuggestionCardProps) {
  const {
    data: suggestion,
    isLoading,
    error,
    refetch,
  } = usePriceSuggestion(productId);

  const applyPrice = useApplyPriceSuggestion();

  // Convert currentPrice to number
  const currentPriceNum = typeof currentPrice === 'string' ? parseFloat(currentPrice) : currentPrice;

  // Loading state
  if (isLoading) {
    return <LoadingState />;
  }

  // Error state - show actual error message
  if (error) {
    const errorMessage = error instanceof Error 
      ? error.message 
      : 'Unable to load suggestion. Please try again.';
    return <ErrorState message={errorMessage} onRetry={() => refetch()} />;
  }

  // No suggestion data returned
  if (!suggestion) {
    return (
      <ErrorState 
        message="No suggestion data available. Try refreshing." 
        onRetry={() => refetch()} 
      />
    );
  }

  // Suggestion exists - always show it, even with low confidence or no change
  const suggestedPrice = Number(suggestion.suggested_price) || currentPriceNum;
  const change = calculateChange(suggestedPrice, currentPriceNum);
  const confidence = Number(suggestion.confidence) || 0;
  const isLowConfidence = confidence < 0.3;
  const noChangeRecommended = Math.abs(change) < 0.01;

  const handleApply = () => {
    applyPrice.mutate({
      id: productId,
      price: suggestedPrice,
    });
  };

  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-blue-500" />
        <h3 className="font-semibold text-gray-900">Price Suggestion</h3>
      </div>

      <div className="space-y-4">
        {/* Suggested Price */}
        <div>
          <p className="text-3xl font-bold text-blue-600">
            {formatCurrency(suggestedPrice)}
          </p>
          <PriceChangeIndicator change={change} />
        </div>

        {/* Low confidence or no change warning */}
        {(isLowConfidence || noChangeRecommended) && (
          <div className="flex items-start gap-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
            <AlertCircle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
            <p className="text-sm text-amber-700">
              {noChangeRecommended 
                ? 'Current price is optimal based on available data.'
                : 'Limited data available. Consider adding more sentiment keywords or competitor links.'}
            </p>
          </div>
        )}

        {/* Reasoning */}
        {suggestion.reasoning && (
          <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
            {suggestion.reasoning}
          </p>
        )}

        {/* Confidence */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500">Confidence:</span>
          <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${
                confidence >= 0.5 ? 'bg-blue-500' : confidence >= 0.3 ? 'bg-amber-400' : 'bg-gray-400'
              }`}
              style={{ width: `${Math.max(confidence * 100, 5)}%` }}
            />
          </div>
          <span className="text-sm font-medium text-gray-700">
            {(confidence * 100).toFixed(0)}%
          </span>
        </div>

        {/* Apply Button - only show if there's a price change */}
        {!noChangeRecommended && (
          <Button
            onClick={handleApply}
            isLoading={applyPrice.isPending}
            className="w-full"
          >
            <Check className="h-4 w-4 mr-2" />
            Apply Suggested Price
          </Button>
        )}
      </div>
    </Card>
  );
}

export default PriceSuggestionCard;

