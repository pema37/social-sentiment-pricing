// frontend/lib/domain/pricing.ts
// Domain layer: Transforms between form data and API shapes
// Single place to fix when API changes - components don't know API details

import { z } from 'zod';
import type { PricingRule, CreatePricingRuleRequest, RuleType, RuleAction } from '@/types';

// ============================================
// ZOD SCHEMAS
// ============================================

/** Valid rule types */
const ruleTypes = [
  'sentiment_threshold',
  'competitor_relative',
  'time_based',
  'volume_surge',
  'viral_detection',
] as const;

/** Valid rule actions */
const ruleActions = [
  'increase_percent',
  'decrease_percent',
  'set_absolute',
  'match_competitor',
  'undercut_competitor',
] as const;

/** Actions that don't require a value input */
const ACTIONS_WITHOUT_VALUE: RuleAction[] = ['match_competitor'];

/**
 * Custom Zod transformer for decimal strings
 * - Handles empty strings → undefined
 * - Handles ".5" → "0.5"
 * - Handles "5%" → "5"
 * - Returns undefined for invalid values
 */
const decimalString = z.string().transform((val) => {
  if (val === '') return undefined;
  
  let cleaned = val.trim().replace(/%/g, '');
  
  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  if (cleaned.startsWith('-.')) cleaned = '-0' + cleaned.substring(1);
  if (cleaned === '' || cleaned === '-') return undefined;
  
  const num = parseFloat(cleaned);
  return isNaN(num) ? undefined : cleaned;
});

/**
 * Zod schema for validating a decimal string is valid
 */
const validDecimalString = z.string().refine((val) => {
  if (val === '') return true; // Empty is okay (optional)
  let cleaned = val.trim().replace(/%/g, '');
  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  if (cleaned.startsWith('-.')) cleaned = '-0' + cleaned.substring(1);
  if (cleaned === '' || cleaned === '-') return true;
  return !isNaN(parseFloat(cleaned));
}, { message: 'Must be a valid number' });

/**
 * Form data schema - validates the raw form input
 */
export const ruleFormSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  description: z.string(),
  rule_type: z.enum(ruleTypes),
  is_active: z.boolean(),
  priority: z.number().int().min(0).max(100),
  scope_type: z.enum(['single', 'multiple', 'categories', 'all']),
  product_id: z.string(),
  applies_to_products: z.array(z.string()),
  applies_to_categories: z.array(z.string()),
  sentiment_threshold: validDecimalString,
  sentiment_direction: z.string(),
  competitor_id: z.string(),
  price_position: z.string(),
  time_days: z.string(),
  volume_threshold: z.string(),
  viral_threshold_reach: z.string(),
  action: z.enum(ruleActions),
  action_value: z.string(),
  max_change_percent: validDecimalString,
  min_price: validDecimalString,
  max_price: validDecimalString,
  cooldown_hours: z.string(),
}).superRefine((data, ctx) => {
  // Conditional validation based on scope_type
  if (data.scope_type === 'single' && !data.product_id) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Select a product',
      path: ['product_id'],
    });
  }
  if (data.scope_type === 'multiple' && data.applies_to_products.length === 0) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Select at least one product',
      path: ['applies_to_products'],
    });
  }
  if (data.scope_type === 'categories' && data.applies_to_categories.length === 0) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Select at least one category',
      path: ['applies_to_categories'],
    });
  }

  // Conditional validation based on rule_type
  if (data.rule_type === 'sentiment_threshold' && !data.sentiment_threshold) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Required',
      path: ['sentiment_threshold'],
    });
  }
  if (data.rule_type === 'time_based' && !data.time_days) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Required',
      path: ['time_days'],
    });
  }
  if (data.rule_type === 'volume_surge' && !data.volume_threshold) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Required',
      path: ['volume_threshold'],
    });
  }
  if (data.rule_type === 'viral_detection' && !data.viral_threshold_reach) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Required',
      path: ['viral_threshold_reach'],
    });
  }

  // Action value required for most actions
  if (!ACTIONS_WITHOUT_VALUE.includes(data.action) && !data.action_value.trim()) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Action value is required',
      path: ['action_value'],
    });
  }
});

