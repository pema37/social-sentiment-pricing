// Rule Form Component
// Form for creating and editing pricing rules

'use client';

import { useState, useCallback } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { cn } from '@/lib/utils';
import {
  useCreatePricingRule,
  useUpdatePricingRule,
} from '@/lib/hooks/use-pricing';
import { useProducts } from '@/lib/hooks/use-products';
import type {
  PricingRule,
  CreatePricingRuleRequest,
  RuleType,
  RuleAction,
} from '@/types';

// ============================================
// TYPES
// ============================================

interface RuleFormProps {
  /** Initial data for editing or duplicating */
  initialData?: Partial<PricingRule>;
  /** Rule ID if editing */
  ruleId?: string;
  /** Callback on successful save */
  onSuccess?: () => void;
  /** Callback on cancel */
  onCancel?: () => void;
}

interface FormData {
  product_id: string;
  name: string;
  description: string;
  rule_type: RuleType;
  is_active: boolean;
  priority: number;
  // Conditions
  sentiment_threshold: string;
  sentiment_direction: string;
  competitor_id: string;
  price_position: string;
  time_days: string;
  volume_threshold: string;
  viral_threshold_reach: string;
  // Action
  action: RuleAction;
  action_value: string;
  // Constraints
  max_change_percent: string;
  min_price: string;
  max_price: string;
  cooldown_hours: string;
}

// ============================================
// CONFIG
// ============================================

const ruleTypes: { value: RuleType; label: string; description: string }[] = [
  {
    value: 'sentiment_threshold',
    label: 'Sentiment Threshold',
    description: 'Trigger when sentiment score crosses a threshold',
  },
  {
    value: 'competitor_relative',
    label: 'Competitor Relative',
    description: 'React to competitor price changes',
  },
  {
    value: 'time_based',
    label: 'Time-Based',
    description: 'Adjust prices based on time patterns',
  },
  {
    value: 'volume_surge',
    label: 'Volume Surge',
    description: 'Respond to sudden demand increases',
  },
  {
    value: 'viral_detection',
    label: 'Viral Detection',
    description: 'Detect viral social media activity',
  },
];

const ruleActions: { value: RuleAction; label: string }[] = [
  { value: 'increase_percent', label: 'Increase by percentage' },
  { value: 'decrease_percent', label: 'Decrease by percentage' },
  { value: 'set_absolute', label: 'Set to absolute price' },
  { value: 'match_competitor', label: 'Match competitor price' },
  { value: 'undercut_competitor', label: 'Undercut competitor' },
];

const sentimentDirections = [
  { value: 'above', label: 'Above threshold' },
  { value: 'below', label: 'Below threshold' },
];

const pricePositions = [
  { value: 'below', label: 'Below competitor' },
  { value: 'match', label: 'Match competitor' },
  { value: 'above', label: 'Above competitor' },
];

// ============================================
// INITIAL STATE
// ============================================

const getInitialFormData = (initialData?: Partial<PricingRule>): FormData => ({
  product_id: initialData?.product_id ?? '',
  name: initialData?.name ?? '',
  description: initialData?.description ?? '',
  rule_type: initialData?.rule_type ?? 'sentiment_threshold',
  is_active: initialData?.is_active ?? true,
  priority: initialData?.priority ?? 10,
  sentiment_threshold: initialData?.sentiment_threshold?.toString() ?? '',
  sentiment_direction: initialData?.sentiment_direction ?? 'above',
  competitor_id: initialData?.competitor_id ?? '',
  price_position: initialData?.price_position ?? 'below',
  time_days: initialData?.time_days?.toString() ?? '',
  volume_threshold: initialData?.volume_threshold?.toString() ?? '',
  viral_threshold_reach: initialData?.viral_threshold_reach?.toString() ?? '',
  action: initialData?.action ?? 'increase_percent',
  action_value: initialData?.action_value ?? '',
  max_change_percent: initialData?.max_change_percent ?? '',
  min_price: initialData?.min_price ?? '',
  max_price: initialData?.max_price ?? '',
  cooldown_hours: initialData?.cooldown_hours?.toString() ?? '24',
});

// ============================================
// COMPONENT
// ============================================

