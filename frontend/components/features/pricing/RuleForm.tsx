// frontend/components/features/pricing/RuleForm.tsx

'use client';

import { useState, useCallback, useMemo } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { useCreatePricingRule, useUpdatePricingRule } from '@/lib/hooks/use-pricing';
import { useProducts } from '@/lib/hooks/use-products';
import type { PricingRule } from '@/types';

// Domain layer - single source of truth for transformations
import {
  ruleToFormData,
  formDataToRequest,
  validateRuleForm,
  DEFAULT_FORM_DATA,
  type RuleFormData,
  type RuleFormErrors,
} from '@/lib/domain/pricing';

import {
  RuleFormBasic,
  RuleFormScope,
  RuleFormConditions,
  RuleFormActions,
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
// COMPONENT
// ============================================

export function RuleForm({ initialData, ruleId, onSuccess, onCancel }: RuleFormProps) {
  // Transform API data to form data using domain layer
  const [formData, setFormData] = useState<RuleFormData>(() =>
    initialData ? ruleToFormData(initialData) : DEFAULT_FORM_DATA
  );
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
    // Use domain layer validation
    const errs = validateRuleForm(formData);
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }, [formData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return toast.error('Please fix the errors before submitting');

    try {
      // Transform form data to API request using domain layer
      const payload = formDataToRequest(formData);

      if (isEditing) {
        await updateMutation.mutateAsync({ id: ruleId, data: payload });
        toast.success('Rule updated');
      } else {
        await createMutation.mutateAsync(payload);
        toast.success('Rule created');
      }
      onSuccess?.();
    } catch (err) {
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


