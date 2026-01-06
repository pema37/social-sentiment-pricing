// components/products/ProductInfoCard.tsx
'use client';

import { Package, Tag } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import type { Product } from '@/types';
import Image from 'next/image';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ProductInfoCardProps {
  product: Product;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function toNumber(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined) return null;
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return isNaN(num) ? null : num;
}

function formatCurrency(value: string | number | null | undefined): string {
  const num = toNumber(value);
  if (num === null) return '—';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(num);
}

function calculatePriceChange(current: string | number, base: string | number): number | null {
  const currentNum = toNumber(current);
  const baseNum = toNumber(base);
  if (currentNum === null || baseNum === null || baseNum === 0) return null;
  const change = ((currentNum - baseNum) / baseNum) * 100;
  return isNaN(change) ? null : change; // Extra safety for edge cases
}

function formatPriceChange(priceChange: number | null): string | undefined {
  if (priceChange === null || typeof priceChange !== 'number' || isNaN(priceChange)) {
    return undefined;
  }
  return `${priceChange >= 0 ? '+' : ''}${priceChange.toFixed(1)}% from base`;
}

// Fix mixed content: ensure HTTPS for external images
function ensureHttps(url: string): string {
  return url.replace(/^http:\/\//i, 'https://');
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

interface StatusBadgeProps {
  isActive: boolean;
}

function StatusBadge({ isActive }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
        isActive
          ? 'bg-green-100 text-green-800'
          : 'bg-gray-100 text-gray-800'
      }`}
    >
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

interface PriceGridItemProps {
  label: string;
  value: string;
  subValue?: string;
  subValueColor?: string;
  highlight?: boolean;
}

function PriceGridItem({ label, value, subValue, subValueColor, highlight }: PriceGridItemProps) {
  return (
    <div className={highlight ? 'bg-blue-50 p-3 rounded-lg' : ''}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`font-semibold ${highlight ? 'text-2xl text-blue-600' : 'text-lg'}`}>
        {value}
      </p>
      {subValue && (
        <p className={`text-xs ${subValueColor || 'text-gray-500'}`}>{subValue}</p>
      )}
    </div>
  );
}

interface KeywordBadgeProps {
  keyword: string;
}

function KeywordBadge({ keyword }: KeywordBadgeProps) {
  return (
    <span className="inline-flex items-center px-2.5 py-1 bg-blue-100 text-blue-800 rounded-full text-xs font-medium">
      {keyword}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function ProductInfoCard({ product }: ProductInfoCardProps) {
  const priceChange = calculatePriceChange(product.current_price, product.base_price);

  const priceChangeColor = priceChange !== null && typeof priceChange === 'number'
    ? priceChange > 0
      ? 'text-green-600'
      : priceChange < 0
        ? 'text-red-600'
        : 'text-gray-500'
    : 'text-gray-500';

  const priceChangeText = formatPriceChange(priceChange);

  return (
    <Card className="p-6">
      <div className="flex gap-6">
        {/* Product Image */}
        <div className="shrink-0">
          {product.image_url ? (
            <Image
              src={ensureHttps(product.image_url)}
              alt={product.name}
              width={96}
              height={96}
              className="w-24 h-24 object-cover rounded-lg"
            />
          ) : (
            <div className="w-24 h-24 bg-gray-100 rounded-lg flex items-center justify-center">
              <Package className="h-10 w-10 text-gray-400" />
            </div>
          )}
        </div>

        {/* Product Details */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-900 truncate">
                {product.name}
              </h2>
              <div className="flex items-center gap-3 mt-1">
                <StatusBadge isActive={product.is_active} />
                {product.sku && (
                  <span className="text-sm text-gray-500">SKU: {product.sku}</span>
                )}
                {product.category && (
                  <span className="text-sm text-gray-500">{product.category}</span>
                )}
              </div>
            </div>
          </div>

          {product.description && (
            <div 
              className="mt-3 text-gray-600 text-sm line-clamp-2 prose prose-sm"
              dangerouslySetInnerHTML={{ __html: product.description }}
            />
          )}
        </div>
      </div>

      {/* Price Grid */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-3 gap-4">
        <PriceGridItem
          label="Current Price"
          value={formatCurrency(product.current_price)}
          subValue={priceChangeText}
          subValueColor={priceChangeColor}
          highlight
        />
        <PriceGridItem
          label="Base Price"
          value={formatCurrency(product.base_price)}
        />
        <PriceGridItem
          label="Price Range"
          value={`${formatCurrency(product.min_price)} - ${formatCurrency(product.max_price)}`}
        />
      </div>

      {/* Keywords */}
      {product.keywords && product.keywords.length > 0 && (
        <div className="mt-6">
          <div className="flex items-center gap-2 mb-2">
            <Tag className="h-4 w-4 text-gray-400" />
            <span className="text-sm font-medium text-gray-700">Keywords</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {product.keywords.map((keyword, index) => (
              <KeywordBadge key={index} keyword={keyword} />
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

export default ProductInfoCard;