export function RuleForm({
  initialData,
  ruleId,
  onSuccess,
  onCancel,
}: RuleFormProps) {
  const [formData, setFormData] = useState<FormData>(() =>
    getInitialFormData(initialData)
  );
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string>>>({});

  const createMutation = useCreatePricingRule();
  const updateMutation = useUpdatePricingRule();

  // Fetch products for the dropdown
  const { data: productsData, isLoading: isLoadingProducts } = useProducts();
  const products = productsData?.items ?? [];

  const isEditing = !!ruleId;
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  // Handle input change
  const handleChange = useCallback(
    (field: keyof FormData, value: string | boolean | number) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      // Clear error when field is edited
      if (errors[field]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }));
      }
    },
    [errors]
  );

  // Validate form
  const validate = useCallback((): boolean => {
    const newErrors: Partial<Record<keyof FormData, string>> = {};

    if (!formData.product_id) {
      newErrors.product_id = 'Product is required';
    }

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!formData.action_value.trim()) {
      newErrors.action_value = 'Action value is required';
    }

    // Type-specific validation
    if (formData.rule_type === 'sentiment_threshold') {
      if (!formData.sentiment_threshold) {
        newErrors.sentiment_threshold = 'Sentiment threshold is required';
      }
    }

    if (formData.rule_type === 'time_based') {
      if (!formData.time_days) {
        newErrors.time_days = 'Time period is required';
      }
    }

    if (formData.rule_type === 'volume_surge') {
      if (!formData.volume_threshold) {
        newErrors.volume_threshold = 'Volume threshold is required';
      }
    }

    if (formData.rule_type === 'viral_detection') {
      if (!formData.viral_threshold_reach) {
        newErrors.viral_threshold_reach = 'Reach threshold is required';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  // Build request payload
  const buildPayload = useCallback((): CreatePricingRuleRequest => {
    const payload: CreatePricingRuleRequest = {
      product_id: formData.product_id,
      name: formData.name.trim(),
      description: formData.description.trim() || undefined,
      rule_type: formData.rule_type,
      is_active: formData.is_active,
      priority: formData.priority,
      action: formData.action,
      action_value: formData.action_value.trim(),
      cooldown_hours: parseInt(formData.cooldown_hours) || 24,
    };

    // Add type-specific conditions
    if (formData.rule_type === 'sentiment_threshold') {
      payload.sentiment_threshold = parseFloat(formData.sentiment_threshold);
      payload.sentiment_direction = formData.sentiment_direction;
    }

    if (formData.rule_type === 'competitor_relative') {
      payload.competitor_id = formData.competitor_id || undefined;
      payload.price_position = formData.price_position;
    }

    if (formData.rule_type === 'time_based') {
      payload.time_days = parseInt(formData.time_days);
    }

    if (formData.rule_type === 'volume_surge') {
      payload.volume_threshold = parseInt(formData.volume_threshold);
    }

    if (formData.rule_type === 'viral_detection') {
      payload.viral_threshold_reach = parseInt(formData.viral_threshold_reach);
    }

    // Add constraints if provided
    if (formData.max_change_percent) {
      payload.max_change_percent = formData.max_change_percent;
    }
    if (formData.min_price) {
      payload.min_price = formData.min_price;
    }
    if (formData.max_price) {
      payload.max_price = formData.max_price;
    }

    return payload;
  }, [formData]);

  // Handle submit
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (!validate()) {
        toast.error('Please fix the errors in the form');
        return;
      }

      const payload = buildPayload();

      try {
        if (isEditing) {
          await updateMutation.mutateAsync({ id: ruleId, data: payload });
          toast.success('Rule updated successfully');
        } else {
          await createMutation.mutateAsync(payload);
          toast.success('Rule created successfully');
        }
        onSuccess?.();
      } catch (error) {
        toast.error(isEditing ? 'Failed to update rule' : 'Failed to create rule');
        console.error('Submit error:', error);
      }
    },
    [validate, buildPayload, isEditing, ruleId, updateMutation, createMutation, onSuccess]
  );

  // Render input field
  const renderInput = (
    field: keyof FormData,
    label: string,
    options?: {
      type?: string;
      placeholder?: string;
      required?: boolean;
      min?: number;
      max?: number;
      step?: number;
    }
  ) => (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {options?.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <input
        type={options?.type ?? 'text'}
        value={formData[field] as string}
        onChange={(e) => handleChange(field, e.target.value)}
        placeholder={options?.placeholder}
        min={options?.min}
        max={options?.max}
        step={options?.step}
        className={cn(
          'w-full px-3 py-2 border rounded-lg text-sm',
          'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
          errors[field] ? 'border-red-300' : 'border-gray-300'
        )}
      />
      {errors[field] && (
        <p className="mt-1 text-sm text-red-600">{errors[field]}</p>
      )}
    </div>
  );

  // Render select field
  const renderSelect = (
    field: keyof FormData,
    label: string,
    options: { value: string; label: string }[],
    required?: boolean
  ) => (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <select
        value={formData[field] as string}
        onChange={(e) => handleChange(field, e.target.value)}
        className={cn(
          'w-full px-3 py-2 border rounded-lg text-sm',
          'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
          errors[field] ? 'border-red-300' : 'border-gray-300'
        )}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {errors[field] && (
        <p className="mt-1 text-sm text-red-600">{errors[field]}</p>
      )}
    </div>
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Basic Info */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Basic Information</h2>
        <div className="space-y-4">
          {/* Product Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Product <span className="text-red-500 ml-1">*</span>
            </label>
            <select
              value={formData.product_id}
              onChange={(e) => handleChange('product_id', e.target.value)}
              disabled={isEditing}
              className={cn(
                'w-full px-3 py-2 border rounded-lg text-sm',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                errors.product_id ? 'border-red-300' : 'border-gray-300',
                isEditing && 'bg-gray-100 cursor-not-allowed'
              )}
            >
              <option value="">Select a product...</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </select>
            {errors.product_id && (
              <p className="mt-1 text-sm text-red-600">{errors.product_id}</p>
            )}
            {isLoadingProducts && (
              <p className="mt-1 text-sm text-gray-500">Loading products...</p>
            )}
          </div>

          {renderInput('name', 'Rule Name', {
            required: true,
            placeholder: 'e.g., Increase price on positive sentiment',
          })}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Describe what this rule does..."
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            {renderInput('priority', 'Priority', {
              type: 'number',
              min: 1,
              max: 100,
              placeholder: '10',
            })}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <div className="flex items-center gap-3 mt-2">
                <button
                  type="button"
                  onClick={() => handleChange('is_active', true)}
                  className={cn(
                    'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                    formData.is_active
                      ? 'bg-green-100 text-green-800 ring-2 ring-green-500'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  )}
                >
                  Active
                </button>
                <button
                  type="button"
                  onClick={() => handleChange('is_active', false)}
                  className={cn(
                    'px-4 py-2 text-sm font-medium rounded-lg transition-colors',
                    !formData.is_active
                      ? 'bg-gray-200 text-gray-800 ring-2 ring-gray-500'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  )}
                >
                  Inactive
                </button>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Rule Type */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Rule Type</h2>
        <div className="grid gap-3">
          {ruleTypes.map((type) => (
            <button
              key={type.value}
              type="button"
              onClick={() => handleChange('rule_type', type.value)}
              className={cn(
                'p-4 text-left border rounded-lg transition-colors',
                formData.rule_type === type.value
                  ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-500'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              )}
            >
              <p className="font-medium text-gray-900">{type.label}</p>
              <p className="text-sm text-gray-500 mt-1">{type.description}</p>
            </button>
          ))}
        </div>
      </Card>

      {/* Type-Specific Conditions */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Conditions</h2>
        <div className="space-y-4">
          {formData.rule_type === 'sentiment_threshold' && (
            <>
              {renderInput('sentiment_threshold', 'Sentiment Score Threshold', {
                type: 'number',
                required: true,
                min: -1,
                max: 1,
                step: 0.1,
                placeholder: '0.7',
              })}
              {renderSelect('sentiment_direction', 'Direction', sentimentDirections, true)}
            </>
          )}

          {formData.rule_type === 'competitor_relative' && (
            <>
              {renderInput('competitor_id', 'Competitor ID', {
                placeholder: 'Leave blank for any competitor',
              })}
              {renderSelect('price_position', 'Price Position', pricePositions, true)}
            </>
          )}

          {formData.rule_type === 'time_based' && (
            <>
              {renderInput('time_days', 'Time Period (days)', {
                type: 'number',
                required: true,
                min: 1,
                placeholder: '7',
              })}
            </>
          )}

          {formData.rule_type === 'volume_surge' && (
            <>
              {renderInput('volume_threshold', 'Volume Threshold (%)', {
                type: 'number',
                required: true,
                min: 1,
                placeholder: '50',
              })}
            </>
          )}

          {formData.rule_type === 'viral_detection' && (
            <>
              {renderInput('viral_threshold_reach', 'Reach Threshold', {
                type: 'number',
                required: true,
                min: 1000,
                placeholder: '10000',
              })}
            </>
          )}
        </div>
      </Card>

      {/* Action */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Action</h2>
        <div className="space-y-4">
          {renderSelect('action', 'Action Type', ruleActions, true)}

          {renderInput('action_value', 'Action Value', {
            required: true,
            placeholder:
              formData.action.includes('percent')
                ? 'e.g., 10 (for 10%)'
                : 'e.g., 29.99',
          })}
        </div>
      </Card>

      {/* Constraints */}
      <Card padding="md">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Safety Constraints</h2>
        <div className="grid grid-cols-2 gap-4">
          {renderInput('max_change_percent', 'Max Change (%)', {
            type: 'number',
            min: 0,
            max: 100,
            placeholder: '20',
          })}

          {renderInput('cooldown_hours', 'Cooldown (hours)', {
            type: 'number',
            min: 1,
            placeholder: '24',
          })}

          {renderInput('min_price', 'Min Price', {
            type: 'number',
            min: 0,
            step: 0.01,
            placeholder: '0.00',
          })}

          {renderInput('max_price', 'Max Price', {
            type: 'number',
            min: 0,
            step: 0.01,
            placeholder: '999.99',
          })}
        </div>
      </Card>

      {/* Actions */}
      <div className="flex items-center justify-end gap-3 pt-4">
        {onCancel && (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" variant="primary" disabled={isSubmitting}>
          {isSubmitting && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          {isEditing ? 'Update Rule' : 'Create Rule'}
        </Button>
      </div>
    </form>
  );
}