// ============================================
// TYPES
// ============================================

export type ScopeType = 'single' | 'multiple' | 'categories' | 'all';

/** Infer form data type from schema */
export type RuleFormData = z.input<typeof ruleFormSchema>;

export type RuleFormErrors = Partial<Record<keyof RuleFormData, string>>;

// ============================================
// DECIMAL HANDLING UTILITIES
// ============================================

/**
 * Normalize a string to a valid decimal string for the API
 */
export function normalizeDecimal(value: string | number | undefined | null): string | undefined {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }

  if (typeof value === 'number') {
    if (isNaN(value)) return undefined;
    return value.toString();
  }

  let cleaned = value.toString().trim().replace(/%/g, '');

  if (cleaned.startsWith('.')) cleaned = '0' + cleaned;
  if (cleaned.startsWith('-.')) cleaned = '-0' + cleaned.substring(1);
  if (cleaned === '' || cleaned === '-') return undefined;

  const num = parseFloat(cleaned);
  return isNaN(num) ? undefined : cleaned;
}

/**
 * Check if a value represents a valid decimal
 */
export function isValidDecimal(value: string | number | undefined | null): boolean {
  return normalizeDecimal(value) !== undefined;
}

/**
 * Parse string to integer, handling edge cases
 */
export function parseInteger(value: string | number | undefined | null): number | undefined {
  if (value === undefined || value === null || value === '') {
    return undefined;
  }

  if (typeof value === 'number') {
    return isNaN(value) ? undefined : Math.floor(value);
  }

  const num = parseInt(value.toString().trim(), 10);
  return isNaN(num) ? undefined : num;
}

/**
 * Convert API decimal (string | null) to form string
 */
export function decimalToFormString(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return '';
  return value.toString();
}

// ============================================
// TRANSFORMATIONS: API → Form
// ============================================

/** Default form data for new rules */
export const DEFAULT_FORM_DATA: RuleFormData = {
  name: '',
  description: '',
  rule_type: 'sentiment_threshold',
  is_active: true,
  priority: 10,
  scope_type: 'single',
  product_id: '',
  applies_to_products: [],
  applies_to_categories: [],
  sentiment_threshold: '',
  sentiment_direction: 'above',
  competitor_id: '',
  price_position: 'below',
  time_days: '',
  volume_threshold: '',
  viral_threshold_reach: '',
  action: 'increase_percent',
  action_value: '',
  max_change_percent: '',
  min_price: '',
  max_price: '',
  cooldown_hours: '24',
};

/**
 * Transform API PricingRule response to form data
 */
export function ruleToFormData(rule: Partial<PricingRule>): RuleFormData {
  const scopeType: ScopeType = rule.applies_to_all_products
    ? 'all'
    : rule.applies_to_categories?.length
      ? 'categories'
      : rule.applies_to_products?.length
        ? 'multiple'
        : 'single';

  return {
    name: rule.name ?? '',
    description: rule.description ?? '',
    rule_type: rule.rule_type ?? 'sentiment_threshold',
    is_active: rule.is_active ?? true,
    priority: rule.priority ?? 10,
    scope_type: scopeType,
    product_id: rule.product_id ?? '',
    applies_to_products: rule.applies_to_products ?? [],
    applies_to_categories: rule.applies_to_categories ?? [],
    sentiment_threshold: decimalToFormString(rule.sentiment_threshold),
    sentiment_direction: rule.sentiment_direction ?? 'above',
    competitor_id: rule.competitor_id ?? '',
    price_position: rule.price_position ?? 'below',
    time_days: rule.time_days ?? '',
    volume_threshold: decimalToFormString(rule.volume_threshold),
    viral_threshold_reach: decimalToFormString(rule.viral_threshold_reach),
    action: rule.action ?? 'increase_percent',
    action_value: decimalToFormString(rule.action_value),
    max_change_percent: decimalToFormString(rule.max_change_percent),
    min_price: decimalToFormString(rule.min_price),
    max_price: decimalToFormString(rule.max_price),
    cooldown_hours: rule.cooldown_hours?.toString() ?? '24',
  };
}

