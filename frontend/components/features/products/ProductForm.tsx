// components/products/ProductForm.tsx
'use client';

import { useState, useMemo } from 'react';
import { Package, DollarSign, Zap, Tag } from 'lucide-react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { CategorySelect } from '@/components/ui/CategorySelect';
import {
  useCreateProduct,
  useUpdateProduct,
  useProducts,
} from '@/lib/hooks/use-products';
import type { Product, CreateProductRequest, UpdateProductRequest } from '@/types';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ProductFormProps {
  product?: Product;
  onSuccess?: () => void;
  onCancel?: () => void;
}

interface FormData {
  name: string;
  sku: string;
  description: string;
  category: string;
  image_url: string;
  base_price: string;
  min_price: string;
  max_price: string;
  sentiment_multiplier: string;
  auto_pricing_enabled: boolean;
  is_active: boolean;
  keywords: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper
// ─────────────────────────────────────────────────────────────────────────────

function buildInitialFormData(product?: Product): FormData {
  return {
    name: product?.name || '',
    sku: product?.sku || '',
    description: product?.description || '',
    category: product?.category || '',
    image_url: product?.image_url || '',
    base_price: product?.base_price?.toString() || '',
    min_price: product?.min_price?.toString() || '',
    max_price: product?.max_price?.toString() || '',
    sentiment_multiplier: product?.sentiment_multiplier?.toString() || '0.2',
    auto_pricing_enabled: product?.auto_pricing_enabled ?? false,
    is_active: product?.is_active ?? true,
    keywords: product?.keywords?.join(', ') || '',
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

interface ToggleSwitchProps {
  enabled: boolean;
  onToggle: () => void;
  label: string;
  description: string;
}

function ToggleSwitch({ enabled, onToggle, label, description }: ToggleSwitchProps) {
  return (
    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
      <div>
        <p className="font-medium text-gray-900">{label}</p>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
      <button
        type="button"
        onClick={onToggle}
        className={`relative w-12 h-6 rounded-full transition-colors ${
          enabled ? 'bg-green-500' : 'bg-gray-300'
        }`}
      >
        <span
          className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
            enabled ? 'translate-x-7' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

interface PriceInputProps {
  name: string;
  label: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  error?: string;
  required?: boolean;
}

function PriceInput({ name, label, value, onChange, error, required }: PriceInputProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <div className="relative">
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
        <Input
          name={name}
          type="number"
          step="0.01"
          min="0"
          value={value}
          onChange={onChange}
          placeholder="0.00"
          className={`pl-7 ${error ? 'border-red-500' : ''}`}
        />
      </div>
      {error && <p className="text-red-500 text-sm mt-1">{error}</p>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────────────────────

export function ProductForm({ product, onSuccess, onCancel }: ProductFormProps) {
  const isEdit = !!product;
  
  const createProduct = useCreateProduct();
  const updateProduct = useUpdateProduct();
  const { data: productsData, isLoading: isLoadingProducts } = useProducts({ page_size: 100 });
  
  const [formData, setFormData] = useState<FormData>(() => buildInitialFormData(product));
  const [errors, setErrors] = useState<Record<string, string>>({});

  const categories = useMemo(() => {
    const cats = new Set<string>();
    productsData?.items?.forEach(p => {
      if (p.category) cats.add(p.category);
    });
    return Array.from(cats).sort();
  }, [productsData?.items]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors(prev => ({ ...prev, [name]: '' }));
  };

  const handleCategoryChange = (value: string) => {
    setFormData(prev => ({ ...prev, category: value }));
  };

  const handleToggle = (field: 'auto_pricing_enabled' | 'is_active') => {
    setFormData(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (!formData.name.trim()) newErrors.name = 'Product name is required';
    if (!formData.base_price || Number(formData.base_price) <= 0) {
      newErrors.base_price = 'Base price must be greater than 0';
    }
    if (formData.min_price && formData.max_price && Number(formData.min_price) > Number(formData.max_price)) {
      newErrors.min_price = 'Min price cannot be greater than max price';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    const data: CreateProductRequest | UpdateProductRequest = {
      name: formData.name.trim(),
      sku: formData.sku.trim() || undefined,
      description: formData.description.trim() || undefined,
      category: formData.category.trim() || undefined,
      image_url: formData.image_url.trim() || undefined,
      base_price: Number(formData.base_price),
      min_price: formData.min_price ? Number(formData.min_price) : undefined,
      max_price: formData.max_price ? Number(formData.max_price) : undefined,
      sentiment_multiplier: Number(formData.sentiment_multiplier) || 0.2,
      auto_pricing_enabled: formData.auto_pricing_enabled,
      is_active: formData.is_active,
      keywords: formData.keywords ? formData.keywords.split(',').map(k => k.trim()).filter(Boolean) : [],
    };

    if (isEdit && product) {
      updateProduct.mutate({ id: product.id, data }, { onSuccess });
    } else {
      createProduct.mutate(data as CreateProductRequest, { onSuccess });
    }
  };

  const isPending = createProduct.isPending || updateProduct.isPending;

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Basic Information */}
      <Card className="p-6">
        <h3 className="text-sm font-medium text-gray-700 mb-4 flex items-center gap-2">
          <Package className="w-4 h-4" />
          Basic Information
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Product Name <span className="text-red-500">*</span>
            </label>
            <Input
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="e.g., Wireless Bluetooth Headphones"
              className={errors.name ? 'border-red-500' : ''}
            />
            {errors.name && <p className="text-red-500 text-sm mt-1">{errors.name}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">SKU</label>
            <Input name="sku" value={formData.sku} onChange={handleChange} placeholder="e.g., WBH-001" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
            <CategorySelect
              value={formData.category}
              onChange={handleCategoryChange}
              categories={categories}
              isLoading={isLoadingProducts}
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              placeholder="Product description..."
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Image URL</label>
            <Input name="image_url" value={formData.image_url} onChange={handleChange} placeholder="https://example.com/image.jpg" />
          </div>
        </div>
      </Card>

      {/* Pricing */}
      <Card className="p-6">
        <h3 className="text-sm font-medium text-gray-700 mb-4 flex items-center gap-2">
          <DollarSign className="w-4 h-4" />
          Pricing
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <PriceInput name="base_price" label="Base Price" value={formData.base_price} onChange={handleChange} error={errors.base_price} required />
          <div />
          <PriceInput name="min_price" label="Min Price" value={formData.min_price} onChange={handleChange} error={errors.min_price} />
          <PriceInput name="max_price" label="Max Price" value={formData.max_price} onChange={handleChange} />
        </div>
      </Card>

      {/* Auto-Pricing Settings */}
      <Card className="p-6">
        <h3 className="text-sm font-medium text-gray-700 mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4" />
          Auto-Pricing Settings
        </h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Sentiment Multiplier</label>
            <Input name="sentiment_multiplier" type="number" step="0.01" min="0" max="1" value={formData.sentiment_multiplier} onChange={handleChange} placeholder="0.2" />
            <p className="text-xs text-gray-500 mt-1">How much sentiment affects pricing (0.0 - 1.0). Default: 0.2 = 20% max impact</p>
          </div>
          <ToggleSwitch enabled={formData.auto_pricing_enabled} onToggle={() => handleToggle('auto_pricing_enabled')} label="Auto-Pricing" description="Automatically adjust prices based on sentiment" />
          <ToggleSwitch enabled={formData.is_active} onToggle={() => handleToggle('is_active')} label="Active" description="Product is visible and available" />
        </div>
      </Card>

      {/* Keywords */}
      <Card className="p-6">
        <h3 className="text-sm font-medium text-gray-700 mb-4 flex items-center gap-2">
          <Tag className="w-4 h-4" />
          Social Monitoring Keywords
        </h3>
        <Input name="keywords" value={formData.keywords} onChange={handleChange} placeholder="keyword1, keyword2, keyword3" />
        <p className="text-xs text-gray-500 mt-1">Comma-separated keywords to track on social media for this product</p>
      </Card>

      {/* Actions */}
      <div className="flex gap-3">
        {onCancel && <Button type="button" variant="secondary" onClick={onCancel} className="flex-1">Cancel</Button>}
        <Button type="submit" isLoading={isPending} className={onCancel ? 'flex-1' : 'w-full'}>
          {isEdit ? 'Save Changes' : 'Create Product'}
        </Button>
      </div>
    </form>
  );
}

export default ProductForm;
