// components/products/PriceSuggestionCard.tsx
'use client';

import { TrendingUp, Check, RefreshCw } from 'lucide-react';
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

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-blue-500" />
        <h3 className="font-semibold text-gray-900">Price Suggestion</h3>
      </div>
      <p className="text-sm text-gray-500 mb-3">Unable to load suggestion</p>
      <Button variant="secondary" size="sm" onClick={onRetry}>
        <RefreshCw className="h-4 w-4 mr-1" />
        Retry
      </Button>
    </Card>
  );
}

function NoSuggestionState() {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="h-5 w-5 text-blue-500" />
        <h3 className="font-semibold text-gray-900">Price Suggestion</h3>
      </div>
      <p className="text-sm text-gray-500">
        No price suggestion available. Enable auto-pricing or add sentiment data.
      </p>
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
      {(change ?? 0).toFixed(1)}% from current
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

  // Error state
  if (error) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  // No suggestion available
  if (!suggestion?.suggested_price) {
    return <NoSuggestionState />;
  }

  const change = calculateChange(suggestion.suggested_price, currentPriceNum);

  const handleApply = () => {
    applyPrice.mutate({
      id: productId,
      price: suggestion.suggested_price,
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
            {formatCurrency(suggestion.suggested_price)}
          </p>
          <PriceChangeIndicator change={change} />
        </div>

        {/* Reasoning */}
        {suggestion.reasoning && (
          <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
            {suggestion.reasoning}
          </p>
        )}

        {/* Confidence */}
        {suggestion.confidence != null && (
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Confidence:</span>
            <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full"
                style={{ width: `${(suggestion.confidence ?? 0) * 100}%` }}
              />
            </div>
            <span className="text-sm font-medium text-gray-700">
              {((suggestion.confidence ?? 0) * 100).toFixed(0)}%
            </span>
          </div>
        )}

        {/* Apply Button */}
        <Button
          onClick={handleApply}
          isLoading={applyPrice.isPending}
          className="w-full"
        >
          <Check className="h-4 w-4 mr-2" />
          Apply Suggested Price
        </Button>
      </div>
    </Card>
  );
}

export default PriceSuggestionCard;