// ============================================
// TRANSFORMATIONS: Form → API
// ============================================

/**
 * Transform form data to API request payload
 */
export function formDataToRequest(form: RuleFormData): CreatePricingRuleRequest {
  const actionValue = ACTIONS_WITHOUT_VALUE.includes(form.action)
    ? '0'
    : (normalizeDecimal(form.action_value) ?? '0');

  const payload: CreatePricingRuleRequest = {
    name: form.name.trim(),
    description: form.description.trim() || undefined,
    rule_type: form.rule_type,
    is_active: form.is_active,
    priority: form.priority,
    action: form.action,
    action_value: actionValue,
    cooldown_hours: parseInteger(form.cooldown_hours) ?? 24,
  };

  // Scoping
  switch (form.scope_type) {
    case 'single':
      payload.product_id = form.product_id || undefined;
      payload.applies_to_all_products = false;
      break;
    case 'multiple':
      payload.applies_to_products = form.applies_to_products;
      payload.applies_to_all_products = false;
      break;
    case 'categories':
      payload.applies_to_categories = form.applies_to_categories;
      payload.applies_to_all_products = false;
      break;
    case 'all':
      payload.applies_to_all_products = true;
      break;
  }

  // Rule type-specific fields
  switch (form.rule_type) {
    case 'sentiment_threshold': {
      const threshold = normalizeDecimal(form.sentiment_threshold);
      payload.sentiment_threshold = threshold ? parseFloat(threshold) : undefined;
      payload.sentiment_direction = form.sentiment_direction || undefined;
      break;
    }
    case 'competitor_relative':
      payload.competitor_id = form.competitor_id || undefined;
      payload.price_position = form.price_position || undefined;
      break;
    case 'time_based':
      payload.time_days = form.time_days || undefined;
      break;
    case 'volume_surge':
      payload.volume_threshold = parseInteger(form.volume_threshold);
      break;
    case 'viral_detection':
      payload.viral_threshold_reach = parseInteger(form.viral_threshold_reach);
      break;
  }

  // Constraints
  const maxChangePercent = normalizeDecimal(form.max_change_percent);
  const minPrice = normalizeDecimal(form.min_price);
  const maxPrice = normalizeDecimal(form.max_price);

  if (maxChangePercent !== undefined) payload.max_change_percent = maxChangePercent;
  if (minPrice !== undefined) payload.min_price = minPrice;
  if (maxPrice !== undefined) payload.max_price = maxPrice;

  return payload;
}

// ============================================
// VALIDATION
// ============================================

/**
 * Validate form data using Zod schema
 * Returns errors object compatible with form state
 */
export function validateRuleForm(form: RuleFormData): RuleFormErrors {
  const result = ruleFormSchema.safeParse(form);
  
  if (result.success) {
    return {};
  }

  // Convert Zod errors to form errors format
  const errors: RuleFormErrors = {};
  for (const issue of result.error.issues) {
    const path = issue.path[0] as keyof RuleFormData;
    if (path && !errors[path]) {
      errors[path] = issue.message;
    }
  }
  
  return errors;
}

/**
 * Check if form has validation errors
 */
export function isFormValid(form: RuleFormData): boolean {
  return ruleFormSchema.safeParse(form).success;
}

/**
 * Validate and transform in one step
 * Returns either the API payload or validation errors
 */
export function validateAndTransform(form: RuleFormData): 
  | { success: true; data: CreatePricingRuleRequest }
  | { success: false; errors: RuleFormErrors } {
  
  const validation = ruleFormSchema.safeParse(form);
  
  if (!validation.success) {
    const errors: RuleFormErrors = {};
    for (const issue of validation.error.issues) {
      const path = issue.path[0] as keyof RuleFormData;
      if (path && !errors[path]) {
        errors[path] = issue.message;
      }
    }
    return { success: false, errors };
  }
  
  return { success: true, data: formDataToRequest(form) };
}


