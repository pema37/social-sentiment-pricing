// Product summary card for dashboard grid
'use client';

import Link from 'next/link';
import { Bell } from 'lucide-react';
import type { ProductSummary } from '@/types/product';

interface ProductSummaryCardProps {
  product: ProductSummary;
}

export function ProductSummaryCard({ product }: ProductSummaryCardProps) {
  // Safe fallback for price_change_percent
  const priceChangePercent = product.price_change_percent ?? 0;
  // Safe fallback for sentiment_score
  const sentimentScore = product.sentiment_score ?? null;
  // Safe parse for current_price
  const currentPrice = parseFloat(product.current_price || '0') || 0;

  const priceChangeColor =
    priceChangePercent > 0
      ? 'text-green-600'
      : priceChangePercent < 0
      ? 'text-red-600'
      : 'text-gray-500';

  return (
    <Link
      href={`/products/${product.id}`}
      className="block p-4 border border-gray-200 rounded-lg hover:border-gray-300 hover:shadow-sm transition-all"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">{product.name}</h3>
          {product.sku && (
            <p className="text-xs text-gray-500 mt-0.5">SKU: {product.sku}</p>
          )}
        </div>
        {product.auto_pricing_enabled && (
          <span className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full shrink-0 ml-2">
            Auto
          </span>
        )}
      </div>

      <div className="mt-3 flex items-end justify-between">
        <div>
          <p className="text-lg font-semibold text-gray-900">
            ${currentPrice.toFixed(2)}
          </p>
          <p className={`text-sm ${priceChangeColor}`}>
            {priceChangePercent > 0 ? '+' : ''}
            {(priceChangePercent ?? 0).toFixed(1)}% from base
          </p>
        </div>
        <div className="text-right">
          {sentimentScore !== null && typeof sentimentScore === 'number' && (
            <p
              className={`text-sm font-medium ${
                sentimentScore >= 0 ? 'text-green-600' : 'text-red-600'
              }`}
            >
              {sentimentScore >= 0 ? '+' : ''}
              {(sentimentScore ?? 0).toFixed(2)}
            </p>
          )}
          <p className="text-xs text-gray-500">{product.mention_count_24h ?? 0} mentions</p>
        </div>
      </div>

      {product.has_pending_recommendation && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <span className="text-xs text-amber-600 flex items-center gap-1">
            <Bell className="w-3 h-3" />
            Pending recommendation
          </span>
        </div>
      )}
    </Link>
  );
}

