// frontend/components/features/pricing/RuleForm.tsx

'use client';

import { useState, useCallback, useMemo } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { useCreatePricingRule, useUpdatePricingRule } from '@/lib/hooks/use-pricing';
import { useProducts } from '@/lib/hooks/use-products';
import type { PricingRule, CreatePricingRuleRequest } from '@/types';

import {
  RuleFormBasic,
  RuleFormScope,
  RuleFormConditions,
  RuleFormActions,
  type RuleFormData,
  type RuleFormErrors,
} from './rule-form';

// ============================================
// PROPS
// ============================================

interface RuleFormProps {
  initialData?: Partial<PricingRule>;
  ruleId?: string;
  onSuccess?: () => void;
  onCancel?: () => void;
}

// ============================================
// HELPERS
// ============================================

/**
 * FIXED: Parse and normalize string to valid decimal string for API
 * - Handles empty strings → undefined
 * - Handles ".00" → "0.00" (Pydantic requires leading zero)
 * - Handles "5%" → "5" (strips % sign)
 * - Returns undefined for invalid values
 * - Returns STRING for TypeScript compatibility
 */
function normalizeDecimalString(value: string | undefined | null): string | undefined {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }
  
  // Remove % sign if present (user might type "5%")
  let cleaned = value.toString().trim().replace(/%/g, '');
  
  // Handle ".00" → "0.00" (add leading zero - required by Pydantic Decimal)
  if (cleaned.startsWith('.')) {
    cleaned = '0' + cleaned;
  }
  
  // Handle "-.5" → "-0.5"
  if (cleaned.startsWith('-.')) {
    cleaned = '-0' + cleaned.substring(1);
  }
  
  // Handle empty after cleanup
  if (cleaned === '' || cleaned === '-') {
    return undefined;
  }
  
  // Validate it's a valid number
  const num = parseFloat(cleaned);
  if (isNaN(num)) {
    return undefined;
  }
  
  // Return the cleaned string (not the number) for TypeScript
  return cleaned;
}

/**
 * Check if a string represents a valid decimal
 */
function isValidDecimal(value: string | undefined | null): boolean {
  return normalizeDecimalString(value) !== undefined;
}

/**
 * Parse string to integer, handling edge cases
 */
function parseInteger(value: string | undefined | null): number | undefined {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }
  
  const num = parseInt(value.toString().trim(), 10);
  
  if (isNaN(num)) {
    return undefined;
  }
  
  return num;
}

const getInitialData = (data?: Partial<PricingRule>): RuleFormData => {
  const scopeType = data?.applies_to_all_products ? 'all'
    : data?.applies_to_categories?.length ? 'categories'
    : data?.applies_to_products?.length ? 'multiple'
    : 'single';

  return {
    name: data?.name ?? '',
    description: data?.description ?? '',
    rule_type: data?.rule_type ?? 'sentiment_threshold',
    is_active: data?.is_active ?? true,
    priority: data?.priority ?? 10,
    scope_type: scopeType,
    product_id: data?.product_id ?? '',
    applies_to_products: data?.applies_to_products ?? [],
    applies_to_categories: data?.applies_to_categories ?? [],
    sentiment_threshold: data?.sentiment_threshold?.toString() ?? '',
    sentiment_direction: data?.sentiment_direction ?? 'above',
    competitor_id: data?.competitor_id ?? '',
    price_position: data?.price_position ?? 'below',
    time_days: data?.time_days ?? '',
    volume_threshold: data?.volume_threshold?.toString() ?? '',
    viral_threshold_reach: data?.viral_threshold_reach?.toString() ?? '',
    action: data?.action ?? 'increase_percent',
    action_value: data?.action_value ?? '',
    max_change_percent: data?.max_change_percent ?? '',
    min_price: data?.min_price ?? '',
    max_price: data?.max_price ?? '',
    cooldown_hours: data?.cooldown_hours?.toString() ?? '24',
  };
};

// Actions that don't require a value input
const ACTIONS_WITHOUT_VALUE = ['match_competitor'];

// ============================================
// COMPONENT
// ============================================

