// frontend/components/features/pricing/rule-form/RuleFormScope.tsx

'use client';

import { Check, X } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { cn } from '@/lib/utils';
import type { Product } from '@/types';
import type { RuleFormSectionProps, ScopeType } from './types';

interface RuleFormScopeProps extends RuleFormSectionProps {
  products: Product[];
  categories: string[];
  isLoading?: boolean;
}

const scopeTypes: { value: ScopeType; label: string; description: string }[] = [
  { value: 'single', label: 'Single Product', description: 'Apply to one product' },
  { value: 'multiple', label: 'Multiple Products', description: 'Select specific products' },
  { value: 'categories', label: 'By Category', description: 'All products in categories' },
  { value: 'all', label: 'All Products', description: 'Apply to all products' },
];

export function RuleFormScope({ data, errors, onChange, products, categories, isLoading }: RuleFormScopeProps) {
  const toggleProduct = (id: string) => {
    const current = data.applies_to_products;
    onChange('applies_to_products', current.includes(id) ? current.filter(x => x !== id) : [...current, id]);
  };

  const toggleCategory = (cat: string) => {
    const current = data.applies_to_categories;
    onChange('applies_to_categories', current.includes(cat) ? current.filter(x => x !== cat) : [...current, cat]);
  };

  return (
    <Card padding="md">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Apply Rule To</h2>

      {/* Scope Type Buttons */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        {scopeTypes.map((type) => (
          <button
            key={type.value}
            type="button"
            onClick={() => onChange('scope_type', type.value)}
            className={cn(
              'p-3 text-left border rounded-lg transition-colors',
              data.scope_type === type.value
                ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-500'
                : 'border-gray-200 hover:border-gray-300'
            )}
          >
            <p className="font-medium text-gray-900 text-sm">{type.label}</p>
            <p className="text-xs text-gray-500">{type.description}</p>
          </button>
        ))}
      </div>

      {/* Single Product */}
      {data.scope_type === 'single' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Select Product <span className="text-red-500">*</span>
          </label>
          <select
            value={data.product_id}
            onChange={(e) => onChange('product_id', e.target.value)}
            className={cn(
              'w-full px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500',
              errors.product_id ? 'border-red-300' : 'border-gray-300'
            )}
          >
            <option value="">Select a product...</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          {errors.product_id && <p className="mt-1 text-sm text-red-600">{errors.product_id}</p>}
        </div>
      )}

      {/* Multiple Products */}
      {data.scope_type === 'multiple' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Products <span className="text-red-500">*</span>
          </label>
          <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg divide-y">
            {isLoading ? (
              <p className="p-4 text-center text-gray-500">Loading...</p>
            ) : products.map((p) => {
              const selected = data.applies_to_products.includes(p.id);
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => toggleProduct(p.id)}
                  className={cn('w-full px-4 py-2 flex justify-between text-left', selected && 'bg-blue-50')}
                >
                  <span className="text-sm">{p.name}</span>
                  <div className={cn('w-5 h-5 rounded border flex items-center justify-center',
                    selected ? 'bg-blue-500 border-blue-500' : 'border-gray-300'
                  )}>
                    {selected && <Check className="w-3 h-3 text-white" />}
                  </div>
                </button>
              );
            })}
          </div>
          {data.applies_to_products.length > 0 && (
            <p className="mt-2 text-sm text-gray-600">{data.applies_to_products.length} selected</p>
          )}
          {errors.applies_to_products && <p className="mt-1 text-sm text-red-600">{errors.applies_to_products}</p>}
        </div>
      )}

      {/* Categories */}
      {data.scope_type === 'categories' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Categories <span className="text-red-500">*</span>
          </label>
          {categories.length === 0 ? (
            <p className="p-4 text-center text-gray-500 border rounded-lg">No categories found</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {categories.map((cat) => {
                const selected = data.applies_to_categories.includes(cat);
                const count = products.filter(p => p.category === cat).length;
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => toggleCategory(cat)}
                    className={cn(
                      'px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2',
                      selected ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    )}
                  >
                    {cat}
                    <span className={cn('px-1.5 py-0.5 rounded text-xs', selected ? 'bg-blue-600' : 'bg-gray-200')}>
                      {count}
                    </span>
                    {selected && <X className="w-3 h-3" />}
                  </button>
                );
              })}
            </div>
          )}
          {errors.applies_to_categories && <p className="mt-1 text-sm text-red-600">{errors.applies_to_categories}</p>}
        </div>
      )}

      {/* All Products */}
      {data.scope_type === 'all' && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>Applies to all {products.length} products</strong>, including future ones.
          </p>
        </div>
      )}
    </Card>
  );
}
