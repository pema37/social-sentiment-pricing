// components/features/products/ProductRow.tsx
// FIX (2026-02-21): Added platform badges showing Shopify/WooCommerce
// connections per product. See BUG-005 in audit report.
'use client';

import { useState, useRef } from 'react';
import Link from 'next/link';
import {
  Package,
  MoreVertical,
  TrendingUp,
  TrendingDown,
  Sparkles,
  Trash2,
  Edit,
  Eye,
  Zap,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { useToggleAutoPricing, type Product } from '@/lib/hooks/use-products';
import Image from 'next/image';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ProductRowProps {
  product: Product;
  onPriceSuggestion: (product: Product) => void;
  onDelete: (product: Product) => void;
}

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
// Platform Badge Config
// ─────────────────────────────────────────────────────────────────────────────

const PLATFORM_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  shopify: {
    bg: 'bg-green-100',
    text: 'text-green-700',
    label: 'Shopify',
  },
  woocommerce: {
    bg: 'bg-purple-100',
    text: 'text-purple-700',
    label: 'Woo',
  },
};

function getPlatformStyle(platform: string) {
  return PLATFORM_STYLES[platform.toLowerCase()] ?? {
    bg: 'bg-gray-100',
    text: 'text-gray-700',
    label: platform,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

interface ProductInfoCellProps {
  product: Product;
}

// FIXED: ProductImage component with error handling and HTTPS enforcement
function ProductImage({ src, alt }: { src: string; alt: string }) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Fix mixed content: ensure HTTPS
  const safeSrc = src.replace(/^http:\/\//i, 'https://');

  if (hasError) {
    return (
      <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center">
        <Package className="w-6 h-6 text-gray-400" />
      </div>
    );
  }

  return (
    <div className="relative w-12 h-12">
      {isLoading && (
        <div className="absolute inset-0 bg-gray-100 rounded-lg animate-pulse" />
      )}
      <Image
        src={safeSrc}
        alt={alt}
        width={48}
        height={48}
        className={`w-12 h-12 rounded-lg object-cover transition-opacity ${
          isLoading ? 'opacity-0' : 'opacity-100'
        }`}
        onError={() => setHasError(true)}
        onLoad={() => setIsLoading(false)}
        // ADDED: unoptimized for external images that might have CORS issues
        unoptimized
      />
    </div>
  );
}

function ProductInfoCell({ product }: ProductInfoCellProps) {
  return (
    <div className="flex items-center gap-4">
      {product.image_url ? (
        <ProductImage src={product.image_url} alt={product.name} />
      ) : (
        <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center">
          <Package className="w-6 h-6 text-gray-400" />
        </div>
      )}
      <div>
        <p className="font-medium text-gray-900">{product.name}</p>
        <div className="flex items-center gap-2">
          <p className="text-sm text-gray-500">{product.sku || 'No SKU'}</p>
          {/* FIX BUG-005: Platform badges */}
          {product.platforms_linked && product.platforms_linked.length > 0 && (
            <div className="flex gap-1">
              {product.platforms_linked.map((pl) => {
                const style = getPlatformStyle(pl.platform);
                return (
                  <span
                    key={pl.platform}
                    className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium leading-none ${style.bg} ${style.text}`}
                    title={`Connected to ${style.label}${pl.store_url ? ` (${pl.store_url})` : ''}${pl.sync_enabled ? '' : ' — sync disabled'}`}
                  >
                    {style.label}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface PriceCellProps {
  currentPrice: number;
  basePrice: number;
}

function PriceCell({ currentPrice, basePrice }: PriceCellProps) {
  const { change, percent } = calculatePriceChange(currentPrice, basePrice);

  return (
    <div className="flex items-center gap-2">
      <span className="font-medium">{formatCurrency(currentPrice)}</span>
      {change !== 0 && (
        <div
          className={`flex items-center gap-1 text-sm ${
            change > 0 ? 'text-green-600' : 'text-red-600'
          }`}
        >
          {change > 0 ? (
            <TrendingUp className="w-4 h-4" />
          ) : (
            <TrendingDown className="w-4 h-4" />
          )}
          <span>
            {change > 0 ? '+' : ''}
            {(Number(percent ?? 0)).toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  );
}

interface AutoPricingToggleProps {
  enabled: boolean;
  onToggle: () => void;
  isPending: boolean;
}

function AutoPricingToggle({ enabled, onToggle, isPending }: AutoPricingToggleProps) {
  return (
    <button
      onClick={onToggle}
      disabled={isPending}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
        enabled
          ? 'bg-green-100 text-green-700 hover:bg-green-200'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      } ${isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <Zap className={`w-4 h-4 ${enabled ? 'text-green-600' : 'text-gray-400'}`} />
      {enabled ? 'On' : 'Off'}
    </button>
  );
}

interface ActionsMenuProps {
  product: Product;
  onPriceSuggestion: () => void;
  onDelete: () => void;
}

function ActionsMenu({ product, onPriceSuggestion, onDelete }: ActionsMenuProps) {
  const [showMenu, setShowMenu] = useState(false);
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({});
  const buttonRef = useRef<HTMLButtonElement>(null);

  const handleClick = () => {
    if (buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const menuHeight = 200; // approximate menu height
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;

      // Position below if enough space, otherwise above
      if (spaceBelow >= menuHeight || spaceBelow > spaceAbove) {
        setMenuStyle({
          top: rect.bottom + 8,
          left: rect.right - 192,
        });
      } else {
        setMenuStyle({
          bottom: window.innerHeight - rect.top + 8,
          left: rect.right - 192,
        });
      }
    }
    setShowMenu(!showMenu);
  };

  return (
    <div className="relative">
      <button
        ref={buttonRef}
        onClick={handleClick}
        className="p-2 hover:bg-gray-100 rounded-lg"
      >
        <MoreVertical className="w-5 h-5 text-gray-500" />
      </button>

      {showMenu && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setShowMenu(false)}
          />
          <div 
            className="fixed w-48 bg-white rounded-lg shadow-lg border z-50"
            style={menuStyle}
          >
            <Link
              href={`/products/${product.id}`}
              className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-gray-50"
              onClick={() => setShowMenu(false)}
            >
              <Eye className="w-4 h-4 text-gray-600" />
              <span>View Details</span>
            </Link>
            <button
              onClick={() => {
                setShowMenu(false);
                onPriceSuggestion();
              }}
              className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-gray-50"
            >
              <Sparkles className="w-4 h-4 text-blue-600" />
              <span>Price Suggestion</span>
            </button>
            <Link
              href={`/products/${product.id}/edit`}
              className="flex items-center gap-3 w-full px-4 py-3 text-left hover:bg-gray-50"
              onClick={() => setShowMenu(false)}
            >
              <Edit className="w-4 h-4 text-gray-600" />
              <span>Edit Product</span>
            </Link>
            <button
              onClick={() => {
                setShowMenu(false);
                onDelete();
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
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function ProductRow({ product, onPriceSuggestion, onDelete }: ProductRowProps) {
  const toggleAutoPricing = useToggleAutoPricing();

  const basePrice = safeNumber(product.base_price);
  const currentPrice = safeNumber(product.current_price);

  const handleToggleAutoPricing = () => {
    toggleAutoPricing.mutate({
      id: product.id,
      enabled: !product.auto_pricing_enabled,
    });
  };

  return (
    <tr className="hover:bg-gray-50">
      <td className="px-6 py-4">
        <ProductInfoCell product={product} />
      </td>

      <td className="px-6 py-4">
        {product.category ? (
          <Badge>{product.category}</Badge>
        ) : (
          <span className="text-gray-400">—</span>
        )}
      </td>

      <td className="px-6 py-4 text-gray-600">{formatCurrency(basePrice)}</td>

      <td className="px-6 py-4">
        <PriceCell currentPrice={currentPrice} basePrice={basePrice} />
      </td>

      <td className="px-6 py-4">
        <AutoPricingToggle
          enabled={product.auto_pricing_enabled}
          onToggle={handleToggleAutoPricing}
          isPending={toggleAutoPricing.isPending}
        />
      </td>

      <td className="px-6 py-4">
        <Badge variant={product.is_active ? 'success' : 'warning'}>
          {product.is_active ? 'Active' : 'Inactive'}
        </Badge>
      </td>

      <td className="px-6 py-4">
        <ActionsMenu
          product={product}
          onPriceSuggestion={() => onPriceSuggestion(product)}
          onDelete={() => onDelete(product)}
        />
      </td>
    </tr>
  );
}

export default ProductRow;



