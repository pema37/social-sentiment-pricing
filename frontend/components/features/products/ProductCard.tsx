'use client';

// components/features/products/ProductCard.tsx
import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import {
  Package,
  TrendingUp,
  TrendingDown,
  Sparkles,
  Trash2,
  Edit,
  Eye,
  Zap,
  MoreHorizontal,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { useToggleAutoPricing, type Product } from '@/lib/hooks/use-products';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function safeNumber(value: unknown, defaultValue = 0): number {
  if (value == null) return defaultValue;
  const num = Number(value);
  return isNaN(num) ? defaultValue : num;
}

function formatCurrency(value: number | string | null | undefined): string {
  const num = safeNumber(value);
  return `$${num.toFixed(2)}`;
}

function calculatePriceChange(current: number, base: number) {
  const safeCurrent = safeNumber(current);
  const safeBase = safeNumber(base);
  const change = safeCurrent - safeBase;
  const percent = safeBase > 0 ? (change / safeBase) * 100 : 0;
  return { 
    change: isNaN(change) ? 0 : change, 
    percent: isNaN(percent) ? 0 : percent 
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ProductCardProps {
  product: Product;
  onPriceSuggestion: (product: Product) => void;
  onDelete: (product: Product) => void;
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function ProductImage({ src, alt }: { src: string; alt: string }) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const safeSrc = src.replace(/^http:\/\//i, 'https://');

  if (hasError) {
    return (
      <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center shrink-0">
        <Package className="w-8 h-8 text-gray-400" />
      </div>
    );
  }

  return (
    <div className="relative w-16 h-16 shrink-0">
      {isLoading && (
        <div className="absolute inset-0 bg-gray-100 rounded-lg animate-pulse" />
      )}
      <Image
        src={safeSrc}
        alt={alt}
        width={64}
        height={64}
        className={`w-16 h-16 rounded-lg object-cover transition-opacity ${
          isLoading ? 'opacity-0' : 'opacity-100'
        }`}
        onError={() => setHasError(true)}
        onLoad={() => setIsLoading(false)}
        unoptimized
      />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function ProductCard({ product, onPriceSuggestion, onDelete }: ProductCardProps) {
  const [showActions, setShowActions] = useState(false);
  const toggleAutoPricing = useToggleAutoPricing();

  const basePrice = safeNumber(product.base_price);
  const currentPrice = safeNumber(product.current_price);
  const { change, percent } = calculatePriceChange(currentPrice, basePrice);

  const handleToggleAutoPricing = () => {
    toggleAutoPricing.mutate({
      id: product.id,
      enabled: !product.auto_pricing_enabled,
    });
  };

  return (
    <Card className="p-4">
      {/* Header: Image + Name + Status */}
      <div className="flex items-start gap-3">
        {product.image_url ? (
          <ProductImage src={product.image_url} alt={product.name} />
        ) : (
          <div className="w-16 h-16 bg-gray-100 rounded-lg flex items-center justify-center shrink-0">
            <Package className="w-8 h-8 text-gray-400" />
          </div>
        )}
        
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="font-medium text-gray-900 truncate">{product.name}</h3>
              <p className="text-sm text-gray-500 truncate">{product.sku || 'No SKU'}</p>
            </div>
            <Badge variant={product.is_active ? 'success' : 'warning'} className="shrink-0">
              {product.is_active ? 'Active' : 'Inactive'}
            </Badge>
          </div>
          
          {product.category && (
            <Badge className="mt-1">{product.category}</Badge>
          )}
        </div>
      </div>

      {/* Price Info */}
      <div className="mt-4 grid grid-cols-2 gap-4">
        <div>
          <p className="text-xs text-gray-500 uppercase">Base Price</p>
          <p className="font-medium text-gray-700">{formatCurrency(basePrice)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500 uppercase">SSP Price</p>
          <div className="flex items-center gap-1">
            <span className="font-medium text-gray-900">{formatCurrency(currentPrice)}</span>
            {change !== 0 && (
              <span className={`flex items-center text-xs ${change > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {change > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {change > 0 ? '+' : ''}{percent.toFixed(1)}%
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Auto-pricing + Actions */}
      <div className="mt-4 flex items-center justify-between border-t pt-4">
        <button
          onClick={handleToggleAutoPricing}
          disabled={toggleAutoPricing.isPending}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            product.auto_pricing_enabled
              ? 'bg-green-100 text-green-700'
              : 'bg-gray-100 text-gray-600'
          } ${toggleAutoPricing.isPending ? 'opacity-50' : ''}`}
        >
          <Zap className={`w-4 h-4 ${product.auto_pricing_enabled ? 'text-green-600' : 'text-gray-400'}`} />
          Auto: {product.auto_pricing_enabled ? 'On' : 'Off'}
        </button>

        <div className="relative">
          <button
            onClick={() => setShowActions(!showActions)}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <MoreHorizontal className="w-5 h-5 text-gray-500" />
          </button>

          {showActions && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowActions(false)} />
              <div className="absolute right-0 bottom-full mb-2 w-48 bg-white rounded-lg shadow-lg border z-50">
                <Link
                  href={`/products/${product.id}`}
                  className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-gray-50"
                  onClick={() => setShowActions(false)}
                >
                  <Eye className="w-4 h-4 text-gray-600" />
                  <span>View Details</span>
                </Link>
                <button
                  onClick={() => {
                    setShowActions(false);
                    onPriceSuggestion(product);
                  }}
                  className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-gray-50"
                >
                  <Sparkles className="w-4 h-4 text-blue-600" />
                  <span>Price Suggestion</span>
                </button>
                <Link
                  href={`/products/${product.id}/edit`}
                  className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-gray-50"
                  onClick={() => setShowActions(false)}
                >
                  <Edit className="w-4 h-4 text-gray-600" />
                  <span>Edit Product</span>
                </Link>
                <button
                  onClick={() => {
                    setShowActions(false);
                    onDelete(product);
                  }}
                  className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-gray-50 text-red-600"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Delete</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </Card>
  );
}

export default ProductCard;



