// components/features/products/PriceSuggestionModal.tsx
'use client';

import {
  X,
  Package,
  TrendingUp,
  TrendingDown,
  Sparkles,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import {
  usePriceSuggestion,
  useApplyPriceSuggestion,
} from '@/lib/hooks/use-products';
import type { Product } from '@/types';
import Image from 'next/image';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface PriceSuggestionModalProps {
  product: Product;
  onClose: () => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatCurrency(value: number | string | null | undefined): string {
  if (value == null) return '$0.00';
  const num = Number(value);
  return isNaN(num) ? '$0.00' : `$${num.toFixed(2)}`;
}

function safeNumber(value: unknown, defaultValue = 0): number {
  if (value == null) return defaultValue;
  const num = Number(value);
  return isNaN(num) ? defaultValue : num;
}

// Fix mixed content: ensure HTTPS for external images
function ensureHttps(url: string): string {
  return url.replace(/^http:\/\//i, 'https://');
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
    </div>
  );
}

function ErrorState() {
  return (
    <div className="text-center py-8">
      <AlertTriangle className="w-12 h-12 text-yellow-500 mx-auto mb-3" />
      <p className="text-gray-600">Unable to generate suggestion</p>
      <p className="text-sm text-gray-500 mt-1">Not enough sentiment data available</p>
    </div>
  );
}

interface ProductInfoProps {
  product: Product;
}

function ProductInfo({ product }: ProductInfoProps) {
  return (
    <div className="flex items-center gap-4">
      {product.image_url ? (
        <Image
          src={ensureHttps(product.image_url)}
          alt={product.name}
          width={64}
          height={64}
          className="w-16 h-16 rounded-lg object-cover"
        />
      ) : (
        <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center">
          <Package className="w-8 h-8 text-gray-400" />
        </div>
      )}
      <div>
        <h3 className="font-medium">{product.name}</h3>
        <p className="text-sm text-gray-500">{product.sku || 'No SKU'}</p>
      </div>
    </div>
  );
}

interface PriceComparisonProps {
  currentPrice: number;
  suggestedPrice: number;
  changePercent: number;
}

function PriceComparison({ currentPrice, suggestedPrice, changePercent }: PriceComparisonProps) {
  const isPositive = changePercent >= 0;
  const safeChangePercent = safeNumber(changePercent);

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-gray-50 rounded-lg p-4">
        <p className="text-sm text-gray-500 mb-1">Current Price</p>
        <p className="text-2xl font-bold">{formatCurrency(currentPrice)}</p>
      </div>
      <div className="bg-blue-50 rounded-lg p-4">
        <p className="text-sm text-blue-600 mb-1">Suggested Price</p>
        <p className="text-2xl font-bold text-blue-600">
          {formatCurrency(suggestedPrice)}
        </p>
        <div className="flex items-center gap-1 mt-1">
          {isPositive ? (
            <TrendingUp className="w-4 h-4 text-green-500" />
          ) : (
            <TrendingDown className="w-4 h-4 text-red-500" />
          )}
          <span
            className={`text-sm font-medium ${
              isPositive ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {isPositive ? '+' : ''}
            {safeChangePercent.toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}

interface ConfidenceBarProps {
  confidence: number;
}

function ConfidenceBar({ confidence }: ConfidenceBarProps) {
  const safeConfidence = safeNumber(confidence);
  const percent = safeConfidence * 100;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-600">Confidence</span>
        <span className="text-sm font-medium">{percent.toFixed(0)}%</span>
      </div>
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-600 rounded-full"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

interface FactorsGridProps {
  sentimentScore: number | null;
  mentionVolume: number;
}

function FactorsGrid({ sentimentScore, mentionVolume }: FactorsGridProps) {
  const displaySentiment = sentimentScore != null && typeof sentimentScore === 'number'
    ? `${(safeNumber(sentimentScore) * 100).toFixed(0)}%`
    : 'N/A';

  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="text-center p-3 bg-gray-50 rounded-lg">
        <p className="text-xs text-gray-500">Sentiment</p>
        <p className="font-semibold">{displaySentiment}</p>
      </div>
      <div className="text-center p-3 bg-gray-50 rounded-lg">
        <p className="text-xs text-gray-500">Mentions</p>
        <p className="font-semibold">{mentionVolume ?? 0}</p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function PriceSuggestionModal({ product, onClose }: PriceSuggestionModalProps) {
  const { data: suggestion, isLoading, error } = usePriceSuggestion(product.id);
  const applyPrice = useApplyPriceSuggestion();

  const handleApply = () => {
    if (suggestion) {
      applyPrice.mutate(
        { id: product.id, price: suggestion.suggested_price },
        { onSuccess: onClose }
      );
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Sparkles className="w-5 h-5 text-blue-600" />
            </div>
            <h2 className="text-lg font-semibold">AI Price Suggestion</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {isLoading ? (
            <LoadingState />
          ) : error ? (
            <ErrorState />
          ) : suggestion ? (
            <div className="space-y-6">
              <ProductInfo product={product} />

              <PriceComparison
                currentPrice={safeNumber(product.current_price)}
                suggestedPrice={safeNumber(suggestion.suggested_price)}
                changePercent={safeNumber(suggestion.change_percent)}
              />

              <ConfidenceBar confidence={safeNumber(suggestion.confidence)} />

              {suggestion.reasoning && (
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">Analysis</p>
                  <p className="text-sm text-gray-600">{suggestion.reasoning}</p>
                </div>
              )}

              <FactorsGrid
                sentimentScore={suggestion.factors.sentiment_score}
                mentionVolume={suggestion.factors.mention_volume ?? 0}
              />
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-6 border-t bg-gray-50 rounded-b-xl">
          <Button variant="secondary" onClick={onClose} className="flex-1">
            Cancel
          </Button>
          <Button
            onClick={handleApply}
            disabled={!suggestion || applyPrice.isPending}
            isLoading={applyPrice.isPending}
            className="flex-1"
          >
            Apply Suggestion
          </Button>
        </div>
      </div>
    </div>
  );
}

export default PriceSuggestionModal;