export function RuleForm({ initialData, ruleId, onSuccess, onCancel }: RuleFormProps) {
  const [formData, setFormData] = useState<RuleFormData>(() => getInitialData(initialData));
  const [errors, setErrors] = useState<RuleFormErrors>({});

  const createMutation = useCreatePricingRule();
  const updateMutation = useUpdatePricingRule();
  const { data: productsData, isLoading: isLoadingProducts } = useProducts();

  const products = useMemo(() => productsData?.items ?? [], [productsData?.items]);
  const categories = useMemo(() => {
    const cats = new Set<string>();
    products.forEach(p => { if (p.category) cats.add(p.category); });
    return Array.from(cats).sort();
  }, [products]);

  const isEditing = !!ruleId;
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  const handleChange = useCallback((field: keyof RuleFormData, value: string | boolean | number | string[]) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: undefined }));
  }, [errors]);

  const validate = useCallback((): boolean => {
    const errs: RuleFormErrors = {};

    if (!formData.name.trim()) errs.name = 'Name is required';
    
    // Only require action_value for actions that need it
    if (!ACTIONS_WITHOUT_VALUE.includes(formData.action) && !formData.action_value.trim()) {
      errs.action_value = 'Action value is required';
    }
    
    // FIXED: Validate action_value is a valid number
    if (!ACTIONS_WITHOUT_VALUE.includes(formData.action) && formData.action_value.trim()) {
      if (!isValidDecimal(formData.action_value)) {
        errs.action_value = 'Must be a valid number';
      }
    }

    // FIXED: Validate decimal fields
    if (formData.max_change_percent && !isValidDecimal(formData.max_change_percent)) {
      errs.max_change_percent = 'Must be a valid number (e.g., 5 or 5.5)';
    }
    if (formData.min_price && !isValidDecimal(formData.min_price)) {
      errs.min_price = 'Must be a valid price (e.g., 0.00 or 10.99)';
    }
    if (formData.max_price && !isValidDecimal(formData.max_price)) {
      errs.max_price = 'Must be a valid price (e.g., 99.99)';
    }

    // Scope validation
    if (formData.scope_type === 'single' && !formData.product_id) errs.product_id = 'Select a product';
    if (formData.scope_type === 'multiple' && !formData.applies_to_products.length) errs.applies_to_products = 'Select at least one product';
    if (formData.scope_type === 'categories' && !formData.applies_to_categories.length) errs.applies_to_categories = 'Select at least one category';

    // Type-specific validation
    if (formData.rule_type === 'sentiment_threshold' && !formData.sentiment_threshold) errs.sentiment_threshold = 'Required';
    if (formData.rule_type === 'time_based' && !formData.time_days) errs.time_days = 'Required';
    if (formData.rule_type === 'volume_surge' && !formData.volume_threshold) errs.volume_threshold = 'Required';
    if (formData.rule_type === 'viral_detection' && !formData.viral_threshold_reach) errs.viral_threshold_reach = 'Required';

    setErrors(errs);
    return Object.keys(errs).length === 0;
  }, [formData]);

  const buildPayload = useCallback((): CreatePricingRuleRequest => {
    // FIXED: Normalize action_value to valid decimal string
    const actionValueStr = ACTIONS_WITHOUT_VALUE.includes(formData.action) 
      ? '0' 
      : (normalizeDecimalString(formData.action_value) ?? '0');
    
    const payload: CreatePricingRuleRequest = {
      name: formData.name.trim(),
      description: formData.description.trim() || undefined,
      rule_type: formData.rule_type,
      is_active: formData.is_active,
      priority: formData.priority,
      action: formData.action,
      action_value: actionValueStr,  // FIXED: String for TypeScript, normalized for Pydantic
      cooldown_hours: parseInt(formData.cooldown_hours) || 24,
    };

    // Scoping
    if (formData.scope_type === 'single') {
      payload.product_id = formData.product_id;
      payload.applies_to_all_products = false;
    } else if (formData.scope_type === 'multiple') {
      payload.applies_to_products = formData.applies_to_products;
      payload.applies_to_all_products = false;
    } else if (formData.scope_type === 'categories') {
      payload.applies_to_categories = formData.applies_to_categories;
      payload.applies_to_all_products = false;
    } else {
      payload.applies_to_all_products = true;
    }

    // Type-specific - sentiment_threshold needs to be a number for the API
    if (formData.rule_type === 'sentiment_threshold') {
      const threshold = normalizeDecimalString(formData.sentiment_threshold);
      payload.sentiment_threshold = threshold ? parseFloat(threshold) : undefined;
      payload.sentiment_direction = formData.sentiment_direction;
    }
    if (formData.rule_type === 'competitor_relative') {
      payload.competitor_id = formData.competitor_id || undefined;
      payload.price_position = formData.price_position;
    }
    if (formData.rule_type === 'time_based') payload.time_days = formData.time_days;
    if (formData.rule_type === 'volume_surge') payload.volume_threshold = parseInteger(formData.volume_threshold);
    if (formData.rule_type === 'viral_detection') payload.viral_threshold_reach = parseInteger(formData.viral_threshold_reach);

    // FIXED: Constraints - normalize to valid decimal strings
    const maxChangePercent = normalizeDecimalString(formData.max_change_percent);
    const minPrice = normalizeDecimalString(formData.min_price);
    const maxPrice = normalizeDecimalString(formData.max_price);
    
    if (maxChangePercent !== undefined) payload.max_change_percent = maxChangePercent;
    if (minPrice !== undefined) payload.min_price = minPrice;
    if (maxPrice !== undefined) payload.max_price = maxPrice;

    return payload;
  }, [formData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return toast.error('Please fix the errors before submitting');

    try {
      if (isEditing) {
        await updateMutation.mutateAsync({ id: ruleId, data: buildPayload() });
        toast.success('Rule updated');
      } else {
        await createMutation.mutateAsync(buildPayload());
        toast.success('Rule created');
      }
      onSuccess?.();
    } catch (err) {
      // FIXED: Show more specific error message if available
      const message = err instanceof Error ? err.message : 'Unknown error';
      toast.error(isEditing ? `Failed to update: ${message}` : `Failed to create: ${message}`);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <RuleFormBasic data={formData} errors={errors} onChange={handleChange} />
      <RuleFormScope data={formData} errors={errors} onChange={handleChange} products={products} categories={categories} isLoading={isLoadingProducts} />
      <RuleFormConditions data={formData} errors={errors} onChange={handleChange} />
      <RuleFormActions data={formData} errors={errors} onChange={handleChange} />

      <div className="flex justify-end gap-3 pt-4">
        {onCancel && <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>}
        <Button type="submit" variant="primary" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          {isEditing ? 'Update Rule' : 'Create Rule'}
        </Button>
      </div>
    </form>
  );
}

