import { memo } from 'react';
import { cn } from '@/lib/utils';

interface ProductSelectorProps {
  value: string | null;
  onChange: (productId: string | null) => void;
  products: { id: string; name: string }[];
  isLoading: boolean;
  className?: string;
}

export const ProductSelector = memo(function ProductSelector({ value, onChange, products, isLoading, className }: ProductSelectorProps) {
  return (
    <div className={cn('relative', className)}>
      <label htmlFor="product-selector" className="sr-only">Select a product</label>
      <select
        id="product-selector"
        value={value || ''}
        onChange={(e) => onChange(e.target.value || null)}
        className="px-3 py-1.5 text-sm rounded-md border border-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 min-w-45"
        disabled={isLoading}
        aria-busy={isLoading}
      >
        <option value="">All Products</option>
        {products.map((product) => (
          <option key={product.id} value={product.id}>{product.name}</option>
        ))}
      </select>
    </div>
  );
});
