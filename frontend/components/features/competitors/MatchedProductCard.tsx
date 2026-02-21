// frontend/components/features/competitors/MatchedProductCard.tsx

'use client';

import { useState } from 'react';
import Image from 'next/image';
import {
  ExternalLink,
  Star,
  Package,
  Link as LinkIcon,
  Check,
  AlertCircle,
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { MatchConfidenceBadge, ConfidenceBar } from './MatchConfidenceBadge';
import type { MatchedProduct } from '@/types';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface MatchedProductCardProps {
  product: MatchedProduct;
  ourPrice?: string | number | null;
  onLink?: (product: MatchedProduct) => void;
  isLinking?: boolean;
  isLinked?: boolean;
  showConfidenceBar?: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function formatPrice(price: string | null, currency: string = 'USD'): string {
  if (!price) return 'Price N/A';
  
  const num = parseFloat(price);
  if (isNaN(num)) return 'Price N/A';
  
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(num);
}

function getPriceDifference(
  competitorPrice: string | null,
  ourPrice?: string | number | null
): { diff: number; percent: number; label: string; color: string } | null {
  if (!competitorPrice || ourPrice === undefined || ourPrice === null) return null;
  
  const competitor = parseFloat(competitorPrice);
  const ours = typeof ourPrice === 'string' ? parseFloat(ourPrice) : ourPrice;
  
  if (isNaN(competitor) || isNaN(ours) || ours === 0) return null;
  
  const diff = competitor - ours;
  const percent = (diff / ours) * 100;
  
  if (diff > 0) {
    return {
      diff,
      percent,
      label: `${percent.toFixed(1)}% higher`,
      color: 'text-green-600', // Good for us - competitor is more expensive
    };
  } else if (diff < 0) {
    return {
      diff,
      percent,
      label: `${Math.abs(percent).toFixed(1)}% lower`,
      color: 'text-red-600', // Competitor is cheaper
    };
  }
  
  return { diff: 0, percent: 0, label: 'Same price', color: 'text-gray-600' };
}

function getSourceLabel(source: string): string {
  switch (source) {
    case 'serpapi_google_shopping':
      return 'Google Shopping';
    case 'google_custom_search':
      return 'Google';
    case 'duckduckgo':
      return 'DuckDuckGo';
    default:
      return source;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function ProductImage({ src, alt }: { src: string | null; alt: string }) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  if (!src || hasError) {
    return (
      <div className="w-20 h-20 bg-gray-100 rounded-lg flex items-center justify-center shrink-0">
        <Package className="w-8 h-8 text-gray-400" />
      </div>
    );
  }

  return (
    <div className="relative w-20 h-20 shrink-0">
      {isLoading && (
        <div className="absolute inset-0 bg-gray-100 rounded-lg animate-pulse" />
      )}
      <Image
        src={src}
        alt={alt}
        width={80}
        height={80}
        className={`w-20 h-20 rounded-lg object-cover transition-opacity ${
          isLoading ? 'opacity-0' : 'opacity-100'
        }`}
        onError={() => setHasError(true)}
        onLoad={() => setIsLoading(false)}
        unoptimized
      />
    </div>
  );
}

function RatingDisplay({ rating, reviews }: { rating: number | null; reviews: number | null }) {
  if (!rating) return null;

  return (
    <div className="flex items-center gap-1 text-sm">
      <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
      <span className="font-medium">{rating.toFixed(1)}</span>
      {reviews !== null && (
        <span className="text-gray-500">({reviews.toLocaleString()})</span>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function MatchedProductCard({
  product,
  ourPrice,
  onLink,
  isLinking = false,
  isLinked = false,
  showConfidenceBar = false,
}: MatchedProductCardProps) {
  const priceDiff = getPriceDifference(product.price, ourPrice);

  return (
    <Card className="p-4 hover:shadow-md transition-shadow">
      <div className="flex gap-4">
        {/* Product Image */}
        <ProductImage src={product.image_url} alt={product.title} />

        {/* Product Info */}
        <div className="flex-1 min-w-0">
          {/* Title & Confidence */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3 className="font-medium text-gray-900 line-clamp-2 flex-1">
              {product.title}
            </h3>
            <MatchConfidenceBadge score={product.confidence_score} size="sm" />
          </div>

          {/* Merchant & Source */}
          <div className="flex items-center gap-2 mb-2">
            <Badge variant="default" className="text-xs">
              {product.merchant}
            </Badge>
            <span className="text-xs text-gray-400">
              via {getSourceLabel(product.source)}
            </span>
          </div>

          {/* Price & Rating Row */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              {/* Price */}
              <span className="text-lg font-semibold text-gray-900">
                {formatPrice(product.price, product.currency)}
              </span>
              
              {/* Price difference */}
              {priceDiff && (
                <span className={`text-sm ${priceDiff.color}`}>
                  {priceDiff.label}
                </span>
              )}
            </div>

            {/* Rating */}
            <RatingDisplay rating={product.rating} reviews={product.reviews_count} />
          </div>

          {/* Stock Status */}
          {!product.in_stock && (
            <div className="flex items-center gap-1 text-sm text-red-600 mb-2">
              <AlertCircle className="w-4 h-4" />
              <span>Out of Stock</span>
            </div>
          )}

          {/* Confidence Bar (optional) */}
          {showConfidenceBar && (
            <div className="mb-3">
              <ConfidenceBar score={product.confidence_score} height="sm" />
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 mt-3">
            {/* View Product Button */}
            <Button
              variant="secondary"
              size="sm"
              onClick={() => window.open(product.url, '_blank', 'noopener,noreferrer')}
            >
              <ExternalLink className="w-4 h-4 mr-1" />
              View
            </Button>

            {/* Link Button */}
            {onLink && !isLinked && (
              <Button
                size="sm"
                onClick={() => onLink(product)}
                disabled={isLinking}
              >
                {isLinking ? (
                  <>
                    <div className="w-4 h-4 mr-1 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Linking...
                  </>
                ) : (
                  <>
                    <LinkIcon className="w-4 h-4 mr-1" />
                    Link Competitor
                  </>
                )}
              </Button>
            )}

            {/* Linked indicator */}
            {isLinked && (
              <span className="inline-flex items-center gap-1 text-sm text-green-600">
                <Check className="w-4 h-4" />
                Linked
              </span>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

export default MatchedProductCard;



