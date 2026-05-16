'use client';

// components/products/ProductForm.tsx
import { useState, useMemo, useCallback } from 'react';
import { Package, DollarSign, Zap, Tag, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { CategorySelect } from '@/components/ui/CategorySelect';
import { GenerateDescriptionModal } from './GenerateDescriptionModal';
import {
  useCreateProduct,
  useUpdateProduct,
  useProducts,
} from '@/lib/hooks/use-products';
import type { Product } from '@/types/product';

// Domain layer - single source of truth for transformations
import {
  productToFormData,
  validateAndCreate,
  validateAndUpdate,
  DEFAULT_PRODUCT_FORM,
  type ProductFormData,
  type ProductFormErrors,
} from '@/lib/domain/products';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface ProductFormProps {
  product?: Product;
  onSuccess?: () => void;
  onCancel?: () => void;
}

// Extended form data to handle keywords as comma-separated string in UI
interface FormState extends Omit<ProductFormData, 'keywords'> {
  keywords_string: string; // UI shows comma-separated
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function toFormState(product?: Product): FormState {
  if (!product) {
    return {
      ...DEFAULT_PRODUCT_FORM,
      keywords_string: '',
    };
  }
  const formData = productToFormData(product);
  return {
    ...formData,
    keywords_string: formData.keywords.join(', '),
  };
}

function toFormData(state: FormState): ProductFormData {
  const { keywords_string, ...rest } = state;
  return {
    ...rest,
    keywords: keywords_string
      .split(',')
      .map(k => k.trim())
      .filter(Boolean),
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
  
  const [formState, setFormState] = useState<FormState>(() => toFormState(product));
  const [errors, setErrors] = useState<ProductFormErrors>({});
  const [showGenerateModal, setShowGenerateModal] = useState(false);

  const categories = useMemo(() => {
    const cats = new Set<string>();
    productsData?.items?.forEach(p => {
      if (p.category) cats.add(p.category);
    });
    return Array.from(cats).sort();
  }, [productsData?.items]);

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormState(prev => ({ ...prev, [name]: value }));
    if (errors[name as keyof ProductFormErrors]) {
      setErrors(prev => ({ ...prev, [name]: undefined }));
    }
  }, [errors]);

  const handleCategoryChange = useCallback((value: string) => {
    setFormState(prev => ({ ...prev, category: value }));
  }, []);

  const handleToggle = useCallback((field: 'auto_pricing_enabled' | 'is_active') => {
    setFormState(prev => ({ ...prev, [field]: !prev[field] }));
  }, []);

  const handleApplyGenerated = useCallback((fields: {
    description?: string;
    seo_title?: string;
    meta_description?: string;
    keywords?: string[];
  }) => {
    if (fields.description) {
      setFormState(prev => ({ ...prev, description: fields.description! }));
    }
    if (fields.keywords) {
      setFormState(prev => ({ ...prev, keywords_string: fields.keywords!.join(', ') }));
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const formData = toFormData(formState);
    
    if (isEdit) {
      const result = validateAndUpdate(formData);
      if (!result.success) {
        setErrors(result.errors);
        toast.error('Please fix the errors before saving');
        return;
      }
      updateProduct.mutateAsync({ id: product!.id, data: result.data })
        .then(() => onSuccess?.())
        .catch(() => {});
    } else {
      const result = validateAndCreate(formData);
      if (!result.success) {
        setErrors(result.errors);
        toast.error('Please fix the errors before saving');
        return;
      }
      createProduct.mutateAsync(result.data)
        .then(() => onSuccess?.())
        .catch(() => {});
    }
  };

  const isPending = createProduct.isPending || updateProduct.isPending;
  const canShowGenerator = isEdit && product?.id;

  return (
    <>
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Information */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-700 flex items-center gap-2">
              <Package className="w-4 h-4" />
              Basic Information
            </h3>
            {canShowGenerator && (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setShowGenerateModal(true)}
                className="flex items-center gap-2 bg-purple-50 text-purple-700 hover:bg-purple-100 border-purple-200"
              >
                <Sparkles className="w-4 h-4" />
                AI Generate
              </Button>
            )}
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Product Name <span className="text-red-500">*</span>
              </label>
              <Input
                name="name"
                value={formState.name}
                onChange={handleChange}
                placeholder="e.g., Wireless Bluetooth Headphones"
                className={errors.name ? 'border-red-500' : ''}
              />
              {errors.name && <p className="text-red-500 text-sm mt-1">{errors.name}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">SKU</label>
              <Input name="sku" value={formState.sku} onChange={handleChange} placeholder="e.g., WBH-001" />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
              <CategorySelect
                value={formState.category}
                onChange={handleCategoryChange}
                categories={categories}
                isLoading={isLoadingProducts}
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                name="description"
                value={formState.description}
                onChange={handleChange}
                placeholder="Product description..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-1">Image URL</label>
              <Input name="image_url" value={formState.image_url} onChange={handleChange} placeholder="https://example.com/image.jpg" />
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
            <PriceInput name="base_price" label="Base Price" value={formState.base_price} onChange={handleChange} error={errors.base_price} required />
            <div />
            <PriceInput name="min_price" label="Min Price" value={formState.min_price} onChange={handleChange} error={errors.min_price} />
            <PriceInput name="max_price" label="Max Price" value={formState.max_price} onChange={handleChange} error={errors.max_price} />
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
              <Input name="sentiment_multiplier" type="number" step="0.01" min="0" max="1" value={formState.sentiment_multiplier} onChange={handleChange} placeholder="0.1" />
              <p className="text-xs text-gray-500 mt-1">How much sentiment affects pricing (0.0 - 1.0). Default: 0.1 = 10% max impact</p>
            </div>
            <ToggleSwitch enabled={formState.auto_pricing_enabled} onToggle={() => handleToggle('auto_pricing_enabled')} label="Auto-Pricing" description="Automatically adjust prices based on sentiment" />
            <ToggleSwitch enabled={formState.is_active} onToggle={() => handleToggle('is_active')} label="Active" description="Product is visible and available" />
          </div>
        </Card>

        {/* Keywords */}
        <Card className="p-6">
          <h3 className="text-sm font-medium text-gray-700 mb-4 flex items-center gap-2">
            <Tag className="w-4 h-4" />
            Social Monitoring Keywords
          </h3>
          <Input name="keywords_string" value={formState.keywords_string} onChange={handleChange} placeholder="keyword1, keyword2, keyword3" />
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

      {canShowGenerator && product && (
        <GenerateDescriptionModal
          isOpen={showGenerateModal}
          onClose={() => setShowGenerateModal(false)}
          productId={product.id}
          productName={product.name}
          onApply={handleApplyGenerated}
        />
      )}
    </>
  );
}

export default ProductForm;


